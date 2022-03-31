#!/usr/bin/env python3
import json
import sys

import requests
from bs4 import BeautifulSoup

NAMES = {"erc20": "ethereum"}
API_URL = "https://coinmarketcap.com/tokens/views/all"


def exit_err(message):
    print(message)
    sys.exit(1)


def fetch_popular_tokens(slug):
    page = requests.get(API_URL)
    soup = BeautifulSoup(page.text, "html.parser")
    data = json.loads(soup.find("script", id="__NEXT_DATA__").text)
    tokens = data["props"]["initialState"]["cryptocurrency"]["listingLatest"]["data"]
    return {
        token["symbol"]: token["platform"]["token_address"]
        for token in tokens
        if "platform" in token and token["platform"]["slug"] == slug
    }


if len(sys.argv) != 2:
    exit_err("Usage: regentokens.py <platform>")

platform = sys.argv[1].lower()
if platform not in NAMES:
    exit_err(f"Unsupported platform: {platform}. Supported ones are: {' '.join(NAMES.keys())}")

slug = NAMES[platform]
token_symbols = fetch_popular_tokens(slug)
save_path = f"daemons/tokens/{platform}.json"
print(f"Successfully saved {len(token_symbols)} tokens for {platform.upper()} to {save_path}")

with open(save_path, "w") as f:
    print(json.dumps(token_symbols, sort_keys=True, indent=4), file=f)
