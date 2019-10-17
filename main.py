from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api import settings
from api.db import CONNECTION_STR, db
from api.views import router

app = FastAPI(title="Bitcart", version="1.0")
app.include_router(router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.set_bind(CONNECTION_STR)
    await db.gino.create_all()


@app.on_event("shutdown")
async def shutdown():
    if settings.TEST:
        await db.gino.drop_all()
