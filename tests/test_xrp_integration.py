"""
XRP Integration Test — runs against public XRPL Testnet.

Usage:
    cd bitcart
    python tests/test_xrp_integration.py

This tests the core XRP daemon components WITHOUT starting the full daemon:
  - RPC provider connectivity
  - XRPFeatures (block number, balance, gas price, tx lookup, address validation)
  - KeyStore (seed generation, address derivation, X-address handling)
  - Wallet (invoice creation, destination tag generation, export)
  - Payment construction (payto unsigned)
  - Transaction processing (destination tag matching)
"""

import asyncio
import sys
import os
import traceback

# Add daemons to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemons"))

from decimal import Decimal


TESTNET_URL = "https://s.altnet.rippletest.net:51234"
# Known funded testnet address for read-only tests
KNOWN_TESTNET_ADDRESS = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"  # genesis account


def import_xrp_module():
    """Import xrp.py classes without executing daemon.start() at module bottom."""
    import importlib.util

    daemons_dir = os.path.join(os.path.dirname(__file__), "..", "daemons")
    spec = importlib.util.spec_from_file_location("xrp", os.path.join(daemons_dir, "xrp.py"))
    module = importlib.util.module_from_spec(spec)

    # Read source and strip the last 2 lines (daemon = XRPDaemon(); daemon.start())
    with open(os.path.join(daemons_dir, "xrp.py"), "r") as f:
        source = f.read()

    # Remove module-level daemon startup
    lines = source.split("\n")
    # Remove "daemon = XRPDaemon()" and "daemon.start()"
    filtered = [l for l in lines if l.strip() not in ("daemon = XRPDaemon()", "daemon.start()")]
    code = compile("\n".join(filtered), os.path.join(daemons_dir, "xrp.py"), "exec")
    exec(code, module.__dict__)
    return module

passed = 0
failed = 0
errors = []


def test_result(name, success, detail=""):
    global passed, failed
    if success:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        errors.append((name, detail))
        print(f"  [FAIL] {name}: {detail}")


async def run_tests():
    global passed, failed

    print("=" * 60)
    print("XRP Integration Tests — XRPL Testnet")
    print("=" * 60)

    # ── 1. RPC Provider & Connectivity ──
    print("\n--- RPC Provider & Connectivity ---")

    xrp_mod = import_xrp_module()
    XRPLRPCProvider = xrp_mod.XRPLRPCProvider
    MultipleRPCXRPLProvider = xrp_mod.MultipleRPCXRPLProvider
    XRPFeatures = xrp_mod.XRPFeatures

    daemons_dir = os.path.join(os.path.dirname(__file__), "..", "daemons")
    sys.path.insert(0, daemons_dir)
    from utils import MultipleProviderRPC

    try:
        provider = XRPLRPCProvider(TESTNET_URL)
        test_result("XRPLRPCProvider created", True)
    except Exception as e:
        test_result("XRPLRPCProvider created", False, str(e))
        print("FATAL: Cannot create provider. Aborting.")
        return

    # Test send_ping_request (AbstractRPCProvider interface)
    try:
        await provider.send_ping_request()
        test_result("send_ping_request (AbstractRPCProvider)", True)
    except Exception as e:
        test_result("send_ping_request (AbstractRPCProvider)", False, str(e))

    # Test send_single_request (AbstractRPCProvider interface)
    try:
        from xrpl.models.requests import ServerInfo
        resp = await provider.send_single_request(ServerInfo())
        test_result("send_single_request (AbstractRPCProvider)", resp.is_successful())
    except Exception as e:
        test_result("send_single_request (AbstractRPCProvider)", False, str(e))

    # Test MultipleProviderRPC integration (use fresh provider to avoid stale client)
    try:
        provider2 = XRPLRPCProvider(TESTNET_URL)
        multi = MultipleProviderRPC([provider2])
        await multi.start()
        resp = await multi.send_request(ServerInfo())
        test_result("MultipleProviderRPC.send_request", resp.is_successful())
    except Exception as e:
        test_result("MultipleProviderRPC.send_request", False, str(e))

    # Create XRPFeatures for remaining tests
    xrp_provider = MultipleRPCXRPLProvider(multi)
    coin = XRPFeatures(xrp_provider)

    # ── 2. BlockchainFeatures ──
    print("\n--- BlockchainFeatures ---")

    # is_connected
    try:
        connected = await coin.is_connected()
        test_result("is_connected", connected)
    except Exception as e:
        test_result("is_connected", False, str(e))

    # get_block_number
    ledger_index = None
    try:
        ledger_index = await coin.get_block_number()
        test_result("get_block_number", isinstance(ledger_index, int) and ledger_index > 0,
                     f"ledger_index={ledger_index}")
    except Exception as e:
        test_result("get_block_number", False, str(e))

    # get_gas_price (fee)
    try:
        fee = await coin.get_gas_price()
        test_result("get_gas_price (fee in drops)", isinstance(fee, int) and fee > 0,
                     f"fee={fee} drops")
    except Exception as e:
        test_result("get_gas_price", False, str(e))

    # get_balance
    try:
        balance = await coin.get_balance(KNOWN_TESTNET_ADDRESS)
        test_result("get_balance (genesis)", isinstance(balance, Decimal),
                     f"balance={balance} drops")
    except Exception as e:
        test_result("get_balance", False, str(e))

    # get_balance for non-existent address returns 0
    try:
        # Use a valid-format but unfunded address
        from xrpl.core.keypairs import generate_seed, derive_keypair, derive_classic_address
        tmp_seed = generate_seed()
        tmp_pub, _ = derive_keypair(tmp_seed)
        unfunded_addr = derive_classic_address(tmp_pub)
        zero_bal = await coin.get_balance(unfunded_addr)
        test_result("get_balance (non-existent = 0)", zero_bal == Decimal(0))
    except Exception as e:
        test_result("get_balance (non-existent)", False, str(e))

    # get_block
    try:
        block = await coin.get_block("validated")
        test_result("get_block('validated')",
                     isinstance(block, dict) and "close_time" in block,
                     f"keys={list(block.keys())[:5]}")
    except Exception as e:
        test_result("get_block", False, str(e))

    # get_block by number
    if ledger_index:
        try:
            block = await coin.get_block(ledger_index)
            test_result("get_block(number)",
                         isinstance(block, dict) and "close_time" in block)
        except Exception as e:
            test_result("get_block(number)", False, str(e))

    # get_block_txes
    if ledger_index:
        try:
            txes = await coin.get_block_txes(ledger_index)
            test_result("get_block_txes", isinstance(txes, list),
                         f"count={len(txes)}")
        except Exception as e:
            test_result("get_block_txes", False, str(e))

    # chain_id
    try:
        cid = await coin.chain_id()
        test_result("chain_id", cid == 0)
    except Exception as e:
        test_result("chain_id", False, str(e))

    # ── 3. Address Validation ──
    print("\n--- Address Validation ---")

    test_result("is_address (valid classic)", coin.is_address("rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"))
    test_result("is_address (invalid)", not coin.is_address("not_an_address"))

    # X-address
    from xrpl.core.addresscodec import classic_address_to_xaddress
    x_addr = classic_address_to_xaddress(KNOWN_TESTNET_ADDRESS, None, True)
    test_result("is_address (valid X-address)", coin.is_address(x_addr))

    # normalize_address
    normalized = coin.normalize_address(x_addr)
    test_result("normalize_address (X-addr to classic)", normalized == KNOWN_TESTNET_ADDRESS,
                 f"got={normalized}")
    test_result("normalize_address (classic passthrough)",
                 coin.normalize_address(KNOWN_TESTNET_ADDRESS) == KNOWN_TESTNET_ADDRESS)

    # ── 4. Payment URI ──
    print("\n--- Payment URI ---")

    try:
        uri = await coin.get_payment_uri(KNOWN_TESTNET_ADDRESS, Decimal("10"), 6, destination_tag=12345)
        test_result("get_payment_uri with dest_tag",
                     "dt=12345" in uri and KNOWN_TESTNET_ADDRESS in uri,
                     f"uri={uri}")
    except Exception as e:
        test_result("get_payment_uri", False, str(e))

    try:
        uri_no_tag = await coin.get_payment_uri(KNOWN_TESTNET_ADDRESS, Decimal("1"), 6)
        test_result("get_payment_uri without dest_tag",
                     "dt=" not in uri_no_tag,
                     f"uri={uri_no_tag}")
    except Exception as e:
        test_result("get_payment_uri (no tag)", False, str(e))

    # ── 5. KeyStore ──
    print("\n--- KeyStore ---")

    KeyStore = xrp_mod.KeyStore

    # Generate seed and derive
    from xrpl.core.keypairs import generate_seed
    seed = generate_seed()
    try:
        ks = KeyStore(key=seed)
        test_result("KeyStore from seed",
                     ks.address and ks.address.startswith("r") and ks.public_key and ks.private_key,
                     f"address={ks.address}")
    except Exception as e:
        test_result("KeyStore from seed", False, str(e))

    # KeyStore from classic address (watching-only)
    try:
        ks_watch = KeyStore(key=KNOWN_TESTNET_ADDRESS)
        test_result("KeyStore from classic address (watch-only)",
                     ks_watch.address == KNOWN_TESTNET_ADDRESS and ks_watch.private_key is None)
    except Exception as e:
        test_result("KeyStore from classic address", False, str(e))

    # KeyStore from X-address (watching-only)
    try:
        ks_x = KeyStore(key=x_addr)
        test_result("KeyStore from X-address (watch-only)",
                     ks_x.address == KNOWN_TESTNET_ADDRESS and ks_x.private_key is None,
                     f"address={ks_x.address}")
    except Exception as e:
        test_result("KeyStore from X-address", False, str(e))

    # KeyStore invalid key
    try:
        KeyStore(key="totally_invalid_key_123")
        test_result("KeyStore rejects invalid key", False, "Should have raised")
    except Exception as e:
        test_result("KeyStore rejects invalid key", "Invalid XRP key" in str(e))

    # add_privkey
    try:
        ks_reimport = KeyStore(key=ks.address)  # watch-only
        ks_reimport.add_privkey(seed)
        test_result("KeyStore.add_privkey",
                     ks_reimport.private_key == ks.private_key and ks_reimport.public_key == ks.public_key)
    except Exception as e:
        test_result("KeyStore.add_privkey", False, str(e))

    # add_privkey mismatch
    try:
        ks_mismatch = KeyStore(key=KNOWN_TESTNET_ADDRESS)
        ks_mismatch.add_privkey(seed)
        test_result("KeyStore.add_privkey rejects mismatch", False, "Should have raised")
    except Exception as e:
        test_result("KeyStore.add_privkey rejects mismatch", "mismatch" in str(e).lower())

    # ── 6. Transaction Data Processing ──
    print("\n--- Transaction Processing ---")

    Transaction = xrp_mod.Transaction

    # process_tx_data — valid payment
    try:
        tx_data = {
            "TransactionType": "Payment",
            "hash": "ABC123",
            "Account": "rSender111111111111111111111",
            "Destination": KNOWN_TESTNET_ADDRESS,
            "Amount": "1000000",
            "DestinationTag": 42,
            "meta": {
                "TransactionResult": "tesSUCCESS",
                "delivered_amount": "1000000",
            },
        }
        tx = await coin.process_tx_data(tx_data)
        test_result("process_tx_data (valid payment)",
                     tx is not None and tx.hash == "ABC123" and tx.destination_tag == 42
                     and tx.value == 1000000 and tx.to == KNOWN_TESTNET_ADDRESS)
    except Exception as e:
        test_result("process_tx_data (valid payment)", False, str(e))

    # process_tx_data — non-Payment type
    try:
        tx_offer = {"TransactionType": "OfferCreate", "hash": "X"}
        result = await coin.process_tx_data(tx_offer)
        test_result("process_tx_data (non-Payment  -> None)", result is None)
    except Exception as e:
        test_result("process_tx_data (non-Payment)", False, str(e))

    # process_tx_data — failed tx
    try:
        tx_fail = {
            "TransactionType": "Payment",
            "hash": "FAIL1",
            "Account": "rX",
            "Destination": "rY",
            "Amount": "100",
            "meta": {"TransactionResult": "tecUNFUNDED_PAYMENT"},
        }
        result = await coin.process_tx_data(tx_fail)
        test_result("process_tx_data (failed tx  -> None)", result is None)
    except Exception as e:
        test_result("process_tx_data (failed tx)", False, str(e))

    # process_tx_data — issued currency (not native XRP)
    try:
        tx_token = {
            "TransactionType": "Payment",
            "hash": "TOKEN1",
            "Account": "rX",
            "Destination": "rY",
            "Amount": {"currency": "USD", "value": "10", "issuer": "rZ"},
            "meta": {
                "TransactionResult": "tesSUCCESS",
                "delivered_amount": {"currency": "USD", "value": "10", "issuer": "rZ"},
            },
        }
        result = await coin.process_tx_data(tx_token)
        test_result("process_tx_data (issued currency  -> None)", result is None)
    except Exception as e:
        test_result("process_tx_data (issued currency)", False, str(e))

    # process_tx_data — partial payment (delivered_amount differs from Amount)
    try:
        tx_partial = {
            "TransactionType": "Payment",
            "hash": "PARTIAL1",
            "Account": "rSender",
            "Destination": "rReceiver",
            "Amount": "5000000",
            "meta": {
                "TransactionResult": "tesSUCCESS",
                "delivered_amount": "3000000",  # only 3 XRP delivered
            },
        }
        tx = await coin.process_tx_data(tx_partial)
        test_result("process_tx_data (partial payment protection)",
                     tx is not None and tx.value == 3000000,
                     f"value={tx.value if tx else 'None'} (expected 3000000)")
    except Exception as e:
        test_result("process_tx_data (partial payment)", False, str(e))

    # ── 7. Invoice & Wallet (in-memory) ──
    print("\n--- Invoice & Wallet ---")

    Invoice = xrp_mod.Invoice
    Wallet = xrp_mod.Wallet
    DIVISIBILITY = xrp_mod.DIVISIBILITY
    MAX_DESTINATION_TAG = xrp_mod.MAX_DESTINATION_TAG

    # Invoice dataclass
    try:
        inv = Invoice(
            address=KNOWN_TESTNET_ADDRESS,
            message="test",
            time=0,
            amount=Decimal("1"),
            sent_amount=Decimal("0"),
            exp=900,
            id="test-invoice-1",
            height=1000,
            destination_tag=42,
            payment_address="42",
        )
        test_result("Invoice dataclass creation",
                     inv.destination_tag == 42 and inv.payment_address == "42"
                     and inv.address == KNOWN_TESTNET_ADDRESS)
    except Exception as e:
        test_result("Invoice dataclass creation", False, str(e))

    # Invoice inherits BaseInvoice fields
    try:
        test_result("Invoice has BaseInvoice fields",
                     hasattr(inv, "status") and hasattr(inv, "sent_amount")
                     and hasattr(inv, "payment_address"))
    except Exception as e:
        test_result("Invoice inheritance", False, str(e))

    # Destination tag generation
    try:
        wallet_obj = Wallet.__new__(Wallet)
        wallet_obj.request_addresses = {}
        tags = set()
        for _ in range(100):
            tag = wallet_obj.generate_destination_tag()
            assert 1 <= tag <= MAX_DESTINATION_TAG, f"tag {tag} out of range"
            assert str(tag) not in wallet_obj.request_addresses
            tags.add(tag)
        test_result("generate_destination_tag (100 unique tags)",
                     len(tags) == 100)
    except Exception as e:
        test_result("generate_destination_tag", False, str(e))

    # ── 8. Spec File ──
    print("\n--- Spec File ---")

    import json
    spec_path = os.path.join(os.path.dirname(__file__), "..", "daemons", "spec", "xrp.json")
    try:
        with open(spec_path) as f:
            spec = json.load(f)
        test_result("xrp.json loads", isinstance(spec, dict))
        test_result("xrp.json has exceptions",
                     "exceptions" in spec and isinstance(spec["exceptions"], dict))
        # Check a few expected error codes
        has_errors = all(k in spec["exceptions"] for k in ["-32010", "-32011"])
        test_result("xrp.json has expected error codes", has_errors,
                     f"keys={list(spec['exceptions'].keys())[:5]}")
    except Exception as e:
        test_result("xrp.json", False, str(e))

    # ── 9. Block Explorer Config ──
    print("\n--- Block Explorer Config ---")

    explorer_path = os.path.join(os.path.dirname(__file__), "..", "api", "ext", "blockexplorer", "explorers.json")
    try:
        with open(explorer_path) as f:
            explorers = json.load(f)
        test_result("explorers.json has XRP", "xrp" in explorers)
        if "xrp" in explorers:
            xrp_exp = explorers["xrp"]
            test_result("XRP mainnet explorer URL",
                         "mainnet" in xrp_exp and "{}" in xrp_exp["mainnet"])
            test_result("XRP testnet explorer URL",
                         "testnet" in xrp_exp and "{}" in xrp_exp["testnet"])
    except Exception as e:
        test_result("explorers.json", False, str(e))

    # ── 10. Live Transaction Lookup (if available) ──
    print("\n--- Live Transaction Lookup ---")

    # Try to find a recent tx from the latest ledger
    if ledger_index:
        try:
            txes = await coin.get_block_txes(ledger_index)
            if txes:
                tx_hash = coin.get_tx_hash(txes[0])
                if tx_hash:
                    tx_detail = await coin.get_transaction(tx_hash)
                    test_result("get_transaction (live tx)",
                                 isinstance(tx_detail, dict) and ("Account" in tx_detail or "tx_json" in tx_detail),
                                 f"hash={tx_hash[:16]}...")
                    confs = await coin.get_confirmations(tx_hash, tx_detail)
                    test_result("get_confirmations (live tx)",
                                 isinstance(confs, int) and confs >= 0,
                                 f"confirmations={confs}")
                else:
                    test_result("get_transaction (live tx)", True, "skipped — no tx hash")
            else:
                test_result("get_transaction (live tx)", True, "skipped — empty ledger")
        except Exception as e:
            test_result("get_transaction (live tx)", False, str(e))

    # ── 11. Daemon Class Configuration ──
    print("\n--- Daemon Configuration ---")

    XRPDaemon = xrp_mod.XRPDaemon

    test_result("XRPDaemon.name", XRPDaemon.name == "XRP")
    test_result("XRPDaemon.DEFAULT_PORT", XRPDaemon.DEFAULT_PORT == 5012)
    test_result("XRPDaemon.DIVISIBILITY", XRPDaemon.DIVISIBILITY == 6)
    test_result("XRPDaemon.BLOCK_TIME", XRPDaemon.BLOCK_TIME == 4)
    test_result("XRPDaemon.KEYSTORE_CLASS", XRPDaemon.KEYSTORE_CLASS is KeyStore)
    test_result("XRPDaemon.WALLET_CLASS", XRPDaemon.WALLET_CLASS is Wallet)
    test_result("XRPDaemon.INVOICE_CLASS", XRPDaemon.INVOICE_CLASS is Invoice)
    test_result("XRPDaemon.UNIT", XRPDaemon.UNIT == "drop")

    # ── 12. SDK Integration ──
    print("\n--- SDK Integration ---")

    try:
        sdk_path = os.path.join(os.path.dirname(__file__), "..", "..", "bitcart-sdk")
        sys.path.insert(0, sdk_path)
        from bitcart import XRP as XRPCoin
        from bitcart.coins import COINS

        test_result("SDK: XRP importable", True)
        test_result("SDK: XRP in COINS", "XRP" in COINS)

        xrp_sdk = XRPCoin()
        test_result("SDK: coin_name", xrp_sdk.coin_name == "XRP")
        test_result("SDK: friendly_name", xrp_sdk.friendly_name == "XRP")
        test_result("SDK: RPC_URL", xrp_sdk.RPC_URL == "http://localhost:5012")
        test_result("SDK: is_eth_based", xrp_sdk.is_eth_based == False)
    except Exception as e:
        test_result("SDK integration", False, traceback.format_exc())

    # Cleanup
    await multi.stop()

    # ── Summary ──
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if errors:
        print("\nFailures:")
        for name, detail in errors:
            print(f"  - {name}: {detail}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
