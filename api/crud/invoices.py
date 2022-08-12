from collections import defaultdict
from decimal import Decimal
from operator import attrgetter

from bitcart.errors import errors
from fastapi import HTTPException
from sqlalchemy import select
from starlette.datastructures import CommaSeparatedStrings

from api import events, invoices, models, schemes, settings, utils
from api.ext.moneyformat import currency_table, truncate
from api.logger import get_exception_message, get_logger
from api.utils.database import safe_db_write

logger = get_logger(__name__)


async def create_invoice(invoice: schemes.CreateInvoice, user: schemes.User):
    logger.info("Started creating invoice")
    logger.debug(invoice)
    d = invoice.dict()
    store = await utils.database.get_object(models.Store, d["store_id"], user)
    if not store.wallets:
        raise HTTPException(422, "No wallet linked")
    d["currency"] = d["currency"] or store.default_currency or "USD"
    d["expiration"] = store.checkout_settings.expiration
    products = d.pop("products", {})
    if isinstance(products, list):
        products = {k: 1 for k in products}
    promocode = d.get("promocode")
    d["user_id"] = store.user_id
    # Launch products access validation
    # TODO: handle it better
    await models.Invoice(**d).validate({**d, "products": list(products.keys())})
    obj = await utils.database.create_object(models.Invoice, d)
    product = None
    if products:
        product = await utils.database.get_object(models.Product, list(products.keys())[0])
    created = []
    with safe_db_write():
        for key, value in products.items():
            created.append((await models.ProductxInvoice.create(invoice_id=obj.id, product_id=key, count=value)).product_id)
    obj.products = created
    obj.payments = []
    current_date = utils.time.now()
    discounts = []
    if product:
        discounts = await utils.database.get_objects(models.Discount, product.discounts)
    discounts = list(filter(lambda x: current_date <= x.end_date, discounts))
    with safe_db_write():
        await update_invoice_payments(obj, store.wallets, discounts, store, product, promocode)
    return obj


async def _create_payment_method(invoice, wallet, product, store, discounts, promocode, lightning=False):
    coin = settings.settings.get_coin(wallet.currency, {"xpub": wallet.xpub, "contract": wallet.contract})
    discount_id = None
    symbol = await coin.server.readcontract(wallet.contract, "symbol") if wallet.contract else wallet.currency
    divisibility = await utils.wallets.get_divisibility(wallet, coin)
    rate = await utils.wallets.get_rate(wallet, invoice.currency, store.default_currency)
    price = invoice.price
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
    request_price = price * (1 - (Decimal(store.checkout_settings.underpaid_percentage) / 100))
    request_price = currency_table.normalize(wallet.currency, request_price / rate, divisibility=divisibility)
    method = coin.add_request
    if lightning:  # pragma: no cover
        try:
            await coin.node_id  # check if works
            method = coin.add_invoice
        except errors.LightningUnsupportedError:
            return
    recommended_fee = (
        await coin.server.recommended_fee(store.checkout_settings.recommended_fee_target_blocks) if not lightning else 0
    )
    recommended_fee = 0 if recommended_fee is None else recommended_fee  # if no rate available, disable it
    recommended_fee = truncate(Decimal(recommended_fee) / 1024, 2)  # convert to sat/byte, two decimal places
    data_got = await method(request_price, description=product.name if product else "", expire=invoice.expiration)
    address = data_got["address"] if not lightning else data_got["lightning_invoice"]
    url = data_got["URI"] if not lightning else data_got["lightning_invoice"]
    node_id = await coin.node_id if lightning else None
    rhash = data_got["rhash"] if lightning else None
    # amount_wei is a way to identify eth-based chains
    lookup_field = data_got["id"] if "amount_wei" in data_got else (rhash if lightning else address)
    return await models.PaymentMethod.create(
        id=utils.common.unique_id(),
        invoice_id=invoice.id,
        amount=data_got[coin.amount_field],
        rate=rate,
        discount=discount_id,
        currency=wallet.currency,
        payment_address=address,
        payment_url=url,
        lookup_field=lookup_field,
        rhash=rhash,
        lightning=lightning,
        node_id=node_id,
        recommended_fee=recommended_fee,
        confirmations=0,
        label=wallet.label,
        hint=wallet.hint,
        created=utils.time.now(),
        contract=wallet.contract,
        symbol=symbol,
        divisibility=divisibility,
    )


async def create_payment_method(invoice, wallet, product, store, discounts, promocode):
    method = await _create_payment_method(invoice, wallet, product, store, discounts, promocode)
    coin_settings = settings.settings.crypto_settings.get(wallet.currency.lower())
    if coin_settings and coin_settings["lightning"] and wallet.lightning_enabled:  # pragma: no cover
        await _create_payment_method(invoice, wallet, product, store, discounts, promocode, lightning=True)
    return method


async def update_invoice_payments(invoice, wallets, discounts, store, product, promocode):
    logger.info(f"Started adding invoice payments for invoice {invoice.id}")
    for wallet_id in wallets:
        wallet = await models.Wallet.get(wallet_id)
        try:
            await create_payment_method(invoice, wallet, product, store, discounts, promocode)
        except Exception as e:
            logger.error(
                f"Invoice {invoice.id}: failed creating payment method {wallet.currency.upper()}:\n{get_exception_message(e)}"
            )
    await invoice.load_data()  # add payment methods with correct names and other related objects
    logger.info(f"Successfully added {len(invoice.payments)} payment methods to invoice {invoice.id}")
    await events.event_handler.publish("expired_task", {"id": invoice.id})


async def batch_invoice_action(query, settings: schemes.BatchSettings, user: schemes.User):
    if settings.command == "mark_complete":
        for invoice_id in settings.ids:
            data = (
                await select([models.Invoice, models.PaymentMethod])
                .where(models.PaymentMethod.invoice_id == models.Invoice.id)
                .where(models.Invoice.id == invoice_id)
                .where(models.Invoice.user_id == user.id)
                .order_by(models.PaymentMethod.created)
                .gino.load((models.Invoice, models.PaymentMethod))
                .first()
            )
            if not data:
                continue
            invoice, method = data
            await invoice.load_data()
            await invoices.update_status(invoice, invoices.InvoiceStatus.COMPLETE, method)
    else:
        await query.gino.status()
    return True


def mark_invoice_complete(orm_model):
    return orm_model.query


def mark_invoice_invalid(orm_model):
    return orm_model.update.values({"status": invoices.InvoiceStatus.INVALID})


def get_methods_inds(methods: list):
    currencies = defaultdict(int)
    met = defaultdict(int)
    for item in methods:
        if not item.label and not item.lightning:  # custom label not counted
            currencies[item.symbol] += 1
    for item in methods:
        if not item.lightning:
            met[item.symbol] += 1
        index = met[item.symbol] if currencies[item.symbol] > 1 else None
        yield index, item
