import math
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from operator import attrgetter
from typing import Iterable

from bitcart.errors import errors
from fastapi import HTTPException
from sqlalchemy import select
from starlette.datastructures import CommaSeparatedStrings

from api import events, invoices, models, pagination, schemes, settings, utils
from api.crud.products import product_add_related
from api.crud.stores import store_add_related
from api.ext.moneyformat import currency_table, round_up
from api.logger import get_logger

logger = get_logger(__name__)


async def create_invoice(invoice: schemes.CreateInvoice, user: schemes.User):
    logger.info("Started creating invoice")
    logger.debug(invoice)
    d = invoice.dict()
    store = await models.Store.get(d["store_id"])
    if not store:
        raise HTTPException(422, f"Store {d['store_id']} doesn't exist!")
    await store_add_related(store)
    d["currency"] = d["currency"] or store.default_currency or "USD"
    d["expiration"] = store.checkout_settings.expiration
    products = d.get("products", {})
    if isinstance(products, list):
        products = {k: 1 for k in products}
    promocode = d.get("promocode")
    d["products"] = list(products.keys())
    obj, wallets = await models.Invoice.create(**d)
    product = None
    if d["products"]:
        product = await models.Product.get(d["products"][0])
        await product_add_related(product)
    created = []
    for key, value in products.items():  # type: ignore
        created.append((await models.ProductxInvoice.create(invoice_id=obj.id, product_id=key, count=value)).product_id)
    obj.products = created
    obj.payments = []
    current_date = utils.time.now()
    discounts = []
    if product:
        discounts = [await models.Discount.get(discount_id) for discount_id in product.discounts]
    discounts = list(filter(lambda x: current_date <= x.end_date, discounts))
    await update_invoice_payments(obj, wallets, discounts, store, product, promocode)
    add_invoice_expiration(obj)
    return obj


async def _create_payment_method(invoice, wallet, product, store, discounts, promocode, lightning=False):
    coin = settings.get_coin(wallet.currency, wallet.xpub)
    discount_id = None
    rate = await coin.rate(invoice.currency)
    if math.isnan(rate):
        rate = await coin.rate(store.default_currency)
    if math.isnan(rate):
        rate = await coin.rate("USD")
    if math.isnan(rate):
        rate = Decimal(1)  # no rate available, no conversion
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
    request_price = price * ((1 - (Decimal(store.checkout_settings.underpaid_percentage) / 100)))
    request_price = currency_table.normalize(wallet.currency, request_price / rate)
    price = currency_table.normalize(wallet.currency, price / rate)
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
    recommended_fee = round_up(Decimal(recommended_fee) / 1024, 2)  # convert to sat/byte, two decimal places
    data_got = await method(request_price, description=product.name if product else "", expire=invoice.expiration)
    address = data_got["address"] if not lightning else data_got["invoice"]
    url = data_got["URI"] if not lightning else data_got["invoice"]
    node_id = await coin.node_id if lightning else None
    rhash = data_got["rhash"] if lightning else None
    return await models.PaymentMethod.create(
        invoice_id=invoice.id,
        amount=price,
        rate=rate,
        discount=discount_id,
        currency=wallet.currency,
        payment_address=address,
        payment_url=url,
        rhash=rhash,
        lightning=lightning,
        node_id=node_id,
        recommended_fee=recommended_fee,
        confirmations=0,
    )


async def create_payment_method(invoice, wallet, product, store, discounts, promocode):
    method = await _create_payment_method(invoice, wallet, product, store, discounts, promocode)
    coin_settings = settings.crypto_settings.get(wallet.currency.lower())
    if coin_settings and coin_settings["lightning"] and wallet.lightning_enabled:  # pragma: no cover
        await _create_payment_method(invoice, wallet, product, store, discounts, promocode, lightning=True)
    return method


async def update_invoice_payments(invoice, wallets, discounts, store, product, promocode):
    logger.info(f"Started adding invoice payments for invoice {invoice.id}")
    for wallet_id in wallets:
        wallet = await models.Wallet.get(wallet_id)
        await create_payment_method(invoice, wallet, product, store, discounts, promocode)
    await invoice_add_related(invoice)  # add payment methods with correct names and other related objects
    logger.info(f"Successfully added {len(invoice.payments)} payment methods to invoice {invoice.id}")
    await events.event_handler.publish("expired_task", {"id": invoice.id})


def add_invoice_expiration(obj):
    obj.expiration_seconds = obj.expiration * 60
    date = obj.created + timedelta(seconds=obj.expiration_seconds) - utils.time.now()
    obj.time_left = utils.time.time_diff(date)


async def invoice_add_related(item: models.Invoice):
    # add related products
    if not item:
        return
    result = await models.ProductxInvoice.select("product_id").where(models.ProductxInvoice.invoice_id == item.id).gino.all()
    item.products = [product_id for product_id, in result if product_id]
    item.payments = []
    payment_methods = (
        await models.PaymentMethod.query.where(models.PaymentMethod.invoice_id == item.id)
        .order_by(models.PaymentMethod.id)
        .gino.all()
    )
    for index, method in get_methods_inds(payment_methods):
        item.payments.append(await method.to_dict(index))
    add_invoice_expiration(item)


async def invoices_add_related(items: Iterable[models.Invoice]):
    for item in items:
        await invoice_add_related(item)
    return items


async def get_invoice(model_id: int, user: schemes.User, item: models.Invoice, internal: bool = False):
    await invoice_add_related(item)
    return item


async def get_invoices(pagination: pagination.Pagination, user: schemes.User):
    return await pagination.paginate(models.Invoice, user.id, postprocess=invoices_add_related)


async def delete_invoice(item: schemes.Invoice, user: schemes.User):
    await models.ProductxInvoice.delete.where(models.ProductxInvoice.invoice_id == item.id).gino.status()
    await item.delete()
    return item


async def batch_invoice_action(query, settings: schemes.BatchSettings, user: schemes.User):
    if settings.command == "mark_complete":
        for invoice_id in settings.ids:
            data = (
                await select([models.Invoice, models.PaymentMethod])
                .where(models.PaymentMethod.invoice_id == models.Invoice.id)
                .where(models.Invoice.id == invoice_id)
                .order_by(models.PaymentMethod.id)
                .gino.load((models.Invoice, models.PaymentMethod))
                .first()
            )
            if not data:  # pragma: no cover
                continue
            invoice, method = data
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
        if not item.lightning:
            currencies[item.currency] += 1
    for item in methods:
        if not item.lightning:
            met[item.currency] += 1
        index = met[item.currency] if currencies[item.currency] > 1 else None
        yield index, item
