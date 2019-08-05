from fastapi import APIRouter, Body
from starlette.websockets import WebSocket
from .schemes import Wallet, User
# from .models import Wallet
from . import crud

router = APIRouter()


@router.post("/users")
async def create_user(user: User):
    await crud.create_user(user)
    return user


@router.get("/wallets")
async def get_wallets():
    return []


@router.post("/wallets")
async def add_wallet(wallet: Wallet):
    await create_user(wallet)
    await Wallet.create(wallet)
    return wallet


@router.get("/stores")
async def get_stores():
    return []


@router.websocket("/")
async def h(websocket: WebSocket):
    websocket.accept()
