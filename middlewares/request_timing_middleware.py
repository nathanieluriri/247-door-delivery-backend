from starlette.middleware.base import BaseHTTPMiddleware
import time   

class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Record the start time before processing the request
        start_time = time.time()
        
        # Process the request and get the response
        response = await call_next(request)
        
        # Calculate the time taken to process the request
        process_time = time.time() - start_time
        
        # You can log the time or set it in the response headers
        response.headers['X-Process-Time'] = str(process_time)
        
        # Optionally, print it for logging purposes
        print(f"Request to {request.url} took {process_time:.6f} seconds")
        
        return response
    
    