#!/usr/bin/env python3
import json
import sys
from typing import Any, cast

import requests
from bs4 import BeautifulSoup, Tag

NAMES = {
    "erc20": {"main_filters": {"platform.slug": "ethereum"}},
    "bep20": {"main_filters": {}, "contract_filters": {"contractPlatform": "BNB Smart Chain (BEP20)"}},
    "erc20matic": {"main_filters": {}, "contract_filters": {"contractPlatform": "Polygon"}},
    "trc20": {"main_filters": {}, "contract_filters": {"contractPlatform": "Tron20"}},
    "cashtokens": {},
}
API_URL = "https://coinmarketcap.com/tokens/views/all"
CASHTOKENS_URL = "https://cashtokenmarkets.bch-1.org"


def exit_err(message: str) -> None:
    print(message)
    sys.exit(1)


def get_next_data(resp: requests.Response) -> dict[str, Any]:
    soup = BeautifulSoup(resp.text, "html.parser")
    return json.loads(cast(Tag, soup.find("script", id="__NEXT_DATA__")).text)


def get_token_address(slug: str, data: dict[str, Any], filters: dict[str, Any]) -> str | None:
    if not filters:
        return data["platform.token_address"]
    platforms = get_next_data(requests.get(f"https://coinmarketcap.com/currencies/{slug}"))["props"]["pageProps"]["detailRes"][
        "detail"
    ]["platforms"]
    for platform in platforms:
        if platform.items() >= filters.items():
            return platform["contractAddress"]
    return None


def fetch_popular_tokens(filters: dict[str, Any]) -> dict[str, str | None]:
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


def fetch_cashtokens() -> dict[str, str | None]:  # noqa: C901
    page = requests.get(CASHTOKENS_URL)
    soup = BeautifulSoup(page.text, "html.parser")
    script_tags = soup.find_all("script")
    initial_tokens_data = None
    for script in script_tags:
        if "initialTokens" in script.text:
            script_text = script.text
            start_idx = script_text.find("self.__next_f.push([")
            if start_idx == -1:
                continue
            json_start = script_text.find(',"', start_idx)
            if json_start == -1:
                continue
            json_start += 2
            json_end = script_text.find('"])', json_start)
            if json_end == -1:
                continue
            json_str = script_text[json_start:json_end]
            try:
                unescaped = json.loads(f'"{json_str}"')
                tokens_start = unescaped.find('"initialTokens":[')
                if tokens_start == -1:
                    continue
                tokens_start = unescaped.find(":[", tokens_start) + 1
                bracket_count = 0
                in_string = False
                escape_next = False
                tokens_end = tokens_start
                for i in range(tokens_start, len(unescaped)):
                    char = unescaped[i]
                    if escape_next:
                        escape_next = False
                        continue
                    if char == "\\":
                        escape_next = True
                        continue
                    if char == '"':
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == "[":
                            bracket_count += 1
                        elif char == "]":
                            bracket_count -= 1
                            if bracket_count == 0:
                                tokens_end = i + 1
                                break
                initial_tokens_data = json.loads(unescaped[tokens_start:tokens_end])
                break
            except (json.JSONDecodeError, ValueError):
                continue
    if not initial_tokens_data:
        raise Exception("Could not find initialTokens data in the page")
    filtered_tokens = []
    for token in initial_tokens_data:
        symbol = token.get("symbol")
        category_id = token.get("categoryId")
        if not symbol or not category_id:
            continue
        if not symbol.isascii() or not all(c.isalnum() or c in "_-" for c in symbol):
            continue
        filtered_tokens.append(token)

    def get_market_cap(token: dict[str, Any]) -> float:
        try:
            analytics = token.get("analytics", {})
            market_cap_str = analytics.get("marketCap")
            if market_cap_str:
                return float(market_cap_str.replace("$", "").replace(",", ""))
            return 0
        except (ValueError, TypeError, AttributeError):
            return 0

    sorted_tokens = sorted(filtered_tokens, key=get_market_cap, reverse=True)
    result: dict[str, str | None] = {}
    for token in sorted_tokens[:20]:
        symbol = token.get("symbol")
        category_id = token.get("categoryId")
        if symbol and category_id:
            result[symbol] = category_id
    return result


if len(sys.argv) != 2:
    exit_err("Usage: regentokens.py <platform>")

platform = sys.argv[1].lower()
if platform not in NAMES:
    exit_err(f"Unsupported platform: {platform}. Supported ones are: {' '.join(NAMES.keys())}")

if platform == "cashtokens":
    token_symbols = fetch_cashtokens()
else:
    filters = NAMES[platform]
    token_symbols = fetch_popular_tokens(filters)

for token in token_symbols.copy():
    if not token_symbols[token]:
        token_symbols.pop(token, None)

save_path = f"daemons/tokens/{platform}.json"
print(f"Successfully saved {len(token_symbols)} tokens for {platform.upper()} to {save_path}")

with open(save_path, "w") as f:
    print(json.dumps(token_symbols, sort_keys=True, indent=4), file=f)
