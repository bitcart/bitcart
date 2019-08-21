from fastapi import FastAPI

from api.db import CONNECTION_STR, db
from api.views import router
from api import settings

app = FastAPI(title="Bitcart", version="1.0")
app.include_router(router)


@app.on_event("startup")
async def startup():
    await db.set_bind(CONNECTION_STR)
    await db.gino.create_all()


@app.on_event("shutdown")
async def shutdown():
    if settings.TEST:
        await db.gino.drop_all()
    await settings.btc.close()
