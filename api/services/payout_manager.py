import asyncio
from decimal import Decimal
from typing import cast

import bitcart
from bitcart import BTC  # type: ignore[attr-defined]
from dishka import AsyncContainer, Scope
from sqlalchemy import select

from api import models
from api.constants import SENT_PAYOUT_STATUSES, PayoutStatus
from api.db import AsyncSession
from api.ext.moneyformat import currency_table
from api.logging import get_logger, log_errors
from api.services.coins import CoinService
from api.services.ipn_sender import IPNSender
from api.services.plugin_registry import PluginRegistry
from api.services.wallet_data import WalletDataService
from api.types import PayoutAmount

logger = get_logger(__name__)

SEND_ALL = Decimal("-1")


class PayoutManager:
    def __init__(
        self,
        ipn_sender: IPNSender,
        coin_service: CoinService,
        wallet_data_service: WalletDataService,
        plugin_registry: PluginRegistry,
        container: AsyncContainer,
    ) -> None:
        self.ipn_sender = ipn_sender
        self.coin_service = coin_service
        self.wallet_data_service = wallet_data_service
        self.plugin_registry = plugin_registry
        self.container = container

    async def update_status(self, payout: models.Payout, status: str) -> None:
        from api.services.crud.refunds import RefundService

        if payout.status == status or payout.status == PayoutStatus.COMPLETE:
            return
        payout.update(status=status)
        async with self.container(scope=Scope.REQUEST) as container:
            session = await container.get(AsyncSession)
            payout = await session.merge(payout)
        await self.ipn_sender.send_invoice_ipn(payout, status)
        await self.plugin_registry.run_hook("payout_status", payout, status)
        if status == PayoutStatus.SENT:
            async with self.container(scope=Scope.REQUEST) as container:
                refund_service = await container.get(RefundService)
                await refund_service.process_sent_payout(payout)

    @classmethod
    async def prepare_tx(
        cls, coin: BTC, wallet: models.Wallet, destination: str, amount: PayoutAmount, divisibility: int
    ) -> str:
        if not coin.is_eth_based:
            if amount == SEND_ALL:
                amount = "!"
            raw_tx = await coin.pay_to(destination, amount, broadcast=False)
        else:
            if wallet.contract:
                if amount == SEND_ALL:
                    address = await coin.server.getaddress()
                    amount = Decimal(await coin.server.readcontract(wallet.contract, "balanceOf", address)) / Decimal(
                        10**divisibility
                    )
                raw_tx = await coin.server.transfer(wallet.contract, destination, amount, unsigned=True)
            else:
                if amount == SEND_ALL:
                    amount = Decimal((await coin.balance())["confirmed"])
                    estimated_fee = Decimal(
                        await coin.server.get_default_fee(await coin.server.payto(destination, amount, unsigned=True))
                    )
                    amount -= estimated_fee
                raw_tx = await coin.server.payto(destination, amount, unsigned=True)
        return cast(str, raw_tx)

    async def prepare_payout_details(
        self, payout: models.Payout, private_key: str | None = None
    ) -> tuple[BTC, models.Wallet, str, PayoutAmount, Decimal, int] | None:
        wallet = payout.wallet
        store = payout.store
        if not wallet or not store or payout.status in SENT_PAYOUT_STATUSES:
            return None
        coin = await self.coin_service.get_coin(
            wallet.currency,
            {"xpub": private_key or wallet.xpub, "contract": wallet.contract, "diskless": True, **wallet.additional_xpub_data},
        )
        try:
            divisibility = await self.wallet_data_service.get_divisibility(wallet, coin)
            rate = await self.wallet_data_service.get_rate(wallet, payout.currency)
            request_amount = (
                currency_table.normalize(wallet.currency, payout.amount / rate, divisibility=divisibility)
                if payout.amount != SEND_ALL
                else SEND_ALL
            )
            return coin, wallet, payout.destination, request_amount, rate, divisibility
        except Exception:
            await coin.server.close_wallet()
            raise

    async def mark_payout_sent(self, payout: models.Payout, tx_hash: str) -> None:
        payout.update(tx_hash=tx_hash)
        await self.update_status(payout, PayoutStatus.SENT)

    async def send_payout(self, payout: models.Payout, private_key: str | None = None) -> None:
        result = await self.prepare_payout_details(payout, private_key)
        if result is None:
            return
        coin, wallet, destination, request_amount, rate, divisibility = result
        try:
            raw_tx = await self.prepare_tx(coin, wallet, destination, request_amount, divisibility)
            tx_hash = await self.broadcast_tx_flow(coin, wallet, raw_tx, payout.max_fee, divisibility, rate)
            if tx_hash is not None:
                await self.mark_payout_sent(payout, tx_hash)
        except Exception:
            await coin.server.close_wallet()
            raise

    async def broadcast_tx_flow(
        self, coin: BTC, wallet: models.Wallet, raw_tx: str, max_fee: Decimal | None, divisibility: int, rate: Decimal
    ) -> str | None:
        try:
            predicted_fee = Decimal(await coin.server.get_default_fee(raw_tx))
            if max_fee is not None:
                max_fee_amount = currency_table.normalize(wallet.currency, max_fee / rate, divisibility=divisibility)
                if predicted_fee > max_fee_amount:
                    return None
            if coin.is_eth_based:
                raw_tx = await coin.server.signtransaction(raw_tx)
            else:
                await coin.server.addtransaction(raw_tx)
            return await coin.server.broadcast(raw_tx)
        finally:
            await coin.server.close_wallet()

    async def finalize_payout(self, coin: BTC, payout: models.Payout) -> None:
        used_fee = await coin.server.get_used_fee(payout.tx_hash)
        payout.update(used_fee=used_fee)
        await self.update_status(payout, PayoutStatus.COMPLETE)

    async def send_batch_payouts(self, payouts: list[models.Payout], private_key: str | None = None) -> None:
        coros = [self.prepare_payout_details(payout, private_key) for payout in payouts]
        results = await asyncio.gather(*coros)  # TODO: Fix concurrency
        if results[0] is None:
            return
        coin, wallet, divisibility, rate = results[0][0], results[0][1], results[0][5], results[0][4]
        outputs = [(result[2], result[3]) for result in results if result is not None]
        if any(output[1] == SEND_ALL for output in outputs):
            raise Exception("Cannot send batch payout with SEND_ALL")
        try:
            raw_tx = await coin.pay_to_many(outputs, broadcast=False)
            max_fee = None
            if any(payout.max_fee is not None for payout in payouts):
                max_fee = min(payout.max_fee for payout in payouts if payout.max_fee is not None)
            tx_hash = await self.broadcast_tx_flow(coin, wallet, cast(str, raw_tx), max_fee, divisibility, rate)
            if tx_hash is not None:
                coros = [self.mark_payout_sent(payout, tx_hash) for payout in payouts]
                await asyncio.gather(*coros)  # TODO: Fix concurrency
        finally:
            await coin.server.close_wallet()

    async def process_new_block(self, currency: str) -> None:
        async with self.container(scope=Scope.REQUEST) as container:
            session = await container.get(AsyncSession)
            payouts = (
                await session.execute(
                    select(models.Payout, models.Wallet)
                    .where(models.Payout.status == PayoutStatus.SENT)
                    .where(models.Wallet.id == models.Payout.wallet_id)
                    .where(models.Wallet.currency == currency)
                )
            ).all()
        coros = []
        for payout, wallet in payouts:
            with log_errors(logger):
                coin = await self.coin_service.get_coin(
                    currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
                )
                try:
                    confirmations = (await coin.get_tx(payout.tx_hash))["confirmations"]
                except bitcart.errors.TxNotFoundError:  # type: ignore
                    continue
                if confirmations >= 1:
                    coros.append(self.finalize_payout(coin, payout))
        await asyncio.gather(*coros)  # TODO: Fix concurrency
