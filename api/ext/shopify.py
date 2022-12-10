import json
import os
from base64 import b64encode

from aiohttp import ClientSession

from api import invoices, models, utils
from api.exceptions import BitcartError
from api.ext.moneyformat import currency_table

SHOPIFY_ORDER_PREFIX = "shopify-"
SHOPIFY_KEYWORDS = ["bitcoin", "btc", "bitcartcc", "bitcart"]


class ShopifyAPIError(BitcartError):
    """Error accessing shopify API"""


class ShopifyClient:
    def __init__(self, shop_name, api_key, api_secret):
        self.api_url = shop_name if "." in shop_name else f"https://{shop_name}.myshopify.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.auth_header = b64encode(f"{api_key}:{api_secret}".encode()).decode()
        self.headers = {"Authorization": f"Basic {self.auth_header}"}

    async def request(self, method, url, **kwargs):
        final_url = os.path.join(self.api_url, "admin/api/2022-04/" + url)
        async with ClientSession(headers=self.headers) as session:
            async with session.request(method, final_url, **kwargs) as response:
                data = await response.text()
                if "invalid api key or access token" in data.lower():
                    raise ShopifyAPIError("Invalid API key or access token")
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    raise ShopifyAPIError("Invalid JSON data")
                return data

    async def get_order(self, order_id):
        return (
            await self.request(
                "GET",
                (
                    f"orders/{order_id}.json?fields=id,total_price,total_outstanding,currency"
                    ",presentment_currency,transactions,financial_status"
                ),
            )
        ).get("order", {})

    async def order_exists(self, order_id):
        data = await self.request("GET", f"orders/{order_id}.json?fields=id")
        return data.get("order") is not None

    async def list_transactions(self, order_id):
        return await self.request("GET", f"orders/{order_id}/transactions.json")

    async def create_transaction(self, order_id, data):
        return await self.request("POST", f"orders/{order_id}/transactions.json", json=data)


def get_shopify_client(store):
    shopify_settings = store.plugin_settings.shopify
    return ShopifyClient(shopify_settings.shop_name, shopify_settings.api_key, shopify_settings.api_secret)


async def shopify_invoice_update(event, event_data):
    invoice = await utils.database.get_object(models.Invoice, event_data["id"], raise_exception=False)
    if not invoice:
        return
    order_id = invoice.order_id
    if not order_id.startswith(SHOPIFY_ORDER_PREFIX):
        return
    order_id = order_id[len(SHOPIFY_ORDER_PREFIX) :]
    store = await utils.database.get_object(models.Store, invoice.store_id, raise_exception=False)
    if not store:
        return
    client = get_shopify_client(store)
    if not await client.order_exists(order_id):
        return
    if invoice.status in invoices.FAILED_STATUSES or invoice.status in invoices.PAID_STATUSES:
        success = invoice.status in invoices.PAID_STATUSES
        await update_shopify_status(client, order_id, invoice.id, invoice.currency, invoice.price, success)


async def update_shopify_status(client, order_id, invoice_id, currency, amount, success):
    currency = currency.upper()
    transactions = (await client.list_transactions(order_id)).get("transactions", [])
    base_tx = None
    for transaction in transactions:
        if any(x in transaction["gateway"].lower() for x in SHOPIFY_KEYWORDS):
            base_tx = transaction
            break
    if base_tx is None:
        return
    if currency != base_tx["currency"].upper():
        return
    kind = "capture"
    parent_id = base_tx["id"]
    status = "success" if success else "failure"
    txes_on_same_invoice = [tx for tx in transactions if tx["authorization"] == invoice_id]
    successful_txes = [tx for tx in txes_on_same_invoice if tx["status"] == "success"]
    successful_captures = [tx for tx in successful_txes if tx["kind"] == "capture"]
    refunds = [tx for tx in txes_on_same_invoice if tx["kind"] == "refund"]
    # if we are working with a non-success registration, but see that we have previously registered this invoice as a success,
    # we switch to creating a "void" transaction, which in shopify terms is a refund.
    if not success and len(successful_captures) > 0 and len(successful_captures) - len(refunds) > 0:
        kind = "void"
        parent_id = successful_captures[-1]["id"]
        status = "success"
    # if we are working with a success registration, but can see that we have already had a successful transaction saved, exit
    elif success and len(successful_captures) > 0 and len(successful_captures) - len(refunds) > 0:
        return
    await client.create_transaction(
        order_id,
        {
            "transaction": {
                "parent_id": parent_id,
                "currency": currency,
                "amount": currency_table.format_decimal(currency, amount),
                "kind": kind,
                "gateway": "BitcartCC",
                "source": "external",
                "authorization": invoice_id,
                "status": status,
            }
        },
    )
