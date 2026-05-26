from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

DAEMONS_PATH = Path(__file__).resolve().parents[1] / "daemons"
sys.path.insert(0, str(DAEMONS_PATH))
sui = importlib.import_module("sui")

SUI_COIN_TYPE = sui.SUI_COIN_TYPE
SUIFeatures = sui.SUIFeatures

VALID_SUI_ADDRESS = "0x" + "a" * 64
SENDER_ADDRESS = "0x" + "b" * 64


def parse_transactions(tx_data: dict) -> list:
    return asyncio.run(SUIFeatures(None).parse_transactions(tx_data))


def build_balance_change(address: str, coin_type: str, amount: str) -> dict:
    return {
        "owner": {"AddressOwner": address},
        "coinType": coin_type,
        "amount": amount,
    }


def build_transaction(status: str, balance_changes: list[dict], digest: str = "digest") -> dict:
    return {
        "digest": digest,
        "transaction": {"data": {"sender": SENDER_ADDRESS}},
        "effects": {"status": {"status": status}},
        "balanceChanges": balance_changes,
    }


def test_sui_address_normalization_pads_and_lowercases() -> None:
    features = SUIFeatures(None)

    assert features.normalize_address("0xA") == "0x" + "0" * 63 + "a"
    assert features.is_address(VALID_SUI_ADDRESS)
    assert not features.is_address("0x1234")
    assert not features.is_address("not-an-address")


def test_process_tx_data_extracts_native_sui_recipient_balance_change() -> None:
    tx_data = build_transaction(
        "success",
        [
            build_balance_change(SENDER_ADDRESS, SUI_COIN_TYPE, "-1000000000"),
            build_balance_change(VALID_SUI_ADDRESS, SUI_COIN_TYPE, "990000000"),
        ],
        digest="7xW7x7MGGs4QXf7YvP8u5wz9LkQyYpV6cDqZkSuiPay",
    )

    transactions = parse_transactions(tx_data)

    assert len(transactions) == 1
    assert transactions[0].hash == tx_data["digest"]
    assert transactions[0].from_addr == SENDER_ADDRESS
    assert transactions[0].to == VALID_SUI_ADDRESS
    assert transactions[0].value == 990000000
    assert transactions[0].contract is None


def test_process_tx_data_ignores_failed_and_non_native_changes() -> None:
    failed_tx = build_transaction(
        "failure",
        [build_balance_change(VALID_SUI_ADDRESS, SUI_COIN_TYPE, "100")],
        digest="failed",
    )
    token_tx = build_transaction(
        "success",
        [build_balance_change(VALID_SUI_ADDRESS, "0xabc::coin::TOKEN", "100")],
        digest="token",
    )

    assert parse_transactions(failed_tx) == []
    assert parse_transactions(token_tx) == []
