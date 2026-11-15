from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.search import router as search_router
from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.services import notify

settings = get_settings()

_LEGACY_NOT_FOUND_BODY = {"error": "not found"}


def _legacy_not_found() -> JSONResponse:
    return JSONResponse(
        content=_LEGACY_NOT_FOUND_BODY,
        status_code=404,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    notify.configure_limits()
    notify.init_notify_token()
    yield


app = FastAPI(title="NASA Space App Challenge", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def legacy_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 405:
        return _legacy_not_found()
    if exc.status_code == 404 and exc.detail == "Not Found":
        return _legacy_not_found()
    return JSONResponse(content={"detail": exc.detail}, status_code=exc.status_code)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(search_router)
app.include_router(v1_router)