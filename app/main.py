from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from app.logging import setup_logging

setup_logging()

import logging
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent
sys.path.append(str(src_path))
sys.path.append(str(src_path.parent))
sys.path.append(str(src_path / "api"))
sys.path.append(str(src_path / "sql"))
sys.path.append(str(src_path / "api" / "api_v1"))
sys.path.append(str(src_path / "api" / "api_v1" / "endpoints"))
sys.path.append(str(src_path / "api" / "api_v1" / "websockets"))

import redis.asyncio as redis
import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.templating import Jinja2Templates
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app import CONFIG
from app.api import v1_router
from app.sql import Base, engine

if CONFIG.PRODUCTION:
    sentry_sdk.init(
        dsn=CONFIG.SENTRY_DSN,
        enable_tracing=True,
    )

Base.metadata.create_all(bind=engine)
logger = logging.getLogger(__name__)

directory = Path(__file__).parent


class App(FastAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.templates = Jinja2Templates(directory=str(directory / "templates"))


app = App(
    title=CONFIG.PROJECT_NAME,
    openapi_url="/openapi.json" if CONFIG.ENABLE_DOCS else None,
)
app.include_router(v1_router, prefix=CONFIG.API_V1_STR)
app.mount("/static", StaticFiles(directory=directory / "static"), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origins if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    if not app.openapi_schema:
        s = []
        if CONFIG.PRODUCTION:
            s.append(
                {"url": "https://api.synccord.com", "description": "Production Server"}
            )
        s.append({"url": "http://localhost:8000", "description": "Development Server"})
        app.openapi_schema = get_openapi(
            title=CONFIG.PROJECT_NAME,
            version=CONFIG.VERSION,
            summary="This is the API for Synccord.",
            terms_of_service="https://synccord.com/terms",
            contact={
                "name": "Synccord",
                "url": "https://synccord.com/",
                "email": "support@synccord.com",
            },
            routes=app.routes,
            servers=s,
        )
    return app.openapi_schema


app.openapi = custom_openapi


async def http_ratelimit_callback(request: Request, response: Response, expire: int):
    """
    default callback when too many requests
    :param request:
    :param expire: The remaining milliseconds
    :param response:
    :return:
    """
    raise HTTPException(
        HTTP_429_TOO_MANY_REQUESTS,
        "Too Many Requests",
        headers={"Retry-After": str(expire)},
    )


@app.on_event("startup")
async def startup():
    if CONFIG.ENABLE_DOCS:
        logger.info(f"{CONFIG.SERVER_HOST}/docs")
    red = redis.from_url(CONFIG.REDIS_URL, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(
        red, prefix="synccord-ratelimit", http_callback=http_ratelimit_callback
    )


@app.get("/ping/", dependencies=[Depends(RateLimiter(times=5, seconds=1))])
async def ping():
    return JSONResponse(
        content={"ping": "pong"},
        status_code=200,
        headers={"X-Custom-Header": "custom header value"},
    )
