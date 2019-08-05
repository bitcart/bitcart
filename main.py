from fastapi import FastAPI
from gui.views import router
from gui.db import CONNECTION_STR, db
from gui.models import Wallet

app = FastAPI(title="Bitcart", version="1.0")
app.include_router(router)


@app.on_event("startup")
async def startup():
    print('y')
    await db.set_bind(CONNECTION_STR)
    await db.gino.create_all()
    print((await Wallet.create()).id)
