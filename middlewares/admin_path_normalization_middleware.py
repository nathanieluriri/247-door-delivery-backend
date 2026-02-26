class AdminPathNormalizationMiddleware:
    """
    Avoid slash-based redirects for admin routes by canonicalizing
    `/api/v1/admins/.../` -> `/api/v1/admins/...` before routing.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if (
                path.startswith("/api/v1/admins/")
                and len(path) > len("/api/v1/admins/")
                and path.endswith("/")
            ):
                new_scope = dict(scope)
                new_scope["path"] = path.rstrip("/")
                scope = new_scope
        await self.app(scope, receive, send)
