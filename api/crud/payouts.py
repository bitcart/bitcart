import asyncio
from collections import defaultdict

from api import models, schemes, utils
from api.ext import payouts as payouts_ext
from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


async def create_payout(payout: schemes.CreatePayout, user: schemes.User):
    d = payout.dict()
    store = await utils.database.get_object(models.Store, d["store_id"], user)
    d["currency"] = d["currency"] or store.default_currency or "USD"
    d["user_id"] = store.user_id
    obj = await utils.database.create_object(models.Payout, d)
    return obj


async def batch_payout_action(
    query, settings: schemes.BatchSettings, user: schemes.User
):  # pragma: no cover: tested in regtest
    if settings.command == "send":
        wallets = settings.options.get("wallets", {})
        if settings.options.get("batch", False):
            payouts = await utils.database.get_objects(models.Payout, settings.ids, postprocess=False)
            wallet_to_payout = defaultdict(list)
            for payout in payouts:
                wallet_to_payout[payout.wallet_id].append(payout)
            for wallet_id, payouts in wallet_to_payout.items():
                try:
                    await payouts_ext.send_batch_payouts(payouts, private_key=wallets.get(wallet_id))
                except Exception as e:
                    logger.error(get_exception_message(e))
                    coros = []
                    for payout in payouts:
                        coros.append(payouts_ext.update_status(payout, payouts_ext.PayoutStatus.FAILED))
                    await asyncio.gather(*coros)
        else:
            for payout_id in settings.ids:
                payout = await utils.database.get_object(models.Payout, payout_id, user, raise_exception=False)
                if not payout:
                    continue
                try:
                    await payouts_ext.send_payout(payout, private_key=wallets.get(payout.wallet_id))
                except Exception as e:
                    logger.error(get_exception_message(e))
                    await payouts_ext.update_status(payout, payouts_ext.PayoutStatus.FAILED)
    await query.gino.status()
    return True


def approve_payouts(orm_model):  # pragma: no cover: tested in regtest
    return orm_model.update.where(orm_model.status == payouts_ext.PayoutStatus.PENDING).values(
        {"status": payouts_ext.PayoutStatus.APPROVED}
    )


def cancel_payouts(orm_model):  # pragma: no cover: tested in regtest
    return orm_model.update.values({"status": payouts_ext.PayoutStatus.CANCELLED})


def send_payouts(orm_model):  # pragma: no cover: tested in regtest
    return orm_model.query
