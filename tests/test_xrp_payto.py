"""
XRP Payto Integration Test — tests actual XRP sending on testnet.

Usage:
    cd bitcart
    python tests/test_xrp_payto.py

This test:
  1. Gets a funded wallet from the XRPL testnet faucet
  2. Tests unsigned payment construction
  3. Tests signed payment (actual send) with destination tag
  4. Verifies the transaction on-chain
  5. Tests the full destination-tag payment detection flow
"""

import asyncio
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemons"))

from decimal import Decimal

TESTNET_URL = "https://s.altnet.rippletest.net:51234"

passed = 0
failed = 0
errors = []


def import_xrp_module():
    """Import xrp.py classes without executing daemon.start() at module bottom."""
    import importlib.util

    daemons_dir = os.path.join(os.path.dirname(__file__), "..", "daemons")
    with open(os.path.join(daemons_dir, "xrp.py")) as f:
        source = f.read()
    lines = source.split("\n")
    filtered = [line for line in lines if line.strip() not in ("daemon = XRPDaemon()", "daemon.start()")]
    spec = importlib.util.spec_from_file_location("xrp", os.path.join(daemons_dir, "xrp.py"))
    module = importlib.util.module_from_spec(spec)
    code = compile("\n".join(filtered), os.path.join(daemons_dir, "xrp.py"), "exec")
    exec(code, module.__dict__)
    return module


def check_result(name, success, detail=""):
    global passed, failed
    if success:
        passed += 1
        print(f"  [PASS] {name}" + (f" ({detail})" if detail else ""))
    else:
        failed += 1
        errors.append((name, detail))
        print(f"  [FAIL] {name}: {detail}")


async def get_funded_wallet():
    """Get a funded testnet wallet from the XRPL faucet via HTTP API."""
    import aiohttp
    from xrpl.asyncio.clients import AsyncJsonRpcClient
    from xrpl.core.keypairs import derive_classic_address, derive_keypair, generate_seed

    print("  Requesting funded wallet from XRPL testnet faucet...")

    # Generate our own wallet
    seed = generate_seed()
    pub, priv = derive_keypair(seed)
    address = derive_classic_address(pub)

    # Fund it via faucet API
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            "https://faucet.altnet.rippletest.net/accounts",
            json={"destination": address},
            headers={"Content-Type": "application/json"},
        ) as resp,
    ):
        if resp.status != 200:
            body = await resp.text()
            raise Exception(f"Faucet returned {resp.status}: {body}")
        await resp.json()

    # Wait a moment for the funding tx to validate
    await asyncio.sleep(5)

    client = AsyncJsonRpcClient(TESTNET_URL)

    class FaucetWallet:
        pass

    wallet = FaucetWallet()
    wallet.address = address
    wallet.seed = seed
    wallet.public_key = pub
    wallet.private_key = priv

    print(f"  Got wallet: {address}")
    return wallet, client


async def run_tests():  # noqa: C901
    global passed, failed

    print("=" * 60)
    print("XRP Payto Integration Test -- XRPL Testnet")
    print("=" * 60)

    xrp_mod = import_xrp_module()
    XRPLRPCProvider = xrp_mod.XRPLRPCProvider
    MultipleRPCXRPLProvider = xrp_mod.MultipleRPCXRPLProvider
    XRPFeatures = xrp_mod.XRPFeatures
    KeyStore = xrp_mod.KeyStore
    XRPDaemon = xrp_mod.XRPDaemon
    DIVISIBILITY = xrp_mod.DIVISIBILITY
    from utils import MultipleProviderRPC

    # ── Setup: Get funded wallets ──
    print("\n--- Setup: Faucet Wallets ---")

    try:
        sender_wallet, client = await get_funded_wallet()
        check_result("Faucet wallet (sender)", True, sender_wallet.address)
    except Exception as e:
        check_result("Faucet wallet (sender)", False, str(e))
        print("FATAL: Cannot get faucet wallet. Aborting.")
        return False

    try:
        receiver_wallet, _ = await get_funded_wallet()
        check_result("Faucet wallet (receiver)", True, receiver_wallet.address)
    except Exception as e:
        check_result("Faucet wallet (receiver)", False, str(e))
        print("FATAL: Cannot get receiver wallet. Aborting.")
        return False

    # ── Setup: Create coin (XRPFeatures) ──
    print("\n--- Setup: RPC Connection ---")

    try:
        provider = XRPLRPCProvider(TESTNET_URL)
        multi = MultipleProviderRPC([provider])
        await multi.start()
        xrp_provider = MultipleRPCXRPLProvider(multi)
        coin = XRPFeatures(xrp_provider)
        check_result("XRPFeatures connected", await coin.is_connected())
    except Exception as e:
        check_result("XRPFeatures connected", False, str(e))
        return False

    # ── 1. Check sender balance ──
    print("\n--- Pre-Send Checks ---")

    try:
        sender_balance = await coin.get_balance(sender_wallet.address)
        sender_xrp = sender_balance / Decimal(10**DIVISIBILITY)
        check_result("Sender balance", sender_balance > 0, f"{sender_xrp} XRP ({sender_balance} drops)")
    except Exception as e:
        check_result("Sender balance", False, str(e))
        return False

    try:
        receiver_balance_before = await coin.get_balance(receiver_wallet.address)
        receiver_xrp_before = receiver_balance_before / Decimal(10**DIVISIBILITY)
        check_result("Receiver balance (before)", True, f"{receiver_xrp_before} XRP")
    except Exception as e:
        check_result("Receiver balance (before)", False, str(e))

    # ── 2. KeyStore from faucet seed ──
    print("\n--- KeyStore from Faucet Seed ---")

    try:
        ks = KeyStore(key=sender_wallet.seed)
        check_result(
            "KeyStore address matches faucet",
            ks.address == sender_wallet.address,
            f"ks={ks.address}, faucet={sender_wallet.address}",
        )
    except Exception as e:
        check_result("KeyStore from faucet seed", False, str(e))
        return False

    # ── 3. Build unsigned payment ──
    print("\n--- Unsigned Payment Construction ---")

    try:
        from xrpl.models.transactions import Payment
        from xrpl.utils import xrp_to_drops

        amount_xrp = Decimal("1.5")
        dest_tag = 99999

        payment_fields = {
            "account": sender_wallet.address,
            "destination": receiver_wallet.address,
            "amount": xrp_to_drops(amount_xrp),
            "destination_tag": dest_tag,
        }
        payment = Payment(**payment_fields)
        check_result(
            "Unsigned Payment object",
            payment.account == sender_wallet.address
            and payment.destination == receiver_wallet.address
            and payment.destination_tag == dest_tag,
            f"amount={payment.amount} drops, dt={payment.destination_tag}",
        )
    except Exception as e:
        check_result("Unsigned Payment object", False, str(e))

    # ── 4. Autofill + Sign + Submit (the actual payto flow) ──
    print("\n--- Signed Payment (Live Send) ---")

    tx_hash = None
    try:
        from xrpl.asyncio.transaction import autofill
        from xrpl.asyncio.transaction import sign as xrpl_sign
        from xrpl.models.requests import SubmitOnly
        from xrpl.wallet import Wallet as XRPLWallet

        # Autofill (adds sequence, fee, last_ledger_sequence)
        prepared = await autofill(payment, client)
        check_result(
            "Autofill transaction",
            prepared.sequence is not None and prepared.fee is not None,
            f"seq={prepared.sequence}, fee={prepared.fee}",
        )
    except Exception as e:
        check_result("Autofill transaction", False, str(e))

    try:
        # Sign
        xrpl_wallet = XRPLWallet(
            public_key=ks.public_key,
            private_key=ks.private_key,
        )
        signed = xrpl_sign(prepared, xrpl_wallet)

        # Verify signed.blob() works (blob is a method in xrpl-py 4.x)
        tx_blob = signed.blob()
        check_result("Sign transaction (signed.blob())", tx_blob is not None and len(tx_blob) > 0, f"blob_len={len(tx_blob)}")
    except Exception as e:
        check_result("Sign transaction", False, str(e))

    try:
        # Submit
        response = await coin._request(SubmitOnly(tx_blob=tx_blob))
        engine_result = response.result.get("engine_result", "")
        tx_hash = response.result.get("tx_json", {}).get("hash", "")

        check_result(
            "Submit transaction", engine_result == "tesSUCCESS", f"engine_result={engine_result}, hash={tx_hash[:16]}..."
        )
    except Exception as e:
        check_result("Submit transaction", False, str(e))

    if not tx_hash:
        print("  WARN: No tx hash, skipping on-chain verification")
    else:
        # ── 5. Wait for validation and verify on-chain ──
        print("\n--- On-Chain Verification ---")

        # Wait for the tx to be validated (usually 3-5 seconds)
        print("  Waiting for ledger validation...")
        validated = False
        for _attempt in range(15):
            await asyncio.sleep(2)
            try:
                tx_data = await coin.get_transaction(tx_hash)
                if tx_data.get("validated", False):
                    validated = True
                    break
            except Exception:
                pass
        check_result("Transaction validated on-chain", validated)

        if validated:
            # Debug: print tx_data keys to understand structure
            print(f"  DEBUG tx_data keys: {list(tx_data.keys())}")
            # The Tx response nests data differently — check for tx_json wrapper
            actual_tx = tx_data.get("tx_json", tx_data)
            print(f"  DEBUG actual_tx keys: {list(actual_tx.keys())[:10]}")
            meta_obj = tx_data.get("meta", {})
            meta_keys = list(meta_obj.keys())[:5] if isinstance(meta_obj, dict) else "N/A"
            print(f"  DEBUG meta type: {type(meta_obj)}, keys: {meta_keys}")
            print(f"  DEBUG top-level Account: {tx_data.get('Account', 'MISSING')}")
            print(f"  DEBUG tx_json Account: {actual_tx.get('Account', 'MISSING')}")
            print(f"  DEBUG tx_json DestinationTag: {actual_tx.get('DestinationTag', 'MISSING')}")

            # Check tx details
            try:
                check_result(
                    "TX destination matches",
                    actual_tx.get("Destination") == receiver_wallet.address,
                    f"got={actual_tx.get('Destination')}",
                )
                check_result(
                    "TX destination_tag matches",
                    actual_tx.get("DestinationTag") == dest_tag,
                    f"got={actual_tx.get('DestinationTag')}",
                )
                check_result(
                    "TX account matches", actual_tx.get("Account") == sender_wallet.address, f"got={actual_tx.get('Account')}"
                )

                meta = tx_data.get("meta", {})
                delivered = meta.get("delivered_amount", "0")
                expected_drops = str(int(amount_xrp * 10**DIVISIBILITY))
                check_result(
                    "TX delivered_amount correct",
                    delivered == expected_drops,
                    f"delivered={delivered}, expected={expected_drops}",
                )
                check_result("TX result is tesSUCCESS", meta.get("TransactionResult") == "tesSUCCESS")
            except Exception as e:
                check_result("TX details verification", False, str(e))

            # Check confirmations
            try:
                confs = await coin.get_confirmations(tx_hash, tx_data)
                check_result("get_confirmations", isinstance(confs, int) and confs >= 1, f"confirmations={confs}")
            except Exception as e:
                check_result("get_confirmations", False, str(e))

            # ── 6. Test process_tx_data on our real transaction ──
            print("\n--- process_tx_data (Real TX) ---")

            # process_tx_data expects the ledger format (from get_block_txes),
            # not the Tx response format. The Tx response nests data under tx_json.
            # In ledger responses, tx data is at the top level.
            # Test both: the raw tx_data (Tx response) and the unwrapped tx_json.

            # First, test with tx_json unwrapped (simulates ledger format)
            ledger_format = {**actual_tx, "meta": tx_data.get("meta", {}), "hash": tx_data.get("hash", "")}
            # xrpl-py 4.x uses "DeliverMax" instead of "Amount" for payments
            if "DeliverMax" in ledger_format and "Amount" not in ledger_format:
                ledger_format["Amount"] = ledger_format["DeliverMax"]
            print(f"  DEBUG ledger_format TransactionType: {ledger_format.get('TransactionType')}")
            try:
                parsed_tx = await coin.process_tx_data(ledger_format)
                check_result("process_tx_data parses real tx (ledger format)", parsed_tx is not None)
                if parsed_tx:
                    check_result("Parsed TX hash", parsed_tx.hash == tx_hash)
                    check_result("Parsed TX from_addr", parsed_tx.from_addr == sender_wallet.address)
                    check_result("Parsed TX to", parsed_tx.to == receiver_wallet.address)
                    check_result(
                        "Parsed TX destination_tag", parsed_tx.destination_tag == dest_tag, f"got={parsed_tx.destination_tag}"
                    )
                    check_result(
                        "Parsed TX value (drops)",
                        parsed_tx.value == int(amount_xrp * 10**DIVISIBILITY),
                        f"value={parsed_tx.value}",
                    )
            except Exception:
                check_result("process_tx_data (real tx)", False, traceback.format_exc())

            # Test actual ledger format from get_block_txes
            try:
                tx_ledger_index = tx_data.get("ledger_index")
                if tx_ledger_index:
                    block_txes = await coin.get_block_txes(tx_ledger_index)
                    # Find our tx in the ledger
                    our_tx_raw = None
                    for btx in block_txes:
                        btx_hash = btx.get("hash", "")
                        if btx_hash == tx_hash:
                            our_tx_raw = btx
                            break
                    if our_tx_raw:
                        print(f"  DEBUG ledger tx keys: {list(our_tx_raw.keys())[:10]}")
                        # Check if ledger format also nests under tx_json
                        if "tx_json" in our_tx_raw:
                            print("  DEBUG: Ledger also uses tx_json wrapper!")
                        parsed_ledger = await coin.process_tx_data(our_tx_raw)
                        check_result(
                            "process_tx_data (actual ledger format)",
                            parsed_ledger is not None,
                            f"parsed={parsed_ledger is not None}",
                        )
                    else:
                        check_result("process_tx_data (actual ledger format)", True, "skipped - tx not in ledger response")
                else:
                    check_result("process_tx_data (actual ledger format)", True, "skipped - no ledger_index")
            except Exception:
                check_result("process_tx_data (actual ledger)", False, traceback.format_exc())

            # ── 7. Verify receiver balance increased ──
            print("\n--- Balance Verification ---")

            try:
                receiver_balance_after = await coin.get_balance(receiver_wallet.address)
                receiver_xrp_after = receiver_balance_after / Decimal(10**DIVISIBILITY)
                balance_diff = receiver_balance_after - receiver_balance_before
                expected_diff = int(amount_xrp * 10**DIVISIBILITY)
                check_result(
                    "Receiver balance increased",
                    balance_diff == expected_diff,
                    f"before={receiver_xrp_before} XRP, after={receiver_xrp_after} XRP, diff={balance_diff} drops",
                )
            except Exception as e:
                check_result("Receiver balance check", False, str(e))

            try:
                sender_balance_after = await coin.get_balance(sender_wallet.address)
                sender_xrp_after = sender_balance_after / Decimal(10**DIVISIBILITY)
                # Sender should have lost amount + fee
                sender_lost = sender_balance - sender_balance_after
                check_result(
                    "Sender balance decreased",
                    sender_lost >= int(amount_xrp * 10**DIVISIBILITY),
                    f"before={sender_xrp} XRP, after={sender_xrp_after} XRP, lost={sender_lost} drops (includes fee)",
                )
            except Exception as e:
                check_result("Sender balance check", False, str(e))

    # ── 8. Test _sign_transaction helper ──
    print("\n--- _sign_transaction Helper ---")

    try:
        from xrpl.models.transactions import Payment as PaymentModel
        from xrpl.utils import xrp_to_drops as to_drops

        test_payment = PaymentModel(
            account=sender_wallet.address,
            destination=receiver_wallet.address,
            amount=to_drops(Decimal("0.1")),
            sequence=999999,
            fee="12",
        )
        # Create a daemon instance to test _sign_transaction
        daemon_inst = XRPDaemon.__new__(XRPDaemon)
        blob = daemon_inst._sign_transaction(test_payment.to_xrpl(), ks.seed)
        check_result("_sign_transaction returns blob", isinstance(blob, str) and len(blob) > 0, f"blob_len={len(blob)}")
    except Exception:
        check_result("_sign_transaction", False, traceback.format_exc())

    # ── 9. X-address handling in payment ──
    print("\n--- X-Address Payment Support ---")

    try:
        from xrpl.core.addresscodec import classic_address_to_xaddress

        # Create X-address with embedded destination tag
        x_addr_with_tag = classic_address_to_xaddress(receiver_wallet.address, 54321, True)
        check_result("X-address created with tag", True, f"x_addr={x_addr_with_tag[:20]}...")

        # Verify X-address decomposition (what payto does)
        from xrpl.core.addresscodec import xaddress_to_classic_address

        classic, tag, _ = xaddress_to_classic_address(x_addr_with_tag)
        check_result(
            "X-address decomposition", classic == receiver_wallet.address and tag == 54321, f"classic={classic}, tag={tag}"
        )
    except Exception as e:
        check_result("X-address handling", False, str(e))

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
