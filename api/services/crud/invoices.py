import asyncio
import contextlib
import secrets
import time
from collections import defaultdict
from collections.abc import Generator
from decimal import Decimal
from operator import attrgetter
from typing import Any, cast

from bitcart import BTC  # type: ignore[attr-defined]
from bitcart.errors import errors
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import insert, select, update
from sqlalchemy.orm import selectinload
from starlette.datastructures import CommaSeparatedStrings

from api import invoices, models, utils
from api.db import AsyncSession
from api.ext import export as export_ext
from api.ext.moneyformat import currency_table, truncate
from api.invoices import InvoiceExceptionStatus, InvoiceStatus
from api.logging import get_exception_message, get_logger
from api.plugins import SKIP_PAYMENT_METHOD
from api.redis import Redis
from api.schemas.invoices import CreateInvoice, MethodUpdateData
from api.schemas.misc import BatchAction
from api.services.coins import CoinService
from api.services.crud import CRUDService
from api.services.crud.products import ProductService
from api.services.crud.repositories import (
    InvoiceRepository,
    PaymentMethodRepository,
    ProductRepository,
    StoreRepository,
    WalletRepository,
)
from api.services.crud.templates import TemplateService
from api.services.ipn_sender import IPNSender
from api.services.notification_manager import NotificationManager
from api.services.payout_manager import PayoutManager
from api.services.plugin_registry import PluginRegistry
from api.services.wallet_data import WalletDataService
from api.types import TasksBroker
from api.utils.routing import SearchPagination

logger = get_logger(__name__)


class InvoiceService(CRUDService[models.Invoice]):
    repository_type = InvoiceRepository

    def __init__(
        self,
        session: AsyncSession,
        payment_method_repository: PaymentMethodRepository,
        store_repository: StoreRepository,
        wallet_repository: WalletRepository,
        product_repository: ProductRepository,
        product_service: ProductService,
        coin_service: CoinService,
        broker: TasksBroker,
        ipn_sender: IPNSender,
        notification_manager: NotificationManager,
        template_service: TemplateService,
        redis_pool: Redis,
        wallet_data_service: WalletDataService,
        plugin_registry: PluginRegistry,
    ) -> None:
        super().__init__(session)
        self.payment_method_repository = payment_method_repository
        self.store_repository = store_repository
        self.wallet_repository = wallet_repository
        self.product_repository = product_repository
        self.product_service = product_service
        self.coin_service = coin_service
        self.broker = broker
        self.ipn_sender = ipn_sender
        self.notification_manager = notification_manager
        self.template_service = template_service
        self.redis_pool = redis_pool
        self.wallet_data_service = wallet_data_service
        self.plugin_registry = plugin_registry

    async def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        data = await super().prepare_data(data)
        await self._process_many_to_many_field(data, "payments", self.payment_method_repository)
        return data

    async def prepare_create(self, data: dict[str, Any], user: models.User | None = None) -> dict[str, Any]:
        data = await super().prepare_create(data, user)
        data["status"] = InvoiceStatus.PENDING
        data["exception_status"] = InvoiceExceptionStatus.NONE
        data["sent_amount"] = Decimal("0")
        return data

    async def set_user_id(self, data: dict[str, Any], model: models.Invoice, user: models.User | None = None) -> str | None:
        store = await self.store_repository.get_one(
            id=data.get("store_id", model.store_id), load=[selectinload(models.Store.wallets)]
        )
        data["user_id"] = store.user_id
        return store.user_id

    async def finalize_create(self, data: dict[str, Any], user: models.User | None = None) -> models.Invoice:
        return await self.create_invoice_flow(data, user)

    @classmethod
    def match_payment(
        self, payments: list[models.PaymentMethod], payment_id: str
    ) -> models.PaymentMethod | None:  # pragma: no cover
        return next((payment for payment in payments if payment.id == payment_id), None)

    @classmethod
    def find_sent_amount_divisibility(
        self, obj_id: str, payments: list[models.PaymentMethod], payment_id: str
    ) -> int | None:  # pragma: no cover
        if not payment_id:
            return None
        method = self.match_payment(payments, payment_id)
        if method:
            return method.divisibility
        logger.error(f"Could not find sent amount divisibility for invoice {obj_id}, payment_id={payment_id}")
        return None

    async def validate(self, data: dict[str, Any], model: models.Invoice, user: models.User | None = None) -> None:
        await super().validate(data, model, user)
        products = data.get("products", {})
        if isinstance(products, list):
            products = dict.fromkeys(products, 1)
        await self.validate_m2m(models.Product, list(products.keys()), data.get("user_id"))

    async def create_invoice_flow(self, data: dict[str, Any], user: models.User | None = None) -> models.Invoice:
        start_time = time.time()
        products = data.pop("products", {})
        if isinstance(products, list):
            products = dict.fromkeys(products, 1)
        store = await self.store_repository.get_one(id=data["store_id"], load=[selectinload(models.Store.wallets)])
        if not store.checkout_settings.allow_anonymous_invoice_creation and not user:
            raise HTTPException(403, "Anonymous invoice creation is disabled")
        if not store.wallets:
            raise HTTPException(422, "No wallet linked")
        data["expiration"] = data["expiration"] or store.checkout_settings.expiration
        data["currency"] = data["currency"] or store.default_currency or "USD"
        promocode = data.get("promocode")
        if products:
            await self.validate_stock_levels(products)
        invoice = models.Invoice(**data)
        for key, value in products.items():
            invoice.products_associations.append(models.ProductxInvoice(invoice_id=invoice.id, product_id=key, count=value))
        invoice = await self.create_base(invoice)
        product = None
        if products:
            product = await self.product_repository.get_one(
                id=list(products.keys())[0], load=[selectinload(models.Product.discounts)]
            )
        current_date = utils.time.now()
        discounts = []
        if product:
            discounts = product.discounts
        discounts = list(filter(lambda x: current_date <= x.end_date, discounts))
        await self.update_invoice_payments(
            invoice, [x.id for x in store.wallets], discounts, store, product, promocode, start_time
        )
        return invoice

    async def update_invoice_payments(
        self,
        invoice: models.Invoice,
        wallets_ids: list[str],
        discounts: list[models.Discount],
        store: models.Store,
        product: models.Product | None,
        promocode: str | None,
        start_time: float,
    ) -> None:
        logger.info(f"Started adding invoice payments for invoice {invoice.id}")
        wallets = await self.wallet_repository.get_ordered_wallets(wallets_ids)
        randomize_selection = store.checkout_settings.randomize_wallet_selection
        if randomize_selection:
            symbols = defaultdict(list)
            for wallet in wallets:
                with contextlib.suppress(Exception):
                    symbol = await self.wallet_data_service.get_wallet_symbol(wallet)
                    symbols[symbol].append(wallet)
            coros = [
                self.create_method_for_wallet(invoice, secrets.choice(symbols[symbol]), discounts, store, product, promocode)
                for symbol in symbols
            ]
        else:
            coros = [
                self.create_method_for_wallet(invoice, wallet, discounts, store, product, promocode) for wallet in wallets
            ]
        db_data = []
        for result in await asyncio.gather(*coros):
            if result is not None:
                for method in result:
                    db_data.append({**method, "created": utils.time.now()})
        if db_data:
            await self.session.execute(insert(models.PaymentMethod), db_data)
            await self.session.refresh(invoice, attribute_names=["payments"])
        creation_time = time.time() - start_time
        logger.info(
            f"Successfully added {len(invoice.payments)} payment methods to invoice {invoice.id} in {creation_time:.2f}s"
        )
        invoice.creation_time = Decimal(creation_time)
        await self.session.flush()

    async def create_payment_method(
        self,
        invoice: models.Invoice,
        wallet: models.Wallet,
        product: models.Product | None,
        store: models.Store,
        discounts: list[models.Discount],
        promocode: str | None,
    ) -> list[dict[str, Any]] | None:
        results = []
        method = await self._create_payment_method(invoice, wallet, product, store, discounts, promocode)
        if method is not SKIP_PAYMENT_METHOD and method is not None:
            results.append(method)
        coin_settings = self.coin_service.get_coin_settings(wallet.currency)
        if coin_settings and coin_settings["lightning"] and wallet.lightning_enabled:  # pragma: no cover
            method = await self._create_payment_method(invoice, wallet, product, store, discounts, promocode, lightning=True)
            if method is not SKIP_PAYMENT_METHOD and method is not None:
                results.append(method)
        return results

    async def create_method_for_wallet(
        self,
        invoice: models.Invoice,
        wallet: models.Wallet,
        discounts: list[models.Discount],
        store: models.Store,
        product: models.Product | None,
        promocode: str | None,
    ) -> list[dict[str, Any]] | None:
        try:
            return await self.create_payment_method(invoice, wallet, product, store, discounts, promocode)
        except Exception as e:
            logger.error(
                f"Invoice {invoice.id}: failed creating payment method {wallet.currency.upper()}:\n{get_exception_message(e)}"
            )
            return None

    async def _create_payment_method(
        self,
        invoice: models.Invoice,
        wallet: models.Wallet,
        product: models.Product | None,
        store: models.Store,
        discounts: list[models.Discount],
        promocode: str | None,
        lightning: bool = False,
    ) -> dict[str, Any] | None:
        data = await self._create_payment_method_core(invoice, wallet, product, store, discounts, promocode, lightning)
        if isinstance(data, dict):
            data["meta"] = data.pop("metadata", {})
        return data

    async def _create_payment_method_core(
        self,
        invoice: models.Invoice,
        wallet: models.Wallet,
        product: models.Product | None,
        store: models.Store,
        discounts: list[models.Discount],
        promocode: str | None,
        lightning: bool = False,
    ) -> dict[str, Any] | None:
        coin = await self.coin_service.get_coin(
            wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract, **wallet.additional_xpub_data}
        )
        method = await self.plugin_registry.apply_filters(
            "pre_create_payment_method", None, coin, invoice, wallet, product, store, discounts, promocode, lightning
        )
        if method is not None:  # pragma: no cover
            return method
        symbol = await self.wallet_data_service.get_wallet_symbol(wallet, coin)
        divisibility = await self.wallet_data_service.get_divisibility(wallet, coin)
        rate = await self.wallet_data_service.get_rate(wallet, invoice.currency, store=store)
        price, discount_id = self.match_discount(invoice.price, wallet, invoice, discounts, promocode)
        support_underpaid = getattr(coin, "support_underpaid", True)
        request_price = (
            price * (1 - (Decimal(store.checkout_settings.underpaid_percentage) / 100)) if support_underpaid else price
        )
        original_request_price = request_price
        request_price = currency_table.normalize(wallet.currency, original_request_price / rate, divisibility=divisibility)
        # adjust the rate to account for the normalization, otherwise clients won't be able to recover the actual sum
        rate = original_request_price / request_price if request_price else rate
        price = currency_table.normalize(wallet.currency, price / rate, divisibility=divisibility)
        if request_price and store.checkout_settings.include_network_fee:  # pragma: no cover
            try:
                network_fee = await self.determine_network_fee(coin, wallet, invoice, store, divisibility)
            except Exception:
                network_fee = Decimal(0)
            request_price += network_fee
            price += network_fee
            request_price = currency_table.normalize(wallet.currency, request_price, divisibility=divisibility)
            price = currency_table.normalize(wallet.currency, price, divisibility=divisibility)
        method = await self.plugin_registry.apply_filters(
            "create_payment_method", None, wallet, coin, request_price, invoice, product, store, lightning
        )
        if method is SKIP_PAYMENT_METHOD:  # pragma: no cover
            return method
        # set defaults
        data: dict[str, Any] = {
            "currency": wallet.currency,
            "metadata": {},
            "rhash": None,
            "node_id": None,
            "recommended_fee": Decimal(0),
            "lightning": lightning,
        }
        if method is not None:  # pragma: no cover
            # Must set payment_address, payment_url, lookup_field
            data.update(method)
        else:
            method = coin.add_request
            if lightning:  # pragma: no cover
                try:
                    await coin.node_id
                    method = coin.add_invoice
                except errors.LightningUnsupportedError:  # type: ignore[misc]
                    return None
            recommended_fee = (
                await coin.server.recommended_fee(store.checkout_settings.recommended_fee_target_blocks)
                if not lightning
                else 0
            )
            recommended_fee = 0 if recommended_fee is None else recommended_fee  # if no rate available, disable it
            data["recommended_fee"] = truncate(Decimal(recommended_fee) / 1024, 2)  # convert to sat/byte, two decimal places
            data_got = await method(request_price, description=product.name if product else "", expire=invoice.expiration)
            data["payment_address"] = data_got["address"] if not lightning else data_got["lightning_invoice"]
            data["payment_url"] = data_got["URI"] if not lightning else data_got["lightning_invoice"]
            if data["payment_url"] is None:
                data["payment_url"] = data["payment_address"]
            data["node_id"] = await coin.node_id if lightning else None
            data["rhash"] = data_got["rhash"] if lightning else None
            data["lookup_field"] = data_got["request_id"] if "request_id" in data_got else data["payment_address"]
        if store.checkout_settings.underpaid_percentage > 0:  # pragma: no cover
            data["payment_url"] = await coin.server.modifypaymenturl(data["payment_url"], price, divisibility)
        return await self.plugin_registry.apply_filters(
            "post_create_payment_method",
            dict(
                id=utils.common.unique_id(),
                invoice_id=invoice.id,
                wallet_id=wallet.id,
                amount=price,
                rate=rate,
                discount=discount_id,
                confirmations=0,
                label=wallet.label,
                hint=wallet.hint,
                contract=wallet.contract,
                symbol=symbol,
                divisibility=divisibility,
                **data,
            ),
            invoice,
            wallet,
            product,
            store,
            discounts,
            promocode,
        )

    @staticmethod
    def match_discount(
        price: Decimal,
        wallet: models.Wallet,
        invoice: models.Invoice,
        discounts: list[models.Discount],
        promocode: str | None,
    ) -> tuple[Decimal, str | None]:
        discount_id = None
        if discounts:
            try:
                discount = max(
                    filter(
                        lambda x: (not x.currencies or wallet.currency in CommaSeparatedStrings(x.currencies))
                        and (promocode == x.promocode or not x.promocode),
                        discounts,
                    ),
                    key=attrgetter("percent"),
                )
                logger.info(f"Payment method {wallet.currency} of invoice {invoice.id}: matched discount {discount.id}")
                discount_id = discount.id
                price -= price * (Decimal(discount.percent) / Decimal(100))
            except ValueError:  # no matched discounts
                pass
        return price, discount_id

    async def determine_network_fee(
        self, coin: BTC, wallet: models.Wallet, invoice: models.Invoice, store: models.Store, divisibility: int
    ) -> Decimal:  # pragma: no cover
        if not coin.is_eth_based:
            return Decimal(await coin.server.get_default_fee(100))  # 100 bytes
        address = await coin.server.getaddress()
        tx = await PayoutManager.prepare_tx(coin, wallet, address, Decimal(0), divisibility)
        fee = Decimal(await coin.server.get_default_fee(tx))
        if wallet.contract:
            coin_no_contract = await self.coin_service.get_coin(
                wallet.currency, {"xpub": wallet.xpub, **wallet.additional_xpub_data}
            )
            # rate from network currency to invoice currency
            rate_no_contract = await self.wallet_data_service.get_rate(wallet, invoice.currency, coin=coin_no_contract)
            # rate from contract currency to invoice currency
            rate_from_base = await self.wallet_data_service.get_rate(wallet, invoice.currency)
            # convert from contract to invoice currency, then back to contract currency
            return (fee * rate_no_contract) / rate_from_base
        return fee

    @staticmethod
    def get_methods_inds(
        methods: list[models.PaymentMethod],
    ) -> Generator[tuple[int | None, models.PaymentMethod]]:
        currencies: dict[str, int] = defaultdict(int)
        met: dict[str, int] = defaultdict(int)
        for item in methods:
            if not item.label and not item.lightning:  # custom label not counted
                currencies[item.symbol] += 1
        for item in methods:
            if not item.label and not item.lightning:
                met[item.symbol] += 1
            index = met[item.symbol] if currencies[item.symbol] > 1 else None
            yield index, item

    async def load_one(self, item: models.Invoice) -> None:
        await super().load_one(item)
        used_payment = next((payment for payment in item.payments if payment.is_used), None)
        item.payment_id = used_payment.id if used_payment else None
        item.refund_id = None

    async def update_confirmations(
        self,
        invoice: models.Invoice,
        method: models.PaymentMethod,
        confirmations: int,
        tx_hashes: list[str] | None = None,
        sent_amount: Decimal = Decimal(0),
    ) -> None:
        if tx_hashes is None:
            tx_hashes = []
        method.update(confirmations=confirmations)
        status = invoice.status
        if confirmations >= 1:
            status = InvoiceStatus.CONFIRMED
        transaction_speed = invoice.store.checkout_settings.transaction_speed
        if confirmations >= transaction_speed:
            status = InvoiceStatus.COMPLETE
        await self.update_status(invoice, status, method, tx_hashes, sent_amount)

    async def update_status(
        self,
        invoice: models.Invoice,
        status: str,
        method: models.PaymentMethod | None = None,
        tx_hashes: list[str] | None = None,
        sent_amount: Decimal = Decimal(0),
        set_exception_status: str | None = None,
    ) -> bool:
        # load it in current session to apply updates
        invoice = await self.merge_object(invoice)
        method = await self.session.merge(method) if method else None
        if tx_hashes is None:
            tx_hashes = []
        if (
            status == InvoiceStatus.PENDING
            and invoice.status == InvoiceStatus.PENDING
            and method
            and sent_amount > 0
            and (not invoice.payment_id or invoice.payment_id == method.id)
        ):
            method.update(is_used=True)
            invoice.update(
                paid_currency=method.get_name(),
                discount=method.discount,
                tx_hashes=tx_hashes,
                sent_amount=sent_amount,
                exception_status=InvoiceExceptionStatus.PAID_PARTIAL,
                payment_id=method.id,
            )
            await self.session.commit()
            await self.process_notifications(invoice)
        if (
            invoice.status != status
            and status != InvoiceStatus.PENDING
            and (invoice.status != InvoiceStatus.COMPLETE or status == InvoiceStatus.REFUNDED)
        ):
            log_text = f"Updating status of invoice {invoice.id}"
            if method:
                full_method_name = method.get_name()
                if (not invoice.payment_id or invoice.payment_id == method.id) and status in [
                    InvoiceStatus.PAID,
                    InvoiceStatus.CONFIRMED,
                    InvoiceStatus.COMPLETE,
                ]:
                    exception_status = (
                        InvoiceExceptionStatus.NONE
                        if sent_amount == method.amount or method.lightning
                        else InvoiceExceptionStatus.PAID_OVER
                    )
                    kwargs: dict[str, Any] = {
                        "paid_currency": full_method_name,
                        "discount": method.discount,
                        "tx_hashes": tx_hashes,
                        "sent_amount": sent_amount,
                        "exception_status": exception_status,
                    }
                    if not invoice.paid_date:
                        kwargs["paid_date"] = utils.time.now()
                    method.update(is_used=True)
                    invoice.update(**kwargs, payment_id=method.id)
                log_text += f" with payment method {full_method_name}"
            logger.info(f"{log_text} to {status}")
            kwargs = {"status": status}
            if set_exception_status:
                kwargs["exception_status"] = set_exception_status
            invoice.update(**kwargs)
            if status == InvoiceStatus.COMPLETE:
                await self.product_service.update_stock_levels(invoice)
            await self.session.commit()
            await self.process_notifications(invoice)
            return True

        return False

    @classmethod
    def prepare_websocket_response(cls, invoice: models.Invoice) -> dict[str, Any]:
        return {
            "status": invoice.status,
            "exception_status": invoice.exception_status,
            "sent_amount": currency_table.format_decimal(
                "",
                cast(Decimal, invoice.sent_amount),
                divisibility=cls.find_sent_amount_divisibility(invoice.id, invoice.payments, cast(str, invoice.payment_id)),
            ),
            "paid_currency": invoice.paid_currency,
            "payment_id": invoice.payment_id,
        }

    async def process_notifications(self, invoice: models.Invoice) -> None:
        await utils.redis.publish_message(self.redis_pool, f"invoice:{invoice.id}", self.prepare_websocket_response(invoice))
        await self.invoice_notification(invoice, invoice.status)

    async def invoice_notification(self, invoice: models.Invoice, status: str) -> None:
        await self.plugin_registry.run_hook("invoice_status", invoice, status)
        await self.ipn_sender.send_invoice_ipn(invoice, status)
        if status == InvoiceStatus.COMPLETE:
            logger.info(f"Invoice {invoice.id} complete, sending notifications...")
            await self.plugin_registry.run_hook("invoice_complete", invoice)
            store = invoice.store
            await self.notification_manager.notify(store, await self.template_service.get_notify_template(store, invoice))
            if invoice.products and (email_obj := utils.email.StoreEmail.get_email(store)).is_enabled():
                messages = []
                products = invoice.products_associations
                for product_relation in products:
                    product = cast(models.Product, product_relation.product)
                    product.price = currency_table.normalize(
                        invoice.currency, product.price
                    )  # to be formatted correctly in emails
                    quantity = product_relation.count
                    product_template = await self.template_service.get_product_template(store, product, quantity)
                    messages.append(product_template)
                    logger.debug(
                        f"Invoice {invoice.id} email notification: rendered product template for product {product.id}:\n"
                        f"{product_template}"
                    )
                store_template = await self.plugin_registry.apply_filters(
                    "email_notification_text",
                    await self.template_service.get_store_template(store, messages),
                    invoice,
                    store,
                    products,
                )
                logger.debug(f"Invoice {invoice.id} email notification: rendered final template:\n{store_template}")
                await self.plugin_registry.run_hook("invoice_email", invoice, store_template)
                email_obj.send_mail(cast(str, invoice.buyer_email), store_template)

    @property
    def supported_batch_actions(self) -> list[str]:
        return super().supported_batch_actions + ["mark_complete", "mark_invalid"]

    async def process_batch_action(self, settings: BatchAction, user: models.User) -> bool:
        if settings.command == "mark_complete":
            for invoice_id in settings.ids:
                invoice = await self.get(invoice_id, user)
                method = invoice.payments[0] if invoice.payments else None
                if not method:
                    continue
                await self.update_status(invoice, invoices.InvoiceStatus.COMPLETE, method)
            return True
        if settings.command == "mark_invalid":
            await self.update_many(
                update(models.Invoice).values({"status": invoices.InvoiceStatus.INVALID}),
                settings.ids,
                user,
            )
            return True
        return await super().process_batch_action(settings, user)

    async def validate_stock_levels(self, products: dict[str, int]) -> None:
        quantities = await self.product_repository.get_quantities(products)
        for product_id, product_name, quantity in quantities:
            if quantity != -1 and quantity < products[product_id]:
                raise HTTPException(
                    422,
                    f"Product {product_name} only has {quantity} items left in stock, requested {products[product_id]}."
                    " Please refresh your page and re-fill your cart from scratch",
                )

    async def get_or_create_invoice_by_order_id(
        self, order_id: str, data: CreateInvoice, user: models.User | None = None
    ) -> models.Invoice:
        item = await self.get_or_none(
            None,
            statement=select(models.Invoice)
            .where(models.Invoice.order_id == order_id)
            .where(models.Invoice.price == data.price)
            .where(models.Invoice.store_id == data.store_id)
            .where(models.Invoice.status != InvoiceStatus.EXPIRED),
        )
        if not item:
            data.order_id = order_id
            item = await self.create(data, user)
        return item

    async def export_invoices(
        self,
        pagination: SearchPagination,
        response: Response,
        export_format: str,
        add_payments: bool,
        all_users: bool,
        user: models.User,
    ) -> Any:
        if all_users and not user.is_superuser:
            raise HTTPException(403, "Not enough permissions")
        # always full list for export
        pagination.limit = -1
        pagination.offset = 0
        query = select(models.Invoice).where(models.Invoice.status == InvoiceStatus.COMPLETE)
        if not all_users:
            query = query.where(models.Invoice.user_id == user.id)
        data, _ = await self.list_and_count(pagination, statement=query)
        export_data = list(export_ext.db_to_json(data, add_payments))
        now = utils.time.now()
        filename = now.strftime(f"bitcart-export-%Y%m%d-%H%M%S.{export_format}")
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        response.headers.update(headers)
        if export_format == "json":
            return export_data
        return StreamingResponse(
            iter([export_ext.json_to_csv(export_data).getvalue()]),
            media_type="application/csv",
            headers=headers,
        )

    async def update_payment_details(self, invoice_id: str, data: MethodUpdateData) -> bool:
        item = await self.get(invoice_id)
        if item.status != InvoiceStatus.PENDING:
            raise HTTPException(422, "Can't update details for paid invoice")
        found_payment: models.PaymentMethod | None = None
        for payment in item.payments:
            if payment.id == data.id:
                found_payment = payment
                break
        if found_payment is None:
            raise HTTPException(404, "No such payment method found")
        if found_payment.user_address is not None:
            raise HTTPException(422, "Can't update payment address once set")
        fetch_data = await self.payment_method_repository.get_info_by_id(found_payment.id)
        if not fetch_data:
            raise HTTPException(404, "No such payment method found")
        method, wallet = fetch_data
        coin = await self.coin_service.get_coin(
            method.currency, {"xpub": wallet.xpub, "contract": method.contract, **wallet.additional_xpub_data}
        )
        try:
            data.address = await coin.server.normalizeaddress(data.address)
        except Exception:
            raise HTTPException(422, "Invalid address") from None
        if not await coin.server.setrequestaddress(method.lookup_field, data.address):
            raise HTTPException(422, "Invalid address")
        await self.plugin_registry.run_hook("invoice_payment_address_set", item, method, data.address)
        method.update(user_address=data.address)
        return True
