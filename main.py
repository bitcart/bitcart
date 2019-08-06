from fastapi import FastAPI

from gui.db import CONNECTION_STR, db
from gui.models import User, Wallet
from gui.views import router

app = FastAPI(title="Bitcart", version="1.0")
app.include_router(router)


@app.on_event("startup")
async def startup():
    await db.set_bind(CONNECTION_STR)
    await db.gino.create_all()
