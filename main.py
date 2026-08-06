from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import models
from database import Base, engine
from middleware.auth_middleware import AuthMiddleware
from router import auth, event, static, venue, vote
from router.static import MEDIA_DIR

app = FastAPI(title="Community Event Platform API")

Base.metadata.create_all(bind=engine)

MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(AuthMiddleware)

app.include_router(event.router)
app.include_router(venue.router)
app.include_router(auth.router)
app.include_router(static.router)
app.include_router(vote.router)
app.mount("/static/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/")
def root():
    return {"message": "Community Event Platform API"}
