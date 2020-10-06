import asyncio

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from api import settings
from api.db import db
from api.ext import tor as tor_ext
from api.utils import run_repeated
from api.views import router

app = FastAPI(title="Bitcart", version="1.0", docs_url="/", redoc_url="/redoc")
app.mount("/images", StaticFiles(directory="images"), name="images")
app.include_router(router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def add_onion_host(request: Request, call_next):
    response = await call_next(request)
    host = request.headers.get("host", "").split(":")[0]
    if tor_ext.TorService.onion_host and not tor_ext.is_onion(host):
        response.headers["Onion-Location"] = tor_ext.TorService.onion_host + request.url.path
    return response


@app.on_event("startup")
async def startup():
    await settings.init_db()
    asyncio.ensure_future(run_repeated(tor_ext.refresh, 120, 10))
    if settings.TEST:
        await db.gino.create_all()


@app.on_event("shutdown")
async def shutdown():
    if settings.TEST:
        await db.gino.drop_all()
