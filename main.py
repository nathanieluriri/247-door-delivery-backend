import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from core.payments.manager import configure_payment_manager
from core.scheduler import scheduler
from middlewares.request_timing_middleware import RequestTimingMiddleware
from limits.strategies import FixedWindowRateLimiter
from datetime import datetime,timedelta
from limits.storage import RedisStorage
from schemas.response_schema import APIResponse
from limits import parse
import time   
import os
import logging
from logging.config import dictConfig
from prometheus_fastapi_instrumentator import Instrumentator
from middlewares.structured_logging_middleware import StructuredLoggingMiddleware
from pymongo import ASCENDING
from contextlib import asynccontextmanager
from pymongo import MongoClient
import redis
from apscheduler.triggers.interval import IntervalTrigger
from starlette.middleware.sessions import SessionMiddleware
from middlewares.admin_path_normalization_middleware import AdminPathNormalizationMiddleware
from middlewares.rate_limiting_middleware import RateLimitingMiddleware
from services.sse_service import cleanup_stale_driver_locations
MONGO_URI = os.getenv("MONGO_URL")
REDIS_URI = f"redis://{os.getenv('REDIS_HOST', '127.0.0.1')}:{os.getenv('REDIS_PORT', '6379')}/0"
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
def _flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
def _float_setting(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default
def _int_setting(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default
RUN_STARTUP_MIGRATOR = _flag("RUN_STARTUP_MIGRATOR", True)
MIGRATOR_IN_BACKGROUND = _flag("MIGRATOR_IN_BACKGROUND", True)
REHYDRATE_IN_BACKGROUND = _flag("REHYDRATE_IN_BACKGROUND", True)
REHYDRATE_TIMEOUT_SECONDS = _float_setting("REHYDRATE_TIMEOUT_SECONDS", 20.0)
STARTUP_INDEXES_IN_BACKGROUND = _flag("STARTUP_INDEXES_IN_BACKGROUND", True)
STARTUP_INDEX_TIMEOUT_SECONDS = _float_setting("STARTUP_INDEX_TIMEOUT_SECONDS", 20.0)
MINIMAL_BOOT_MODE = _flag("MINIMAL_BOOT_MODE", False)
SESSION_SECRET_KEY = (
    os.getenv("SESSION_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "not-some-random-string"
)
SESSION_MAX_AGE_SECONDS = max(_int_setting("SESSION_MAX_AGE_SECONDS", 600), 1)
SESSION_HTTPS_ONLY = _flag("SESSION_HTTPS_ONLY", False)
SESSION_SAME_SITE = os.getenv("SESSION_SAME_SITE", "lax")
startup_logger = logging.getLogger("app.startup")
async def _run_migrator() -> None:
    from redis_om import Migrator
    from starlette.concurrency import run_in_threadpool

    started = time.perf_counter()
    await run_in_threadpool(Migrator().run)
    startup_logger.info(
        "startup_migrator_completed",
        extra={"duration_ms": round((time.perf_counter() - started) * 1000, 2)},
    )
async def _run_rehydrate_jobs() -> None:
    from services.ride_service import rehydrate_scheduled_ride_jobs

    started = time.perf_counter()
    if REHYDRATE_TIMEOUT_SECONDS > 0:
        await asyncio.wait_for(
            rehydrate_scheduled_ride_jobs(),
            timeout=REHYDRATE_TIMEOUT_SECONDS,
        )
    else:
        await rehydrate_scheduled_ride_jobs()
    startup_logger.info(
        "startup_rehydrate_completed",
        extra={"duration_ms": round((time.perf_counter() - started) * 1000, 2)},
    )


async def _ensure_startup_indexes() -> None:
    from core.database import db

    started = time.perf_counter()
    await asyncio.gather(
        db.stripe_events.create_index(
            [("stripe_id", 1)],
            unique=True,
        ),
        db.chats.create_index(
            [("rideId", 1)],
        ),
        db.reset_tokens.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,
        ),
        db.reset_tokens.create_index(
            [("userId", 1)],
            unique=True,
            name="unique_active_reset_token",
            partialFilterExpression={
                "expires_at": {"$exists": True}
            },
        ),
        db.refreshToken.create_index(
            [("expiresAt", ASCENDING)],
            expireAfterSeconds=0,
            name="refresh_token_expires_idx",
        ),
        db.ratings.create_index(
            [("rideId", 1), ("raterId", 1)],
            unique=True,
            name="rating_ride_rater_unique",
            partialFilterExpression={
                "rideId": {"$exists": True},
                "raterId": {"$exists": True},
            },
        ),
    )
    startup_logger.info(
        "startup_indexes_ready",
        extra={"duration_ms": round((time.perf_counter() - started) * 1000, 2)},
    )
async def _run_background_startup_step(step: str, runner) -> None:
    started = time.perf_counter()
    try:
        await runner()
    except Exception:
        startup_logger.exception("startup_background_step_failed", extra={"step": step})
        return
    startup_logger.info(
        "startup_background_step_completed",
        extra={
            "step": step,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )
# --- Heartbeat Function ---
def apscheduler_heartbeat():
        timestamp = time.time()
        redis_client.set("apscheduler:heartbeat", str(timestamp), ex=60)  # expires in 60s
        
        
@asynccontextmanager
async def lifespan(app:FastAPI):
    startup_started = time.perf_counter()
    app.state.startup_background_tasks = []
    # --- Add Heartbeat Job ---
    scheduler.add_job(
        apscheduler_heartbeat,
        trigger=IntervalTrigger(seconds=105),
        id="apscheduler_heartbeat",
        name="APScheduler Heartbeat",
        replace_existing=True
    )
    scheduler.add_job(
        cleanup_stale_driver_locations,
        trigger=IntervalTrigger(seconds=180),
        id="driver_presence_cleanup",
        name="Remove stale driver geo entries",
        replace_existing=True,
    )
    if STARTUP_INDEXES_IN_BACKGROUND:
        app.state.startup_background_tasks.append(
            asyncio.create_task(
                _run_background_startup_step("ensure_indexes", _ensure_startup_indexes),
                name="startup:ensure_indexes",
            )
        )
    else:
        if STARTUP_INDEX_TIMEOUT_SECONDS > 0:
            await asyncio.wait_for(
                _ensure_startup_indexes(),
                timeout=STARTUP_INDEX_TIMEOUT_SECONDS,
            )
        else:
            await _ensure_startup_indexes()
    configure_payment_manager(force=True)
    scheduler.start()
    if RUN_STARTUP_MIGRATOR:
        if MIGRATOR_IN_BACKGROUND:
            app.state.startup_background_tasks.append(
                asyncio.create_task(
                    _run_background_startup_step("migrator", _run_migrator),
                    name="startup:migrator",
                )
            )
        else:
            await _run_migrator()
    if REHYDRATE_IN_BACKGROUND:
        app.state.startup_background_tasks.append(
            asyncio.create_task(
                _run_background_startup_step("rehydrate_scheduled_rides", _run_rehydrate_jobs),
                name="startup:rehydrate_scheduled_rides",
            )
        )
    else:
        await _run_rehydrate_jobs()
    startup_logger.info(
        "startup_ready",
        extra={"duration_ms": round((time.perf_counter() - startup_started) * 1000, 2)},
    )
    try:
        yield
    finally:
        for task in app.state.startup_background_tasks:
            if not task.done():
                task.cancel()
        if app.state.startup_background_tasks:
            await asyncio.gather(*app.state.startup_background_tasks, return_exceptions=True)
        scheduler.shutdown()
# Create the FastAPI app
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
dictConfig(
    {
        "version": 1,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            }
        },
        "handlers": {
            "default": {
                "level": LOG_LEVEL,
                "class": "logging.StreamHandler",
                "formatter": "json",
            }
        },
        "root": {"level": LOG_LEVEL, "handlers": ["default"]},
    }
)
API_DESCRIPTION = """
Door Delivery API powers riders, drivers, and admin operations for ride requests,
dispatching, payments, and compliance workflows.
## Authentication
- Most endpoints require `Authorization: Bearer <access_token>`.
- Access tokens are issued on login and refresh flows.
- Some endpoints accept an optional token to infer identity.
## Rate Limits
Rate limits are enforced via Redis-based fixed windows:
- Anonymous: 120/min
- Member: 160/min
- Admin: 240/min
## Pagination
List endpoints typically support `start`/`stop` (offset + limit) or `page_number`.
## Errors
Errors return a consistent `APIResponse` payload with `status_code`, `detail`, and `data`.
"""
tags_metadata = [
    {
        "name": "Health",
        "description": "Service health checks and operational diagnostics.",
    },
    {
        "name": "Admins",
        "description": "Admin authentication, user management, compliance, and audit tools.",
    },
    {
        "name": "Drivers",
        "description": "Driver onboarding, profile, vehicle, documents, rides, and payouts.",
    },
    {
        "name": "Riders",
        "description": "Rider authentication, profile, addresses, rides, and ratings.",
    },
    {
        "name": "Payments",
        "description": "Payment webhooks, provider switching, and payment event reporting.",
    },
    {
        "name": "SSE",
        "description": "Server-Sent Events streams and acknowledgements.",
    },
    {
        "name": "Chats",
        "description": "Ride chat creation and streaming.",
    },
]
app = FastAPI(
    lifespan=lifespan,
    title="Door Delivery API",
    summary="On-demand delivery and ride platform API.",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_tags=tags_metadata,
)
Instrumentator().instrument(app).expose(app, include_in_schema=False)
app.add_middleware(AdminPathNormalizationMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site=SESSION_SAME_SITE, # type: ignore
    https_only=SESSION_HTTPS_ONLY,
)
redis_url = (
    os.getenv("CELERY_BROKER_URL")
    or os.getenv("REDIS_URL")
    or f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0"
)
# Setup limiter
storage = RedisStorage(
   redis_url
)
limiter = FixedWindowRateLimiter(storage)
RATE_LIMITS = {
    "anonymous": parse("120/minute"),
    "member": parse("160/minute"),
    "admin": parse("240/minute"),
}
app.state.limiter = limiter
app.state.rate_limits = RATE_LIMITS
# Add the middleware to the app
# ||||||||||||||||||||||||||||||||||||
app.add_middleware(RateLimitingMiddleware)
# ||||||||||||||||||||||||||||||||||||
# Add CORS middleware (be cautious in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Custom exception handler for HTTPExceptions
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse(
            status_code=exc.status_code,
            data=None,
            detail=exc.detail,
        ).dict()
    )
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=APIResponse(
            status_code=500,
            data=None,
            detail="Internal server error",
        ).dict(),
    )
async def test_scheduler(message):
    print(message)
@app.post(
    "/ride/publish-test",
    response_model=APIResponse[dict],
    summary="Test publish ride request",
    description="Publishes a ride request event to nearby drivers using a fixed payload.",
)
async def publish_ride_request_test():
    from services.sse_service import publish_ride_request

    data = {
        "pickup": "ChIJpWm44e0LThARBZjsnnXbdXs",
        "destination": "ChIJ68mtM_IKThARPkerhQBAsqc",
        "vehicleType": "CAR",
        "pickupSchedule": 1770393207214,
        "paymentStatus": True,
        "price": 8506.4,
        "rideStatus": "findingDriver",
        "userId": "694573edfb42ab4e70634aec",
        "checkoutSessionObject": {
            "id": "cs_test_a1BFh6SvD7J9dKh5UgNFLgxN44sXjym4gb9WgNkXdsww4iS9qxyE4WkYlv",
            "payment_status": "paid",
            "amount_total": 851,
            "currency": "gbp",
            "payment_intent": "pi_3SxrLeEM4mSGBUuf0df4RIUB",
            "payment_link": "plink_1SxrLXEM4mSGBUufQMJQRc72",
            "metadata": {
                "ride_id": "69860e78919dd9c5d0ac6a8d",
                "user_id": "694573edfb42ab4e70634aec",
            },
        },
        "stripeEvent": {
            "id": "evt_1SxrLgEM4mSGBUufkI7FJ6Qd",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_a1BFh6SvD7J9dKh5UgNFLgxN44sXjym4gb9WgNkXdsww4iS9qxyE4WkYlv",
                    "object": "checkout.session",
                    "adaptive_pricing": {"enabled": True},
                    "after_expiration": None,
                    "allow_promotion_codes": False,
                    "amount_subtotal": 851,
                    "amount_total": 851,
                    "automatic_tax": {
                        "enabled": False,
                        "liability": None,
                        "provider": None,
                        "status": None,
                    },
                    "billing_address_collection": "auto",
                    "cancel_url": "https://stripe.com",
                    "client_reference_id": None,
                    "client_secret": None,
                    "collected_information": None,
                    "consent": None,
                    "consent_collection": None,
                    "created": 1770393209,
                    "currency": "gbp",
                    "currency_conversion": None,
                    "custom_fields": [],
                    "custom_text": {
                        "after_submit": None,
                        "shipping_address": None,
                        "submit": None,
                        "terms_of_service_acceptance": None,
                    },
                    "customer": None,
                    "customer_account": None,
                    "customer_creation": "if_required",
                    "customer_details": {
                        "address": {
                            "city": "Bristol",
                            "country": "GB",
                            "line1": "3 Princess Street",
                            "line2": "Units 2",
                            "postal_code": "BS3 4AG",
                            "state": None,
                        },
                        "business_name": None,
                        "email": "nathaniel@doux.finance",
                        "individual_name": None,
                        "name": "Nath",
                        "phone": None,
                        "tax_exempt": "none",
                        "tax_ids": [],
                    },
                    "customer_email": None,
                    "discounts": [],
                    "expires_at": 1770479609,
                    "invoice": None,
                    "invoice_creation": {
                        "enabled": False,
                        "invoice_data": {
                            "account_tax_ids": None,
                            "custom_fields": None,
                            "description": None,
                            "footer": None,
                            "issuer": None,
                            "metadata": {},
                            "rendering_options": None,
                        },
                    },
                    "livemode": False,
                    "locale": "auto",
                    "metadata": {
                        "ride_id": "69860e78919dd9c5d0ac6a8d",
                        "user_id": "694573edfb42ab4e70634aec",
                    },
                    "mode": "payment",
                    "origin_context": None,
                    "payment_intent": "pi_3SxrLeEM4mSGBUuf0df4RIUB",
                    "payment_link": "plink_1SxrLXEM4mSGBUufQMJQRc72",
                    "payment_method_collection": "if_required",
                    "payment_method_configuration_details": {
                        "id": "pmc_1SIYzrEM4mSGBUufrLGUnZLs",
                        "parent": None,
                    },
                    "payment_method_options": {},
                    "payment_method_types": [
                        "card",
                        "link",
                        "revolut_pay",
                        "amazon_pay",
                    ],
                    "payment_status": "paid",
                    "permissions": None,
                    "phone_number_collection": {"enabled": False},
                    "recovered_from": None,
                    "saved_payment_method_options": None,
                    "setup_intent": None,
                    "shipping_address_collection": None,
                    "shipping_cost": None,
                    "shipping_details": None,
                    "shipping_options": [],
                    "status": "complete",
                    "submit_type": "auto",
                    "subscription": None,
                    "success_url": "https://yourapp.com/payment/success",
                    "total_details": {
                        "amount_discount": 0,
                        "amount_shipping": 0,
                        "amount_tax": 0,
                    },
                    "ui_mode": "hosted",
                    "url": None,
                    "wallet_options": None,
                }
            },
        },
        "origin": {"latitude": 9.0725085, "longitude": 7.4953609},
        "paymentLink": "https://buy.stripe.com/test_6oUfZhebbg0R0LX6xP77O1A",
        "map": {
            "totalDistanceMeters": 4173,
            "totalDurationSeconds": 391,
            "encodedPolyline": "s~jv@y}vl@VKjDd@d@Dv@F|@AhAB|AKfBYbCo@zAo@hAk@MYOH_@R_@Pa@PqAVmAFoAEeAO[GeEeA}Ba@aCWcBIkBGuA?}DLy@@}@GmD]gBMuCQkAE}AByCXuB`@uAd@iAf@c@XcAv@oAfAmAvA_@f@yJ|OS`@[CQBKBOHYr@C^@PC`@YtAYv@o@`BeBhFe@dBg@jB`Bd@vCt@`FpAM^Wz@q@nCaCbJiBtHi@rBs@hBMXk@_@W`@EV",
            "waypointOrder": [],
            "legs": [
                {
                    "startAddress": "SCHATZ PARK AND GARDEN (JAV CHRISTMAS VILLAGE), Shehu Shagari Wy, Wuse, Abuja 904101, Federal Capital Territory, Nigeria",
                    "endAddress": "61 Aguiyi Ironsi St, Maitama, Abuja 904101, Federal Capital Territory, Nigeria",
                    "distanceMeters": 4173,
                    "durationSeconds": 391,
                }
            ],
        },
        "id": "69860e78919dd9c5d0ac6a8d",
        "dateCreated": 1770393207,
        "lastUpdated": 1770393217,
    }
    pickup_location = (data["origin"]["latitude"], data["origin"]["longitude"])
    count = await publish_ride_request(
        ride_id=data["id"],
        pickup=data["pickup"],
        destination=data["destination"],
        vehicle_type=str(data["vehicleType"]),
        fare_estimate=data["price"],
        rider_id=data["userId"],
        pickup_location=pickup_location,
    )
    return APIResponse(
        status_code=200,
        data={"published_to": count, "ride_id": data["id"]},
        detail="Ride request published",
    )
# Simple test route
@app.get(
    "/",
    tags=["Health"],
    include_in_schema=False,
    summary="Root ping (internal)",
    description="Lightweight ping endpoint to verify the API process is running.",
)
def root():
    """
    Internal root ping used for smoke checks and scheduler testing.
    Access: Public (no auth), intended for internal diagnostics.
    """
    from core.scheduler import scheduler

    run_time = datetime.now() + timedelta(seconds=20)
    scheduler.add_job(test_scheduler,"date",run_date=run_time,args=[f"test message {run_time}"],misfire_grace_time=31536000)
    data= {"message": "Hello from FasterAPI!"}
    return APIResponse(status_code=200,detail="Successfully fetched data",data=data)
# Clients
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
redis_client = redis.Redis.from_url(REDIS_URI, socket_connect_timeout=2)
# Health check route
@app.get(
    "/health",
    tags=["Health"],
    summary="Lightweight health check",
    description="Returns a compact status snapshot for MongoDB, Redis, APScheduler, and Celery.",
    response_description="Overall service status with dependency snapshots.",
)
async def health_check_regular():
    """
    Return a compact health snapshot of MongoDB, Redis, APScheduler, and Celery.
    Access: Public (no auth).
    """
    from celery_worker import celery_app

    overall_status = "healthy"
    services = {}
    # --- MongoDB Check ---
    start_time = time.perf_counter()
    try:
        mongo_client.admin.command("ping")
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        services["mongo"] = {
            "status": "healthy",
            "latency_ms": latency,
            "message": "MongoDB ping successful"
        }
    except Exception as e:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        services["mongo"] = {
            "status": "unhealthy",
            "latency_ms": latency,
            "message": str(e)
        }
        overall_status = "degraded"
    # --- Redis Check ---
    start_time = time.perf_counter()
    try:
        redis_client.ping()
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        services["redis"] = {
            "status": "healthy",
            "latency_ms": latency,
            "message": "Redis ping successful"
        }
    except Exception as e:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        services["redis"] = {
            "status": "unhealthy",
            "latency_ms": latency,
            "message": str(e)
        }
        overall_status = "degraded"
    # --- Worker (Heartbeat) Check ---
    start_time = time.perf_counter()
    # Check APScheduler
    try:
        aps_heartbeat = redis_client.get("apscheduler:heartbeat")
        if aps_heartbeat:
            last_seen = float(aps_heartbeat)
            age = time.time() - last_seen
            if age <= 30:
                services["apscheduler"] = {
                    "status": "healthy",
                    "latency_ms": 0,
                    "message": f"Last heartbeat {int(age)}s ago"
                }
            else:
                services["apscheduler"] = {
                    "status": "degraded",
                    "latency_ms": 0,
                    "message": f"Stale heartbeat (last seen {int(age)}s ago)"
                }
                overall_status = "degraded"
        else:
            services["apscheduler"] = {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": "No heartbeat found"
            }
            overall_status = "degraded"
    except Exception as e:
        services["apscheduler"] = {
            "status": "unhealthy",
            "latency_ms": 0,
            "message": str(e)
        }
        overall_status = "degraded"
    # --- Final Structured Response ---
    data = {
        "status": overall_status,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "services": services
    }
     # --- Celery health check ---
    try:
        result = celery_app.send_task("celery_worker.test_scheduler", args=["Health check ping"])
        response = result.get(timeout=5)
        services["celery"] = {
            "status": "healthy",
            "latency_ms": 0,
            "message": f"Worker response received successfully",
            "task_id": result.id
        }
    except TimeoutError:
        services["celery"] = {
            "status": "unhealthy",
            "latency_ms": 0,
            "message": "Celery task timed out"
        }
        overall_status = "degraded"
    except Exception as e:
        services["celery"] = {
            "status": "unhealthy",
            "latency_ms": 0,
            "message": str(e)
        }
        overall_status = "degraded"
    # --- Final response ---
    return APIResponse(
        status_code=200 if overall_status == "healthy" else 207,
        detail=f"Health check completed with status: {overall_status}",
        data={"status": overall_status, "services": services}
    )
@app.get(
    "/test_broadcast",
    tags=["SSE"],
    summary="Trigger a test ride request broadcast",
    description="Publishes a synthetic ride request event to validate SSE delivery.",
    response_description="Publishes a test SSE event for driver discovery.",
)
async def test_sse_broadcast(pickup_lat: float, pickup_lon: float):
    """
    Send a synthetic ride request event to validate SSE plumbing.
    Access: Public (no auth), intended for internal testing only.
    """
    from services.sse_service import publish_ride_request

    await publish_ride_request(
        ride_id="1234567897542",
        pickup=f"{pickup_lat},{pickup_lon}",
        destination="9.0706,7.4675",
        vehicle_type="CAR",
        fare_estimate=123445,
        rider_id=None,
        pickup_location=(pickup_lat, pickup_lon),
    )
@app.get(
    "/health-detailed",
    tags=["Health"],
    summary="Detailed health check",
    description="Returns a detailed per-service report with latency and status metadata.",
    response_description="Per-service status with latency, messages, and timestamps.",
)
async def health_check():
    """
    Return a verbose health report across MongoDB, Redis, APScheduler, and Celery.
    Access: Public (no auth).
    """
    from celery_worker import celery_app

    services = {}
    # This list will track the status of all services
    service_statuses = [] 
    # Note: 'overall_status' will be determined at the end,
    # not incrementally.
    # --- MongoDB Check ---
    service_name = "mongo"
    service_desc = "Primary Database (MongoDB)"
    start_time = time.perf_counter()
    try:
        mongo_client.admin.command("ping")
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "healthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency,
            "message": "Connection successful and ping acknowledged."
        }
    except Exception as e:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "unhealthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency,
            "message": f"Connection failed: {str(e)}"
        }
    service_statuses.append(status)
    # --- Redis Check ---
    service_name = "redis"
    service_desc = "Cache & Message Broker (Redis)"
    start_time = time.perf_counter()
    try:
        redis_client.ping()
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "healthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency,
            "message": "Connection successful and ping acknowledged."
        }
    except Exception as e:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "unhealthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency,
            "message": f"Connection failed: {str(e)}"
        }
    service_statuses.append(status)
    # --- APScheduler (Heartbeat) Check ---
    service_name = "apscheduler"
    service_desc = "Internal Job Scheduler (APScheduler)"
    start_time = time.perf_counter()
    try:
        # Check for the heartbeat key set by the scheduler
        aps_heartbeat = redis_client.get("apscheduler:heartbeat")
        latency = round((time.perf_counter() - start_time) * 1000, 2) # Latency of the check itself
        if aps_heartbeat:
            last_seen = float(aps_heartbeat)
            age = time.time() - last_seen
            if age <= 30: # Healthy if heartbeat is within 30 seconds
                status = "healthy"
                message = f"Scheduler is active. Last heartbeat {int(age)}s ago."
            else: # Degraded if heartbeat is stale
                status = "degraded"
                message = f"Stale heartbeat. Last seen {int(age)}s ago. Scheduler may be stuck or overloaded."
            services[service_name] = {
                "description": service_desc,
                "status": status,
                "latency_ms": latency,
                "message": message
            }
        else: # Unhealthy if no heartbeat key is found
            status = "unhealthy"
            services[service_name] = {
                "description": service_desc,
                "status": status,
                "latency_ms": latency,
                "message": "No heartbeat found. Scheduler may be down or has not run yet."
            }
    except Exception as e:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "unhealthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency,
            "message": f"Failed to check scheduler heartbeat: {str(e)}"
        }
    service_statuses.append(status)
    # --- Celery Worker Check ---
    # This check is now run *before* the final response is built
    service_name = "celery"
    service_desc = "Background Task Worker (Celery)"
    start_time = time.perf_counter()
    task_id = None
    try:
        result = celery_app.send_task("celery_worker.test_scheduler", args=["Health check ping"])
        task_id = result.id
        # Wait for 5 seconds for the worker to respond
        response = result.get(timeout=5) 
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "healthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency, # Now captures actual task round-trip time
            "message": f"Worker task executed successfully. Response: '{response}'",
            "task_id": task_id
        }
    except TimeoutError:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "unhealthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency, # Will be ~5000+
            "message": "Celery task timed out after 5 seconds. Worker may be busy or down.",
            "task_id": task_id
        }
    except Exception as e:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        status = "unhealthy"
        services[service_name] = {
            "description": service_desc,
            "status": status,
            "latency_ms": latency,
            "message": f"Celery task failed to execute: {str(e)}",
            "task_id": task_id
        }
    service_statuses.append(status)
    # --- Determine Overall Status ---
    if "unhealthy" in service_statuses:
        overall_status = "unhealthy"
    elif "degraded" in service_statuses:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    # --- Final Structured Response ---
    data = {
        "status": overall_status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), # Using ISO 8601 format
        "services": services
    }
    # --- Final response ---
    http_status_code = 200 if overall_status == "healthy" else 207
    return APIResponse(
        status_code=http_status_code,
        detail=f"Health check completed with status: {overall_status}",
        data=data  
    )
# --- auto-routes-start ---
if not MINIMAL_BOOT_MODE:
    from api.v1.admin_route import router as v1_admin_route_router
    from api.v1.driver import router as v1_driver_router
    from api.v1.rider_route import router as v1_rider_route_router
    from api.v1.payment import router as v1_payment_router
    from api.v1.sse import router as v1_sse_router
    from api.v1.quarantine import router as v1_quarantine_router
    from api.v1.chat import router as v1_chat_router
    from api.web.payment_template_route import router as web_payment_template_router
    from api.web.fake_onboarding_template_route import router as web_fake_onboarding_router

    app.include_router(v1_admin_route_router, prefix='/api/v1', include_in_schema=True)
    app.include_router(v1_driver_router, prefix='/api/v1')
    app.include_router(v1_rider_route_router, prefix='/api/v1')
    app.include_router(v1_payment_router, prefix='/api/v1', include_in_schema=True)
    app.include_router(v1_sse_router, prefix='/api/v1')
    app.include_router(v1_quarantine_router, prefix='/api/v1')
    app.include_router(v1_chat_router, prefix='/api/v1')
    app.include_router(web_payment_template_router, prefix='/api', include_in_schema=False)
    app.include_router(web_fake_onboarding_router, prefix='/api', include_in_schema=False)
else:
    logging.warning("MINIMAL_BOOT_MODE enabled: skipping API router imports")
# --- auto-routes-end ---
