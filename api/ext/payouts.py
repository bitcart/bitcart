import asyncio
from decimal import Decimal

import bitcart
from sqlalchemy import select

from api import invoices, models, settings, utils
from api.ext.moneyformat import currency_table
from api.logger import get_logger
from api.plugins import run_hook
from api.utils.logging import log_errors

logger = get_logger(__name__)

SEND_ALL = Decimal("-1")


class PayoutStatus:
    PENDING = "pending"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    FAILED = "failed"
    SENT = "sent"
    COMPLETE = "complete"


SENT_STATUSES = [PayoutStatus.SENT, PayoutStatus.COMPLETE]


async def update_status(payout, status):
    if payout.status == status or payout.status == PayoutStatus.COMPLETE:
        return
    await payout.update(status=status).apply()
    await utils.notifications.send_ipn(payout, status)
    await run_hook("payout_status", payout, status)
    if status == PayoutStatus.SENT:
        # Refunds: mark invoice as refunded if there's a matching object
        refund = await models.Refund.query.where(models.Refund.payout_id == payout.id).gino.first()
        if refund:
            invoice = await utils.database.get_object(models.Invoice, refund.invoice_id, raise_exception=False)
            if invoice:
                await invoices.update_status(invoice, invoices.InvoiceStatus.REFUNDED)


async def prepare_tx(coin, wallet, destination, amount, divisibility):
    if not coin.is_eth_based:
        if amount == SEND_ALL:
            amount = "!"
        raw_tx = await coin.pay_to(destination, amount, broadcast=False)
    else:
        if wallet.contract:
            if amount == SEND_ALL:
                amount = Decimal(await coin.server.readcontract(wallet.contract, "balanceOf", wallet.xpub)) / Decimal(
                    10**divisibility
                )
            raw_tx = await coin.server.transfer(wallet.contract, destination, amount, unsigned=True)
        else:
            if amount == SEND_ALL:
                request_amount = Decimal((await coin.balance())["confirmed"])
                estimated_fee = Decimal(
                    await coin.server.get_default_fee(await coin.server.payto(destination, amount, unsigned=True))
                )
                request_amount -= estimated_fee
            raw_tx = await coin.server.payto(destination, amount, unsigned=True)
    return raw_tx


async def prepare_payout_details(payout, private_key=None):
    wallet = await utils.database.get_object(models.Wallet, payout.wallet_id, raise_exception=False)
    store = await utils.database.get_object(models.Store, payout.store_id, raise_exception=False)
    if not wallet or not store or payout.status in SENT_STATUSES:
        return
    coin = await settings.settings.get_coin(
        wallet.currency,
        {"xpub": private_key or wallet.xpub, "contract": wallet.contract, "diskless": True, **wallet.additional_xpub_data},
    )
    try:
        divisibility = await utils.wallets.get_divisibility(wallet, coin)
        rate = await utils.wallets.get_rate(wallet, payout.currency)
        request_amount = (
            currency_table.normalize(wallet.currency, payout.amount / rate, divisibility=divisibility)
            if payout.amount != SEND_ALL
            else SEND_ALL
        )
        return coin, wallet, payout.destination, request_amount, rate, divisibility
    except Exception:
        await coin.server.close_wallet()
        raise


async def mark_payout_sent(payout, tx_hash):
    await payout.update(tx_hash=tx_hash).apply()
    await update_status(payout, PayoutStatus.SENT)


async def send_payout(payout, private_key=None):
    result = await prepare_payout_details(payout, private_key)
    if result is None:
        return
    coin, wallet, destination, request_amount, rate, divisibility = result
    try:
        raw_tx = await prepare_tx(coin, wallet, destination, request_amount, divisibility)
        tx_hash = await broadcast_tx_flow(coin, wallet, raw_tx, payout.max_fee, divisibility, rate)
        if tx_hash is not None:
            await mark_payout_sent(payout, tx_hash)
    except Exception:
        await coin.server.close_wallet()
        raise


async def broadcast_tx_flow(coin, wallet, raw_tx, max_fee, divisibility, rate):
    try:
        predicted_fee = Decimal(await coin.server.get_default_fee(raw_tx))
        if max_fee is not None:
            max_fee_amount = currency_table.normalize(wallet.currency, max_fee / rate, divisibility=divisibility)
            if predicted_fee > max_fee_amount:
                return
        if coin.is_eth_based:
            raw_tx = await coin.server.signtransaction(raw_tx)
        else:
            await coin.server.addtransaction(raw_tx)
        return await coin.server.broadcast(raw_tx)
    finally:
        await coin.server.close_wallet()


async def send_batch_payouts(payouts, private_key=None):
    coros = [prepare_payout_details(payout, private_key) for payout in payouts]
    results = await asyncio.gather(*coros)
    if results[0] is None:
        return
    coin, wallet, divisibility, rate = results[0][0], results[0][1], results[0][5], results[0][4]
    outputs = [(result[2], result[3]) for result in results]
    if any(output[1] == SEND_ALL for output in outputs):
        raise Exception("Cannot send batch payout with SEND_ALL")
    try:
        raw_tx = await coin.pay_to_many(outputs, broadcast=False)
        max_fee = None
        if any(payout.max_fee is not None for payout in payouts):
            max_fee = min(payout.max_fee for payout in payouts)
        tx_hash = await broadcast_tx_flow(coin, wallet, raw_tx, max_fee, divisibility, rate)
        if tx_hash is not None:
            coros = [mark_payout_sent(payout, tx_hash) for payout in payouts]
            await asyncio.gather(*coros)
    finally:
        await coin.server.close_wallet()


async def process_new_block(currency):
    payouts = (
        await select([models.Payout, models.Wallet])
        .where(models.Payout.status == PayoutStatus.SENT)
        .where(models.Wallet.id == models.Payout.wallet_id)
        .where(models.Wallet.currency == currency)
        .gino.load((models.Payout, models.Wallet))
        .all()
    )
    coros = []
    for payout, wallet in payouts:
        with log_errors():
            coin = await settings.settings.get_coin(
                currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
            )
            try:
                confirmations = (await coin.get_tx(payout.tx_hash))["confirmations"]
            except bitcart.errors.TxNotFoundError:
                continue
            if confirmations >= 1:
                coros.append(finalize_payout(coin, payout))
    await asyncio.gather(*coros)


async def finalize_payout(coin, payout):
    used_fee = await coin.server.get_used_fee(payout.tx_hash)
    await payout.update(used_fee=used_fee).apply()
    await update_status(payout, PayoutStatus.COMPLETE)
