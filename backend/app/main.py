"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import get_db, init_db
from .routers import alerts, audit, auth, cases, dashboard, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("soc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db(get_db())
        log.info("MongoDB ready")
    except Exception as exc:
        log.error("Could not initialise MongoDB (%s). Is mongod running?", type(exc).__name__)
    yield


app = FastAPI(
    title="AI SOC Analyst Assistant API",
    description="Educational SOC incident-management platform (simulated alerts). "
                "Not a production SIEM. Use **Authorize** with a username/email + password to try endpoints.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,  # explicit allow-list, never "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # Default FastAPI echoes the submitted value back ("input"), which could leak a password.
    errors = [{"loc": [str(x) for x in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


for r in (auth.router, users.router, alerts.router, cases.router, audit.router, dashboard.router):
    app.include_router(r)


@app.get("/api/health", tags=["Meta"])
def health():
    try:
        get_db().command("ping")
        return {"status": "ok", "database": "up"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
