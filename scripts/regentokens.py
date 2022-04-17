#!/usr/bin/env python3
import json
import sys

import requests
from bs4 import BeautifulSoup

NAMES = {
    "erc20": {"main_filters": {"slug": "ethereum"}},
    "bep20": {"main_filters": {}, "contract_filters": {"contractPlatform": "BNB Smart Chain (BEP20)"}},
    "sep20": {},
}
API_URL = "https://coinmarketcap.com/tokens/views/all"
SMARTBCH_URL = "https://www.marketcap.cash"
SMARTBCH_TOKEN_METADATA = "https://raw.githubusercontent.com/MarketCap-Cash/SmartBCH-Token-List/main/tokens.json"
SMARTBCH_NUMBER_TOKENS = 50  # fetch top 50 tokens by market cap


def exit_err(message):
    print(message)
    sys.exit(1)


def get_next_data(resp):
    soup = BeautifulSoup(resp.text, "html.parser")
    return json.loads(soup.find("script", id="__NEXT_DATA__").text)


def get_token_address(slug, data, filters):
    if not filters:
        return data["token_address"]
    platforms = get_next_data(requests.get(f"https://coinmarketcap.com/currencies/{slug}"))["props"]["initialProps"][
        "pageProps"
    ]["info"]["platforms"]
    for platform in platforms:
        if platform.items() >= filters.items():
            return platform["contractAddress"]


def fetch_popular_tokens(filters):
    page = requests.get(API_URL)
    data = get_next_data(page)
    tokens = data["props"]["initialState"]["cryptocurrency"]["listingLatest"]["data"]
    return {
        token["symbol"]: get_token_address(token["slug"], token["platform"], filters.get("contract_filters", {}))
        for token in tokens
        if "platform" in token and token["platform"].items() >= filters["main_filters"].items()
    }


def fetch_top50_smartbch():
    page = requests.get(SMARTBCH_URL)
    data = get_next_data(page)
    tokens_meta = requests.get(SMARTBCH_TOKEN_METADATA).json()
    initial_tokens = data["props"]["pageProps"]["coins"]
    tokens = sorted(initial_tokens.items(), key=lambda x: x[1]["market_cap"], reverse=True)
    tokens = tokens[1 : SMARTBCH_NUMBER_TOKENS + 1]  # exclude BCH itself
    return {token[0]: tokens_meta[token[0]]["address"] for token in tokens}


if len(sys.argv) != 2:
    exit_err("Usage: regentokens.py <platform>")

platform = sys.argv[1].lower()
if platform not in NAMES:
    exit_err(f"Unsupported platform: {platform}. Supported ones are: {' '.join(NAMES.keys())}")

filters = NAMES[platform]

if platform == "sep20":
    token_symbols = fetch_top50_smartbch()
else:
    token_symbols = fetch_popular_tokens(filters)

for token in token_symbols.copy():
    if not token_symbols[token]:
        token_symbols.pop(token, None)

save_path = f"daemons/tokens/{platform}.json"
print(f"Successfully saved {len(token_symbols)} tokens for {platform.upper()} to {save_path}")

with open(save_path, "w") as f:
    print(json.dumps(token_symbols, sort_keys=True, indent=4), file=f)
