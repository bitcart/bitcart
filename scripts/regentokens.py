#!/usr/bin/env python3
import json
import sys

import requests
from bs4 import BeautifulSoup

NAMES = {
    "erc20": {"main_filters": {"platform.slug": "ethereum"}},
    "bep20": {"main_filters": {}, "contract_filters": {"contractPlatform": "BNB Smart Chain (BEP20)"}},
    "erc20matic": {"main_filters": {}, "contract_filters": {"contractPlatform": "Polygon"}},
    "trc20": {"main_filters": {}, "contract_filters": {"contractPlatform": "Tron20"}},
}
API_URL = "https://coinmarketcap.com/tokens/views/all"


def exit_err(message):
    print(message)
    sys.exit(1)


def get_next_data(resp):
    soup = BeautifulSoup(resp.text, "html.parser")
    return json.loads(soup.find("script", id="__NEXT_DATA__").text)


def get_token_address(slug, data, filters):
    if not filters:
        return data["platform.token_address"]
    platforms = get_next_data(requests.get(f"https://coinmarketcap.com/currencies/{slug}"))["props"]["pageProps"]["detailRes"][
        "detail"
    ]["platforms"]
    for platform in platforms:
        if platform.items() >= filters.items():
            return platform["contractAddress"]


def fetch_popular_tokens(filters):
    page = requests.get(API_URL)
    data = get_next_data(page)
    tokens = json.loads(data["props"]["initialState"])["cryptocurrency"]["listingLatest"]["data"]
    keys = tokens[0]["keysArr"]
    for idx in range(1, len(tokens)):
        tokens[idx] = {key: tokens[idx][key_idx] for key_idx, key in enumerate(keys)}
    return {
        token["symbol"]: get_token_address(token["slug"], token, filters.get("contract_filters", {}))
        for token in tokens
        if "keysArr" not in token and token.items() >= filters["main_filters"].items()
    }


if len(sys.argv) != 2:
    exit_err("Usage: regentokens.py <platform>")

platform = sys.argv[1].lower()
if platform not in NAMES:
    exit_err(f"Unsupported platform: {platform}. Supported ones are: {' '.join(NAMES.keys())}")

filters = NAMES[platform]

token_symbols = fetch_popular_tokens(filters)

for token in token_symbols.copy():
    if not token_symbols[token]:
        token_symbols.pop(token, None)

save_path = f"daemons/tokens/{platform}.json"
print(f"Successfully saved {len(token_symbols)} tokens for {platform.upper()} to {save_path}")

with open(save_path, "w") as f:
    print(json.dumps(token_symbols, sort_keys=True, indent=4), file=f)
