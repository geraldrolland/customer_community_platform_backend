"""Application entrypoint for the HappenHub Community Event Platform API.

Builds the FastAPI application, initializes the database schema, registers
the middleware stack (TrustedHost, CORS, Auth, CSRF, RequestLogger) and the
API routers, and exposes the static media mount.
"""
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

import models
from core.settings import settings
from database import Base, engine
from middleware.auth_middleware import AuthMiddleware
from middleware.csrf_middleware import CsrfMiddleware
from middleware.request_logger_middleware import RequestLoggerMiddleware
from router import auth, event, static, venue, vote
from router.static import MEDIA_DIR

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.APP_NAME)

Base.metadata.create_all(bind=engine)

MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(CsrfMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
app.add_middleware(RequestLoggerMiddleware)

app.include_router(event.router)
app.include_router(venue.router)
app.include_router(auth.router)
app.include_router(static.router)
app.include_router(vote.router)
app.mount("/static/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/")
def root():
    """Health-check endpoint.

    Returns:
        dict: A greeting payload confirming the API is reachable.
    """
    return {"message": "Community Event Platform API"}
