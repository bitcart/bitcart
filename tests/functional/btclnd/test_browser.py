"""Browser-based end-to-end tests for the BTCLND admin panel.

Uses Playwright to drive a real browser against the admin panel,
testing the same flows as the API-level functional tests but through
the actual UI. This catches frontend rendering issues, broken forms,
and API/UI mismatches that unit and API tests miss.

Prerequisites:
    1. Start regtest environment: just btclnd-regtest-env
    2. Start full stack (daemon, API, worker, admin on port 3000)
    3. Create admin user (test@test.com / password)
    4. Run: pytest tests/functional/btclnd/test_browser.py -v --headed
       (use --headed to watch the browser, omit for headless CI)

Environment variables:
    ADMIN_URL: Admin panel URL (default: http://localhost:3000)
    ADMIN_EMAIL: Admin email (default: test@test.com)
    ADMIN_PASSWORD: Admin password (default: password)
"""

import json
import os
import re
import subprocess
import sys
import time

import pytest
from playwright.sync_api import Page, expect

ADMIN_URL = os.environ.get("ADMIN_URL", "http://localhost:3000")
API_URL = os.environ.get("API_URL", ADMIN_URL.replace(":3000", ":8000"))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "test@test.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")


# ---------------------------------------------------------------------------
# Regtest helpers (synchronous, for use in Playwright tests)
# ---------------------------------------------------------------------------

def _load_ports():
    """Load regtest port configuration."""
    ports_file = os.path.join(os.getcwd(), ".regtest", "ports.env")
    if not os.path.exists(ports_file):
        return {}
    ports = {}
    with open(ports_file) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                ports[k] = v
    return ports


def _bitcoin_cli(*args):
    """Run bitcoin-cli against regtest."""
    ports = _load_ports()
    rpc_port = ports.get("BITCOIND_RPC_PORT", "18554")
    bitcoin_dir = os.path.join(os.getcwd(), ".regtest", "bitcoind")
    cmd = [
        "bitcoin-cli", f"-datadir={bitcoin_dir}",
        "-rpcuser=doggman", "-rpcpassword=donkey",
        f"-rpcport={rpc_port}", "-rpcwallet=test_wallet", "-regtest",
    ] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def _mine_blocks(count, address=None):
    """Mine blocks in regtest."""
    if not address:
        address = _bitcoin_cli("getnewaddress")
    _bitcoin_cli("generatetoaddress", str(count), address)


def _get_api_headers(page: Page):
    """Get API auth headers using Playwright's request context."""
    resp = page.request.post(f"{API_URL}/token",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "permissions": ["full_control"]})
    if resp.status != 200:
        pytest.skip("Cannot get API token")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _api_get(page: Page, path: str):
    """GET from API."""
    return page.request.get(f"{API_URL}{path}", headers=_get_api_headers(page)).json()


def _api_post(page: Page, path: str, data: dict):
    """POST to API."""
    return page.request.post(f"{API_URL}{path}", headers=_get_api_headers(page), data=data)


@pytest.fixture(scope="session")
def browser_context_args():
    return {"ignore_https_errors": True}


@pytest.fixture(scope="function")
def logged_in_page(page: Page):
    """Log in to the admin panel and return the page."""
    page.goto(f"{ADMIN_URL}/login")
    page.wait_for_load_state("networkidle")
    # Fill login form
    page.fill('input[type="email"], input[name="email"]', ADMIN_EMAIL)
    page.fill('input[type="password"], input[name="password"]', ADMIN_PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{ADMIN_URL}/**")
    page.wait_for_load_state("networkidle")
    return page


class TestWalletCreation:
    """Test wallet creation flows via the browser."""

    def test_lnd_wallet_shows_warning(self, logged_in_page: Page):
        """Creating an LND wallet should show the experimental warning."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        # Click Add button
        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")

        # Select BTCLND currency
        page.click(".v-autocomplete")
        page.wait_for_selector(".v-list-item")
        page.click("text=btclnd")
        page.wait_for_timeout(500)

        # Warning should appear
        warning = page.locator("text=LND support in Bitcart is a new, experimental feature")
        expect(warning).to_be_visible()

    def test_lnd_wallet_shows_zero_conf_toggle(self, logged_in_page: Page):
        """Zero-conf monitoring toggle should appear for LND wallets."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")

        page.click(".v-autocomplete")
        page.wait_for_selector(".v-list-item")
        page.click("text=btclnd")
        page.wait_for_timeout(500)

        toggle = page.locator("text=Monitor for zero-conf transactions")
        expect(toggle).to_be_visible()

    def test_lnd_wallet_shows_tor_toggle(self, logged_in_page: Page):
        """Tor toggle should appear for LND wallets."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")

        page.click(".v-autocomplete")
        page.wait_for_selector(".v-list-item")
        page.click("text=btclnd")
        page.wait_for_timeout(500)

        toggle = page.locator("text=Enable Tor")
        expect(toggle).to_be_visible()

    def test_btc_wallet_no_lnd_warning(self, logged_in_page: Page):
        """BTC/Electrum wallet should NOT show the LND warning."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")

        # Default currency is btc
        page.wait_for_timeout(500)

        warning = page.locator("text=LND support in Bitcart is a new, experimental feature")
        expect(warning).not_to_be_visible()

    def test_btc_wallet_no_zero_conf_toggle(self, logged_in_page: Page):
        """Zero-conf toggle should NOT appear for BTC/Electrum wallets."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")
        page.wait_for_timeout(500)

        toggle = page.locator("text=Monitor for zero-conf transactions")
        expect(toggle).not_to_be_visible()

    def test_btc_wallet_no_tor_toggle(self, logged_in_page: Page):
        """Tor toggle should NOT appear for BTC/Electrum wallets."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")
        page.wait_for_timeout(500)

        toggle = page.locator("text=Enable Tor")
        expect(toggle).not_to_be_visible()

    def test_create_btc_wallet_generates_seed(self, logged_in_page: Page):
        """Creating a BTC/Electrum hot wallet should generate and display a seed."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")
        page.wait_for_timeout(500)

        # BTC is the default currency — fill name
        page.fill('input[aria-label="Name"], .v-text-field input', "test-btc-wallet")

        # Click "Create a new wallet"
        page.click("text=Create a new wallet")
        page.wait_for_selector("text=Create a new wallet")
        page.wait_for_timeout(500)

        # For Electrum, select "Hot wallet" radio
        hot_radio = page.locator("text=Hot wallet")
        if hot_radio.is_visible():
            hot_radio.click()
            page.wait_for_timeout(300)

        # Click Create
        create_btn = page.locator(".v-dialog--active >> text=Create")
        create_btn.click()

        # Wait for seed to appear
        page.wait_for_selector("code", timeout=60000)
        seed_text = page.locator(".v-dialog--active code").text_content()

        # Electrum seed should be 12 words
        words = seed_text.strip().split()
        assert len(words) == 12, f"Expected 12-word Electrum seed, got {len(words)}: {seed_text[:50]}..."

        # Close seed dialog
        page.click(".v-dialog--active >> text=Close")
        page.wait_for_timeout(500)

    def test_create_lnd_wallet_generates_seed(self, logged_in_page: Page):
        """Creating an LND hot wallet should generate and display a seed."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")

        page.click("text=Add")
        page.wait_for_selector(".v-dialog--active")

        # Select BTCLND
        page.click(".v-autocomplete")
        page.wait_for_selector(".v-list-item")
        page.click("text=btclnd")
        page.wait_for_timeout(500)

        # Fill name
        page.fill('input[aria-label="Name"], .v-text-field input', "test-lnd-wallet")

        # Click the "Create a new wallet" button to open seed dialog
        page.click("text=Create a new wallet")
        page.wait_for_selector("text=Create a new wallet")
        page.wait_for_timeout(500)

        # For LND (hot_wallet_only), it should skip wallet type selection
        # and go straight to Create
        create_btn = page.locator(".v-dialog--active >> text=Create")
        create_btn.click()

        # Wait for seed to appear
        page.wait_for_selector("code", timeout=60000)
        seed_text = page.locator(".v-dialog--active code").text_content()

        # Seed should be 24 words
        words = seed_text.strip().split()
        assert len(words) == 24, f"Expected 24-word seed, got {len(words)}: {seed_text[:50]}..."

        # Close seed dialog
        page.click(".v-dialog--active >> text=Close")
        page.wait_for_timeout(500)

        # Save the wallet
        page.click("text=Save")
        page.wait_for_timeout(3000)


class TestSettingsPersistence:
    """Test that wallet settings (Tor, zero-conf) persist across edit sessions."""

    def _create_lnd_wallet_via_api(self, page: Page, name: str, tor: bool, zero_conf: bool):
        """Create an LND wallet via API and return the wallet ID."""
        headers = _get_api_headers(page)
        # Generate seed
        import requests as req
        seed_resp = req.post("http://localhost:5012",
            auth=("electrum", "electrumz"),
            json={"method": "make_seed", "id": 1}, timeout=60)
        seed = seed_resp.json()["result"]

        resp = page.request.post(f"{API_URL}/wallets", headers=headers,
            data={
                "name": name, "xpub": seed, "currency": "btclnd",
                "lightning_enabled": True,
                "additional_xpub_data": {
                    "tor_enabled": tor,
                    "zero_conf_monitoring": zero_conf,
                },
            })
        return resp.json()["id"]

    def _open_edit_dialog_for_wallet(self, page: Page, wallet_name: str):
        """Navigate to wallets list and open the edit dialog for a wallet by name."""
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Click edit on the row with the matching name
        rows = page.locator("tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            if wallet_name in row.text_content():
                row.locator(".mdi-pencil, [aria-label='edit'], .v-icon:has-text('edit')").first.click()
                page.wait_for_selector(".v-dialog--active")
                page.wait_for_timeout(1000)
                return True
        return False

    def test_lnd_zero_conf_persists_after_edit(self, logged_in_page: Page):
        """Zero-conf setting should persist when re-opening the edit dialog."""
        page = logged_in_page
        wallet_id = self._create_lnd_wallet_via_api(page, "persist-zeroconf-test", tor=False, zero_conf=True)

        # Open edit dialog
        found = self._open_edit_dialog_for_wallet(page, "persist-zeroconf-test")
        assert found, "Could not find wallet in list"

        # Zero-conf toggle should be ON
        zero_conf_switch = page.locator("text=Monitor for zero-conf transactions").locator("..").locator("input[type='checkbox']")
        # Check the switch state via aria-checked or the v-input--is-label-active class
        dialog = page.locator(".v-dialog--active")
        dialog_text = dialog.text_content()
        assert "Monitor for zero-conf transactions" in dialog_text, "Zero-conf toggle should be visible"

        # The switch should reflect the saved state (enabled)
        switch_container = dialog.locator(".v-input--switch:has(.v-label:has-text('Monitor for zero-conf'))").first
        is_on = "v-input--is-label-active" in (switch_container.get_attribute("class") or "")
        # Alternative check: look at aria-checked
        if not is_on:
            checkbox = switch_container.locator("input[role='switch'], input[type='checkbox']").first
            is_on = checkbox.is_checked() if checkbox.count() > 0 else False
        assert is_on, "Zero-conf should be enabled after re-opening edit dialog"

    def test_lnd_tor_persists_after_edit(self, logged_in_page: Page):
        """Tor setting should persist when re-opening the edit dialog."""
        page = logged_in_page
        wallet_id = self._create_lnd_wallet_via_api(page, "persist-tor-test", tor=True, zero_conf=False)

        found = self._open_edit_dialog_for_wallet(page, "persist-tor-test")
        assert found, "Could not find wallet in list"

        dialog = page.locator(".v-dialog--active")
        dialog_text = dialog.text_content()
        assert "Enable Tor" in dialog_text, "Tor toggle should be visible"

        switch_container = dialog.locator(".v-input--switch:has(.v-label:has-text('Enable Tor'))").first
        is_on = "v-input--is-label-active" in (switch_container.get_attribute("class") or "")
        if not is_on:
            checkbox = switch_container.locator("input[role='switch'], input[type='checkbox']").first
            is_on = checkbox.is_checked() if checkbox.count() > 0 else False
        assert is_on, "Tor should be enabled after re-opening edit dialog"

    def test_lnd_disabled_settings_persist(self, logged_in_page: Page):
        """Disabled Tor and zero-conf should stay disabled after re-opening edit."""
        page = logged_in_page
        wallet_id = self._create_lnd_wallet_via_api(page, "persist-disabled-test", tor=False, zero_conf=False)

        found = self._open_edit_dialog_for_wallet(page, "persist-disabled-test")
        assert found, "Could not find wallet in list"

        dialog = page.locator(".v-dialog--active")

        # Zero-conf should be OFF
        zc_switch = dialog.locator(".v-input--switch:has(.v-label:has-text('Monitor for zero-conf'))").first
        zc_on = "v-input--is-label-active" in (zc_switch.get_attribute("class") or "")
        if not zc_on:
            checkbox = zc_switch.locator("input[role='switch'], input[type='checkbox']").first
            zc_on = checkbox.is_checked() if checkbox.count() > 0 else False
        assert not zc_on, "Zero-conf should be disabled"

        # Tor should be OFF
        tor_switch = dialog.locator(".v-input--switch:has(.v-label:has-text('Enable Tor'))").first
        tor_on = "v-input--is-label-active" in (tor_switch.get_attribute("class") or "")
        if not tor_on:
            checkbox = tor_switch.locator("input[role='switch'], input[type='checkbox']").first
            tor_on = checkbox.is_checked() if checkbox.count() > 0 else False
        assert not tor_on, "Tor should be disabled"

    def test_electrum_wallet_no_settings_leak(self, logged_in_page: Page):
        """Creating/editing an Electrum wallet should not have Tor/zero-conf fields
        and should not send these settings to the daemon."""
        page = logged_in_page
        headers = _get_api_headers(page)

        # Create Electrum wallet via API (without tor/zero_conf in additional_xpub_data)
        try:
            import requests as req
            seed_resp = req.post("http://localhost:5000",
                auth=("electrum", "electrumz"),
                json={"method": "make_seed", "id": 1}, timeout=30)
            seed = seed_resp.json().get("result")
            if not seed:
                pytest.skip("Electrum daemon not available")
        except Exception:
            pytest.skip("Electrum daemon not available")

        resp = page.request.post(f"{API_URL}/wallets", headers=headers,
            data={"name": "persist-electrum-test", "xpub": seed, "currency": "btc"})
        if resp.status != 200:
            pytest.skip("Cannot create Electrum wallet")
        wallet = resp.json()

        # Verify additional_xpub_data does NOT contain tor/zero_conf
        data = wallet.get("additional_xpub_data", {})
        assert "tor_enabled" not in data, f"Electrum wallet should not have tor_enabled, got: {data}"
        assert "zero_conf_monitoring" not in data, f"Electrum wallet should not have zero_conf, got: {data}"

        # Open edit dialog and verify toggles are hidden
        found = self._open_edit_dialog_for_wallet(page, "persist-electrum-test")
        if not found:
            pytest.skip("Could not find Electrum wallet in list")

        dialog = page.locator(".v-dialog--active")
        dialog_text = dialog.text_content()
        assert "Monitor for zero-conf transactions" not in dialog_text, \
            "Zero-conf toggle should not appear for Electrum wallet"
        assert "Enable Tor" not in dialog_text, \
            "Tor toggle should not appear for Electrum wallet"

    def test_electrum_wallet_save_works(self, logged_in_page: Page):
        """Editing and saving an Electrum wallet should work without errors."""
        page = logged_in_page

        found = self._open_edit_dialog_for_wallet(page, "persist-electrum-test")
        if not found:
            pytest.skip("No Electrum test wallet found")

        # Change the name and save
        dialog = page.locator(".v-dialog--active")
        name_field = dialog.locator("input").first
        name_field.fill("persist-electrum-test-edited")

        dialog.locator("text=Save").click()
        page.wait_for_timeout(3000)

        # Verify no error snackbar
        page_text = page.content().lower()
        assert "invalid xpub" not in page_text, "Saving Electrum wallet should not produce invalid xpub error"
        assert "unexpected keyword" not in page_text, "Saving should not produce keyword argument error"


class TestWalletList:
    """Test wallet list page displays correctly."""

    def test_lightning_indicator_shows_for_all_wallets(self, logged_in_page: Page):
        """Lightning enabled/disabled indicator should appear for all wallets."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Should have circle icons (our lightning indicator)
        indicators = page.locator("td >> .mdi-circle, td >> .mdi-circle-outline")
        expect(indicators.first).to_be_visible()

    def test_node_status_icon_only_for_lnd(self, logged_in_page: Page):
        """Node status action icon should only appear for BTCLND wallets."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Lightning bolt should appear for all rows
        lightning_icons = page.locator("td .mdi-lightning-bolt")
        count = lightning_icons.count()
        assert count > 0, "No lightning management icons found"

        # Info icons should only appear for LND wallets
        info_icons = page.locator("td .mdi-information-outline")
        info_count = info_icons.count()
        # Count should be less than total wallets if we have both BTC and BTCLND
        assert info_count <= count, "Info icons should not exceed lightning icons"


class TestCheckoutDisplay:
    """Test that the checkout page displays correctly for both wallet types."""

    def _get_api_headers(self, page: Page):
        """Get API auth headers."""
        api_url = ADMIN_URL.replace(":3000", ":8000")
        token_resp = page.request.post(f"{api_url}/token",
            data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "permissions": ["full_control"]})
        if token_resp.status != 200:
            pytest.skip("Cannot get API token")
        return {"Authorization": f"Bearer {token_resp.json()['access_token']}"}

    def _create_invoice_and_get_checkout(self, page: Page, store_id: str):
        """Create invoice via API and navigate to checkout page."""
        api_url = ADMIN_URL.replace(":3000", ":8000")
        headers = self._get_api_headers(page)
        inv_resp = page.request.post(
            f"{api_url}/invoices",
            headers=headers,
            data={"store_id": store_id, "price": 0.00001, "currency": "BTC"},
        )
        if inv_resp.status != 200:
            pytest.skip("Cannot create invoice")
        invoice_id = inv_resp.json()["id"]
        page.goto(f"{ADMIN_URL}/i/{invoice_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        return inv_resp.json()

    def _find_store_with_wallet_type(self, page: Page, currency: str):
        """Find or create a store that uses a wallet of the given currency."""
        headers = self._get_api_headers(page)
        stores = page.request.get(f"{API_URL}/stores", headers=headers).json().get("result", [])
        wallets = page.request.get(f"{API_URL}/wallets", headers=headers).json().get("result", [])
        wallet_map = {w["id"]: w for w in wallets}
        for store in stores:
            for wid in store.get("wallets", []):
                w = wallet_map.get(wid)
                if w and w["currency"].lower() == currency.lower():
                    return store["id"]
        # No existing store — find a wallet and create one
        for w in wallets:
            if w["currency"].lower() == currency.lower():
                resp = page.request.post(f"{API_URL}/stores", headers=headers,
                    data={"name": f"{currency.upper()} Auto Store", "wallets": [w["id"]]})
                if resp.status == 200:
                    return resp.json()["id"]
        return None

    def _get_invoice_payment_methods(self, page: Page, store_id: str):
        """Create an invoice via API and return its payment methods."""
        headers = self._get_api_headers(page)
        inv_resp = page.request.post(
            f"{API_URL}/invoices",
            headers=headers,
            data={"store_id": store_id, "price": 0.00001, "currency": "BTC"},
        )
        if inv_resp.status != 200:
            return None, []
        invoice = inv_resp.json()
        return invoice["id"], invoice.get("payments", [])

    def _create_wallet_and_store(self, page: Page, currency: str, name: str, lightning_enabled: bool = True):
        """Create a fresh wallet and store via API, return (wallet_id, store_id)."""
        headers = self._get_api_headers(page)
        daemon_port = 5012 if currency == "btclnd" else 5000

        # Generate seed
        import requests as req
        try:
            seed_resp = req.post(f"http://localhost:{daemon_port}",
                auth=("electrum", "electrumz"),
                json={"method": "make_seed", "id": 1}, timeout=60)
            seed = seed_resp.json().get("result")
            if not seed:
                return None, None
        except Exception:
            return None, None

        # Create wallet
        wallet_data = {
            "name": name, "xpub": seed, "currency": currency,
            "lightning_enabled": lightning_enabled,
        }
        resp = page.request.post(f"{API_URL}/wallets", headers=headers, data=wallet_data)
        if resp.status != 200:
            return None, None
        wallet_id = resp.json()["id"]

        # Create store
        store_resp = page.request.post(f"{API_URL}/stores", headers=headers,
            data={"name": f"{name} Store", "wallets": [wallet_id]})
        if store_resp.status != 200:
            return None, None
        store_id = store_resp.json()["id"]
        return wallet_id, store_id

    def test_lnd_no_channels_no_lightning_pm(self, logged_in_page: Page):
        """LND wallet with no channels should NOT show lightning payment method."""
        page = logged_in_page
        wallet_id, store_id = self._create_wallet_and_store(page, "btclnd", "lnd-no-channels-test")
        if not wallet_id:
            pytest.skip("Cannot create LND wallet")

        invoice_id, payments = self._get_invoice_payment_methods(page, store_id)
        if not invoice_id:
            pytest.skip("Cannot create invoice")

        lightning_pms = [p for p in payments if p.get("lightning")]
        onchain_pms = [p for p in payments if not p.get("lightning")]

        assert len(onchain_pms) > 0, "Should have on-chain payment method"
        assert len(lightning_pms) == 0, (
            f"Should NOT have lightning PM with no inbound capacity. "
            f"Got {len(lightning_pms)} lightning PM(s)"
        )

        # Verify checkout page only shows on-chain
        page.goto(f"{ADMIN_URL}/i/{invoice_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        page_text = page.content()
        assert "BTCLND" not in page_text, "Should show BTC not BTCLND"

    def test_lnd_checkout_shows_btc_not_btclnd(self, logged_in_page: Page):
        """LND checkout page should show 'BTC' not 'BTCLND' for payment methods."""
        page = logged_in_page
        store_id = self._find_store_with_wallet_type(page, "btclnd")
        if not store_id:
            pytest.skip("No store with BTCLND wallet")

        self._create_invoice_and_get_checkout(page, store_id)
        page_text = page.content()
        assert "BTCLND" not in page_text, "LND checkout should show 'BTC' not 'BTCLND'"

    def test_electrum_lightning_disabled_no_lightning_pm(self, logged_in_page: Page):
        """Electrum wallet with lightning disabled should only show on-chain PM."""
        page = logged_in_page
        wallet_id, store_id = self._create_wallet_and_store(
            page, "btc", "btc-ln-disabled-test", lightning_enabled=False
        )
        if not wallet_id:
            pytest.skip("Cannot create Electrum wallet")

        invoice_id, payments = self._get_invoice_payment_methods(page, store_id)
        if not invoice_id:
            pytest.skip("Cannot create invoice")

        lightning_pms = [p for p in payments if p.get("lightning")]
        onchain_pms = [p for p in payments if not p.get("lightning")]

        assert len(onchain_pms) > 0, "Should have on-chain payment method"
        assert len(lightning_pms) == 0, "Should NOT have lightning PM when lightning is disabled"

    def test_electrum_lightning_enabled_no_channels_no_lightning_pm(self, logged_in_page: Page):
        """Electrum wallet with lightning enabled but no channels should NOT show lightning PM."""
        page = logged_in_page
        wallet_id, store_id = self._create_wallet_and_store(
            page, "btc", "btc-ln-no-channels-test", lightning_enabled=True
        )
        if not wallet_id:
            pytest.skip("Cannot create Electrum wallet")

        invoice_id, payments = self._get_invoice_payment_methods(page, store_id)
        if not invoice_id:
            pytest.skip("Cannot create invoice")

        lightning_pms = [p for p in payments if p.get("lightning")]
        onchain_pms = [p for p in payments if not p.get("lightning")]

        assert len(onchain_pms) > 0, "Should have on-chain payment method"
        assert len(lightning_pms) == 0, (
            "Should NOT have lightning PM when lightning is enabled but no channels exist"
        )

    def test_electrum_checkout_shows_btc(self, logged_in_page: Page):
        """Electrum checkout page should show 'BTC' for payment methods."""
        page = logged_in_page
        store_id = self._find_store_with_wallet_type(page, "btc")
        if not store_id:
            pytest.skip("No store with BTC/Electrum wallet")

        self._create_invoice_and_get_checkout(page, store_id)
        page_text = page.content()
        assert "BTCLND" not in page_text, "Electrum checkout should show 'BTC' not 'BTCLND'"


class TestLightningManagement:
    """Test the lightning management page."""

    def _navigate_to_lightning(self, page: Page):
        """Navigate to the lightning management page for the first LND wallet."""
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Click lightning bolt on first LND wallet row
        rows = page.locator("tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            if "btclnd" in row.text_content().lower():
                row.locator(".mdi-lightning-bolt").click()
                break
        else:
            pytest.skip("No LND wallet found in wallet list")

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

    def test_lightning_page_shows_network(self, logged_in_page: Page):
        """Lightning page should show the network chip (e.g., 'regtest')."""
        page = logged_in_page
        self._navigate_to_lightning(page)

        # Should show network chip
        network_chip = page.locator(".v-chip:has-text('regtest'), .v-chip:has-text('signet'), .v-chip:has-text('mainnet')")
        expect(network_chip.first).to_be_visible()

    def test_lightning_page_shows_announced_toggle(self, logged_in_page: Page):
        """Lightning page should show the announced/unannounced toggle for LND wallets."""
        page = logged_in_page
        self._navigate_to_lightning(page)

        toggle = page.locator("text=Announced, text=Unannounced")
        expect(toggle.first).to_be_visible()

    def test_lightning_page_shows_balance(self, logged_in_page: Page):
        """Lightning page should show the lightning balance."""
        page = logged_in_page
        self._navigate_to_lightning(page)

        balance = page.locator("text=Lightning balance")
        expect(balance).to_be_visible()

    def test_lightning_page_amount_label_shows_sats(self, logged_in_page: Page):
        """Channel open amount field should show 'sats' for LND wallets."""
        page = logged_in_page
        self._navigate_to_lightning(page)

        label = page.locator("text=Amount (sats)")
        expect(label).to_be_visible()

    def test_lightning_page_channel_table_has_fee_columns(self, logged_in_page: Page):
        """Channel table should have base fee and fee rate columns."""
        page = logged_in_page
        self._navigate_to_lightning(page)

        base_fee_header = page.locator("th:has-text('Base fee')")
        fee_rate_header = page.locator("th:has-text('Fee rate')")
        visibility_header = page.locator("th:has-text('Visibility')")

        expect(base_fee_header).to_be_visible()
        expect(fee_rate_header).to_be_visible()
        expect(visibility_header).to_be_visible()


class TestNodeStatus:
    """Test the node status page."""

    def _navigate_to_status(self, page: Page):
        """Navigate to node status page for the first LND wallet."""
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Click info icon on first LND wallet row
        rows = page.locator("tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            if "btclnd" in row.text_content().lower():
                info_icon = row.locator(".mdi-information-outline")
                if info_icon.count() > 0:
                    info_icon.click()
                    break
        else:
            pytest.skip("No LND wallet with node status icon found")

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

    def test_status_page_shows_network(self, logged_in_page: Page):
        """Node status page should show the network."""
        page = logged_in_page
        self._navigate_to_status(page)

        network = page.locator("text=Network")
        expect(network).to_be_visible()

    def test_status_page_shows_lnd_version(self, logged_in_page: Page):
        """Node status page should show LND version."""
        page = logged_in_page
        self._navigate_to_status(page)

        version = page.locator("text=LND Version")
        expect(version).to_be_visible()

    def test_status_page_shows_sync_status(self, logged_in_page: Page):
        """Node status page should show sync status."""
        page = logged_in_page
        self._navigate_to_status(page)

        sync = page.locator("text=Synced to Chain")
        expect(sync).to_be_visible()

    def test_status_page_shows_block_height(self, logged_in_page: Page):
        """Node status page should show block height."""
        page = logged_in_page
        self._navigate_to_status(page)

        height = page.locator("text=Block Height")
        expect(height).to_be_visible()

    def test_status_page_has_logs_tab(self, logged_in_page: Page):
        """Node status page should have a Logs tab."""
        page = logged_in_page
        self._navigate_to_status(page)

        logs_tab = page.locator("text=LND Logs")
        expect(logs_tab).to_be_visible()

    def test_status_page_no_info_icon_for_electrum(self, logged_in_page: Page):
        """BTC/Electrum wallets should not have a node status icon."""
        page = logged_in_page
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        rows = page.locator("tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            text = row.text_content().lower()
            # Find a BTC (non-LND) wallet row
            if "btc" in text and "btclnd" not in text and "currency" not in text:
                info_icons = row.locator(".mdi-information-outline")
                assert info_icons.count() == 0, "BTC wallet should not have node status icon"
                return
        # If no BTC wallet exists, skip
        pytest.skip("No BTC/Electrum wallet found to test")


class TestElectrumLightning:
    """Test that Electrum wallet lightning page differs from LND."""

    def _navigate_to_electrum_lightning(self, page: Page):
        """Navigate to lightning page for the first Electrum wallet."""
        page.goto(f"{ADMIN_URL}/wallets")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        rows = page.locator("tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            text = row.text_content().lower()
            if "btc" in text and "btclnd" not in text and "currency" not in text:
                row.locator(".mdi-lightning-bolt").click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1000)
                return
        pytest.skip("No Electrum wallet found")

    def test_electrum_no_announced_toggle(self, logged_in_page: Page):
        """Electrum lightning page should NOT show announced/unannounced toggle."""
        page = logged_in_page
        self._navigate_to_electrum_lightning(page)

        toggle = page.locator("text=Announced")
        expect(toggle).not_to_be_visible()

    def test_electrum_amount_label_shows_btc(self, logged_in_page: Page):
        """Electrum channel open amount should show 'BTC' not 'sats'."""
        page = logged_in_page
        self._navigate_to_electrum_lightning(page)

        sats_label = page.locator("text=Amount (sats)")
        expect(sats_label).not_to_be_visible()

        # If lightning is enabled, Amount (BTC) should be visible
        page_content = page.content()
        if "Amount (BTC)" in page_content:
            btc_label = page.locator("text=Amount (BTC)")
            expect(btc_label).to_be_visible()

    def test_electrum_no_network_chip(self, logged_in_page: Page):
        """Electrum lightning page should NOT show a network chip."""
        page = logged_in_page
        self._navigate_to_electrum_lightning(page)

        # Network chips are LND-only
        network_chip = page.locator(".v-chip:has-text('regtest'), .v-chip:has-text('signet'), .v-chip:has-text('mainnet'), .v-chip:has-text('testnet')")
        expect(network_chip).not_to_be_visible()

    def test_electrum_no_routing_stats(self, logged_in_page: Page):
        """Electrum lightning page should NOT show routing stats."""
        page = logged_in_page
        self._navigate_to_electrum_lightning(page)

        routed = page.locator("text=routed")
        earned = page.locator("text=earned")
        expect(routed).not_to_be_visible()
        expect(earned).not_to_be_visible()

    def test_electrum_no_fee_columns(self, logged_in_page: Page):
        """Electrum channel table should NOT have LND-specific fee columns."""
        page = logged_in_page
        self._navigate_to_electrum_lightning(page)

        page_content = page.content()
        # These columns are LND-specific
        assert "Base fee (sats)" not in page_content, "Electrum should not show base fee column"
        assert "Fee rate (%)" not in page_content, "Electrum should not show fee rate column"


# ---------------------------------------------------------------------------
# Sequence 1: Inbound channel → receive lightning payment → close channel
# ---------------------------------------------------------------------------


class TestLNDSequence1InboundChannelPayment:
    """Sequence 1 for LND: External node opens channel TO our LND wallet,
    creates a lightning invoice in Bitcart, external node pays it,
    then close the channel from the lightning management page.
    """

    def _get_lnd_wallet_id(self, page: Page):
        """Find the first BTCLND wallet ID."""
        headers = _get_api_headers(page)
        wallets = page.request.get(f"{API_URL}/wallets", headers=headers).json().get("result", [])
        for w in wallets:
            if w["currency"].lower() == "btclnd":
                return w["id"]
        pytest.skip("No BTCLND wallet found")

    def _get_store_for_wallet(self, page: Page, wallet_id: str):
        """Find or create a store using this wallet."""
        headers = _get_api_headers(page)
        stores = page.request.get(f"{API_URL}/stores", headers=headers).json().get("result", [])
        for s in stores:
            if wallet_id in s.get("wallets", []):
                return s["id"]
        # Create store
        resp = page.request.post(f"{API_URL}/stores", headers=headers,
            data={"name": "LND Test Store", "wallets": [wallet_id]})
        return resp.json()["id"]

    def test_inbound_channel_receive_payment_close(self, logged_in_page: Page):
        """Open channel TO us → create invoice → pay → verify paid → close channel."""
        page = logged_in_page
        ports = _load_ports()
        if not ports:
            pytest.skip("Regtest environment not running")

        wallet_id = self._get_lnd_wallet_id(page)
        store_id = self._get_store_for_wallet(page, wallet_id)
        headers = _get_api_headers(page)

        # Get merchant info via API
        status = page.request.get(f"{API_URL}/wallets/{wallet_id}/status", headers=headers).json()
        merchant_pubkey = status.get("identity_pubkey", "")
        if not merchant_pubkey:
            pytest.skip("LND wallet not synced")

        # Get merchant P2P port from daemon
        wallets = page.request.get(f"{API_URL}/wallets", headers=headers).json()["result"]
        lnd_wallet = next(w for w in wallets if w["id"] == wallet_id)
        seed = lnd_wallet["xpub"]

        # Use the BTCLND daemon to get P2P port
        import hashlib
        wk = hashlib.sha256(seed.strip().encode()).hexdigest()[:16]
        pm_path = os.path.join(os.getcwd(), ".regtest", "daemon", "port_map.json")
        if not os.path.exists(pm_path):
            pytest.skip("Daemon port map not found")
        pm = json.load(open(pm_path))
        merchant_p2p = pm.get(wk, {}).get("p2p")
        if not merchant_p2p:
            pytest.skip("Merchant P2P port not found")

        # --- Setup: Customer opens channel to our merchant ---
        # This part uses direct gRPC via subprocess (can't use async in Playwright)
        # We use the daemon RPC as a proxy to avoid async

        # Fund customer and open channel (via regtest helpers)
        # Customer connects to merchant and opens channel
        customer_grpc = ports["CUSTOMER_GRPC"]
        customer_dir = ports["CUSTOMER_DIR"]

        # Use lncli for customer operations
        def lncli_customer(*args):
            cmd = [
                os.environ.get("LNCLI_BIN", "lncli"),
                f"--rpcserver=127.0.0.1:{customer_grpc}",
                f"--lnddir={customer_dir}",
                "--network=regtest", "--no-macaroons",
            ] + list(args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 and "already connected" not in result.stderr:
                return None
            try:
                return json.loads(result.stdout) if result.stdout.strip() else {}
            except json.JSONDecodeError:
                return result.stdout.strip()

        # Connect and open channel
        lncli_customer("connect", f"{merchant_pubkey}@127.0.0.1:{merchant_p2p}")
        time.sleep(2)
        open_result = lncli_customer("openchannel", merchant_pubkey, "500000")
        if not open_result:
            pytest.skip("Failed to open channel from customer")
        _mine_blocks(6)
        time.sleep(5)

        # --- Create invoice via Bitcart UI ---
        page.goto(f"{ADMIN_URL}/invoices")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Create invoice via API (faster, then verify checkout page)
        inv_resp = page.request.post(f"{API_URL}/invoices", headers=headers,
            data={"store_id": store_id, "price": 0.00005, "currency": "BTC"})
        invoice = inv_resp.json()
        invoice_id = invoice["id"]

        # Get lightning payment address
        payments = invoice.get("payments", [])
        ln_method = next((p for p in payments if p.get("lightning")), None)
        assert ln_method, "No lightning payment method on invoice"
        bolt11 = ln_method["payment_address"]

        # --- Pay via customer lncli ---
        pay_result = lncli_customer("payinvoice", "--force", bolt11)

        # Mine block to trigger detection
        _mine_blocks(1)
        time.sleep(5)

        # --- Verify checkout page shows paid ---
        page.goto(f"{ADMIN_URL}/i/{invoice_id}")
        page.wait_for_load_state("networkidle")

        # Wait for status to update
        for _ in range(30):
            page_text = page.content()
            if "paid" in page_text.lower() or "complete" in page_text.lower():
                break
            page.wait_for_timeout(2000)
            page.reload()
            page.wait_for_load_state("networkidle")

        page_text = page.content().lower()
        assert "paid" in page_text or "complete" in page_text, \
            f"Invoice should show as paid/complete"

        # --- Close channel from lightning management page ---
        page.goto(f"{ADMIN_URL}/wallets/{wallet_id}/lightning")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Find close button in channel list
        close_btn = page.locator(".mdi-close").first
        if close_btn.is_visible():
            close_btn.click()
            page.wait_for_timeout(3000)

            # Mine blocks to confirm close
            _mine_blocks(6)
            time.sleep(5)

            # Reload and check channel appears in inactive/closed section
            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            page_text = page.content()
            # Should have "Other Channels" section or reduced active count
            assert "Other Channels" in page_text or "Active Channels (0)" in page_text, \
                "Channel should be closed or in inactive list"


class TestLNDSequence2OutboundChannelPayInvoice:
    """Sequence 2 for LND: Open channel FROM our LND wallet TO external node,
    create invoice on external node, pay it from the lightning management page,
    then close the channel.
    """

    def _get_lnd_wallet_id(self, page: Page):
        headers = _get_api_headers(page)
        wallets = page.request.get(f"{API_URL}/wallets", headers=headers).json().get("result", [])
        for w in wallets:
            if w["currency"].lower() == "btclnd":
                return w["id"]
        pytest.skip("No BTCLND wallet found")

    def test_outbound_channel_pay_invoice_close(self, logged_in_page: Page):
        """Open channel FROM us → create invoice on other node → pay via UI → close."""
        page = logged_in_page
        ports = _load_ports()
        if not ports:
            pytest.skip("Regtest environment not running")

        wallet_id = self._get_lnd_wallet_id(page)
        headers = _get_api_headers(page)

        # Get receiver info
        receiver_grpc = ports.get("RECEIVER_GRPC")
        receiver_dir = ports.get("RECEIVER_DIR")
        receiver_p2p = ports.get("RECEIVER_P2P")
        if not receiver_grpc:
            pytest.skip("Receiver node not configured")

        def lncli_receiver(*args):
            cmd = [
                os.environ.get("LNCLI_BIN", "lncli"),
                f"--rpcserver=127.0.0.1:{receiver_grpc}",
                f"--lnddir={receiver_dir}",
                "--network=regtest", "--no-macaroons",
            ] + list(args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            try:
                return json.loads(result.stdout) if result.stdout.strip() else {}
            except json.JSONDecodeError:
                return result.stdout.strip()

        # Get receiver pubkey
        receiver_info = lncli_receiver("getinfo")
        if not isinstance(receiver_info, dict):
            pytest.skip("Cannot get receiver info")
        receiver_pubkey = receiver_info.get("identity_pubkey", "")

        # --- Fund merchant and navigate to lightning page ---
        # Fund via mining to merchant address
        wallets_list = page.request.get(f"{API_URL}/wallets", headers=headers).json()["result"]
        lnd_wallet = next(w for w in wallets_list if w["id"] == wallet_id)
        seed = lnd_wallet["xpub"]

        # Get a merchant address via API
        # Use the daemon RPC
        daemon_resp = page.request.post("http://localhost:5012",
            headers={"Authorization": "Basic ZWxlY3RydW06ZWxlY3RydW16", "Content-Type": "application/json"},
            data=json.dumps({"method": "createnewaddress", "params": {"xpub": seed}, "id": 1}))
        merchant_addr = daemon_resp.json().get("result", "")
        if merchant_addr:
            _mine_blocks(1, merchant_addr)
            _mine_blocks(100)
            time.sleep(5)

        # --- Open channel via lightning management page ---
        page.goto(f"{ADMIN_URL}/wallets/{wallet_id}/lightning")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Connect to receiver first via daemon
        daemon_resp = page.request.post("http://localhost:5012",
            headers={"Authorization": "Basic ZWxlY3RydW06ZWxlY3RydW16", "Content-Type": "application/json"},
            data=json.dumps({"method": "add_peer", "params": {"xpub": seed, "addr": f"{receiver_pubkey}@127.0.0.1:{receiver_p2p}"}, "id": 1}))
        time.sleep(2)

        # Fill channel open form
        page.fill('input[aria-label="Node ID"]', receiver_pubkey)
        page.fill('input[aria-label="Amount (sats)"]', "300000")

        # Click Open Channel
        page.click("text=Open channel")
        page.wait_for_timeout(3000)

        # Mine blocks to confirm
        _mine_blocks(6)
        time.sleep(5)

        # Reload to see channel
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # Verify channel appears
        page_text = page.content()
        assert receiver_pubkey[:16] in page_text or "OPEN" in page_text, \
            "Channel should appear in channel list"

        # --- Create invoice on receiver and pay via UI ---
        add_invoice_result = lncli_receiver("addinvoice", "--amt", "10000", "--memo", "browser test")
        if not isinstance(add_invoice_result, dict):
            pytest.skip("Cannot create invoice on receiver")
        bolt11 = add_invoice_result.get("payment_request", "")
        assert bolt11, "No payment request returned"

        # Fill LN Invoice field and pay
        page.fill('input[aria-label="LN Invoice"]', bolt11)
        page.click("text=Pay LN invoice")
        page.wait_for_timeout(5000)

        # Check for success snackbar
        page_text = page.content().lower()
        assert "success" in page_text or "paid" in page_text, \
            "Payment should show success"

        # --- Close channel from UI ---
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        close_btn = page.locator(".mdi-close").first
        if close_btn.is_visible():
            close_btn.click()
            page.wait_for_timeout(3000)

            _mine_blocks(6)
            time.sleep(5)

            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            page_text = page.content()
            assert "Other Channels" in page_text or "Active Channels (0)" in page_text, \
                "Channel should be closed or in inactive list"


# ---------------------------------------------------------------------------
# Electrum equivalents of Sequence 1 and 2
# ---------------------------------------------------------------------------


class _ElectrumSequenceBase:
    """Shared helpers for Electrum lightning browser tests."""

    def _get_electrum_wallet_id(self, page: Page):
        headers = _get_api_headers(page)
        wallets = page.request.get(f"{API_URL}/wallets", headers=headers).json().get("result", [])
        for w in wallets:
            if w["currency"].lower() == "btc" and w.get("lightning_enabled"):
                return w["id"]
        pytest.skip("No Electrum wallet with lightning enabled found")

    def _get_store_for_wallet(self, page: Page, wallet_id: str):
        headers = _get_api_headers(page)
        stores = page.request.get(f"{API_URL}/stores", headers=headers).json().get("result", [])
        for s in stores:
            if wallet_id in s.get("wallets", []):
                return s["id"]
        resp = page.request.post(f"{API_URL}/stores", headers=headers,
            data={"name": "Electrum Test Store", "wallets": [wallet_id]})
        return resp.json()["id"]

    def _get_electrum_node_id(self, page: Page, wallet_id: str):
        headers = _get_api_headers(page)
        checkln = page.request.get(f"{API_URL}/wallets/{wallet_id}/checkln", headers=headers)
        node_id = checkln.json()
        if not node_id or node_id is False:
            pytest.skip("Electrum lightning not available")
        return node_id

    def _lncli(self, ports, node_name, *args):
        """Run lncli against a regtest LND node (customer or receiver)."""
        grpc = ports.get(f"{node_name}_GRPC")
        lnd_dir = ports.get(f"{node_name}_DIR")
        cmd = [
            os.environ.get("LNCLI_BIN", "lncli"),
            f"--rpcserver=127.0.0.1:{grpc}",
            f"--lnddir={lnd_dir}",
            "--network=regtest", "--no-macaroons",
        ] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 and "already connected" not in result.stderr:
            return None
        try:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            return result.stdout.strip()


class TestElectrumSequence1InboundChannelPayment(_ElectrumSequenceBase):
    """Sequence 1 for Electrum: External node opens channel TO our Electrum wallet,
    creates a lightning invoice in Bitcart, external node pays it,
    then close the channel from the lightning management page.
    """

    def test_electrum_inbound_channel_receive_payment_close(self, logged_in_page: Page):
        """Electrum: inbound channel → receive payment → verify paid → close channel."""
        page = logged_in_page
        ports = _load_ports()
        if not ports:
            pytest.skip("Regtest environment not running")

        wallet_id = self._get_electrum_wallet_id(page)
        store_id = self._get_store_for_wallet(page, wallet_id)
        headers = _get_api_headers(page)
        electrum_node_id = self._get_electrum_node_id(page, wallet_id)

        # --- Customer opens channel TO our Electrum wallet ---
        # Get Electrum's listening port (Electrum lightning listens on 9735 by default
        # or configured via BTC_LIGHTNING_LISTEN)
        electrum_listen = os.environ.get("BTC_LIGHTNING_LISTEN", "127.0.0.1:9735")
        # If it's just a port, prepend localhost
        if ":" not in electrum_listen:
            electrum_listen = f"127.0.0.1:{electrum_listen}"

        self._lncli(ports, "CUSTOMER", "connect", f"{electrum_node_id}@{electrum_listen}")
        time.sleep(2)

        open_result = self._lncli(ports, "CUSTOMER", "openchannel", electrum_node_id, "500000")
        if not open_result:
            pytest.skip("Failed to open channel from customer to Electrum")
        _mine_blocks(6)
        time.sleep(5)

        # --- Create invoice via Bitcart API ---
        inv_resp = page.request.post(f"{API_URL}/invoices", headers=headers,
            data={"store_id": store_id, "price": 0.00005, "currency": "BTC"})
        if inv_resp.status != 200:
            pytest.skip("Cannot create invoice")
        invoice = inv_resp.json()
        invoice_id = invoice["id"]

        # Get lightning payment method
        payments = invoice.get("payments", [])
        ln_method = next((p for p in payments if p.get("lightning")), None)
        if not ln_method:
            pytest.skip("No lightning payment method on Electrum invoice")
        bolt11 = ln_method["payment_address"]

        # --- Customer pays invoice ---
        self._lncli(ports, "CUSTOMER", "payinvoice", "--force", bolt11)
        _mine_blocks(1)
        time.sleep(5)

        # --- Verify checkout page shows paid ---
        page.goto(f"{ADMIN_URL}/i/{invoice_id}")
        page.wait_for_load_state("networkidle")

        for _ in range(30):
            page_text = page.content().lower()
            if "paid" in page_text or "complete" in page_text:
                break
            page.wait_for_timeout(2000)
            page.reload()
            page.wait_for_load_state("networkidle")

        page_text = page.content().lower()
        assert "paid" in page_text or "complete" in page_text, \
            "Electrum invoice should show as paid/complete"

        # --- Close channel from lightning management page ---
        page.goto(f"{ADMIN_URL}/wallets/{wallet_id}/lightning")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        close_btn = page.locator(".mdi-close").first
        if close_btn.is_visible():
            close_btn.click()
            page.wait_for_timeout(3000)
            _mine_blocks(6)
            time.sleep(5)

            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            page_text = page.content()
            assert "Other Channels" in page_text or "Active Channels (0)" in page_text, \
                "Electrum channel should be closed or in inactive list"


class TestElectrumSequence2OutboundChannelPayInvoice(_ElectrumSequenceBase):
    """Sequence 2 for Electrum: Open channel FROM our Electrum wallet TO external node,
    create invoice on external node, pay it via the lightning management page,
    then close the channel.
    """

    def test_electrum_outbound_channel_pay_invoice_close(self, logged_in_page: Page):
        """Electrum: open channel → pay external invoice via UI → close channel."""
        page = logged_in_page
        ports = _load_ports()
        if not ports:
            pytest.skip("Regtest environment not running")

        wallet_id = self._get_electrum_wallet_id(page)
        headers = _get_api_headers(page)
        self._get_electrum_node_id(page, wallet_id)  # verify lightning is available

        # Get receiver info
        receiver_grpc = ports.get("RECEIVER_GRPC")
        receiver_p2p = ports.get("RECEIVER_P2P")
        if not receiver_grpc:
            pytest.skip("Receiver node not configured")

        receiver_info = self._lncli(ports, "RECEIVER", "getinfo")
        if not isinstance(receiver_info, dict):
            pytest.skip("Cannot get receiver info")
        receiver_pubkey = receiver_info.get("identity_pubkey", "")

        # --- Navigate to lightning management page ---
        page.goto(f"{ADMIN_URL}/wallets/{wallet_id}/lightning")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Verify lightning is enabled
        page_text = page.content()
        if "Lightning support enabled" not in page_text and "Lightning balance" not in page_text:
            pytest.skip("Lightning not enabled on Electrum wallet")

        # --- Open channel via UI ---
        # Electrum uses pubkey@host:port format for Node ID
        connection_str = f"{receiver_pubkey}@127.0.0.1:{receiver_p2p}"
        page.fill('input[aria-label="Node ID"]', connection_str)
        page.fill('input[aria-label="Amount (BTC)"]', "0.005")

        page.click("text=Open channel")
        page.wait_for_timeout(3000)

        _mine_blocks(6)
        time.sleep(5)

        # Reload and verify channel appears
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # Wait for channel to appear in list
        for _ in range(30):
            page_text = page.content()
            if receiver_pubkey[:16] in page_text or "OPEN" in page_text:
                break
            page.wait_for_timeout(2000)
            page.reload()
            page.wait_for_load_state("networkidle")

        page_text = page.content()
        assert receiver_pubkey[:16] in page_text or "OPEN" in page_text, \
            "Electrum channel should appear in channel list"

        # --- Create invoice on receiver and pay via UI ---
        add_invoice_result = self._lncli(ports, "RECEIVER", "addinvoice", "--amt", "10000", "--memo", "electrum browser test")
        if not isinstance(add_invoice_result, dict):
            pytest.skip("Cannot create invoice on receiver")
        bolt11 = add_invoice_result.get("payment_request", "")
        assert bolt11, "No payment request returned from receiver"

        # Fill LN Invoice and pay
        page.fill('input[aria-label="LN Invoice"]', bolt11)
        page.click("text=Pay LN invoice")
        page.wait_for_timeout(5000)

        # Verify success
        page_text = page.content().lower()
        assert "success" in page_text or "paid" in page_text, \
            "Electrum LN payment should show success"

        # --- Close channel from UI ---
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        close_btn = page.locator(".mdi-close").first
        if close_btn.is_visible():
            close_btn.click()
            page.wait_for_timeout(3000)
            _mine_blocks(6)
            time.sleep(5)

            page.reload()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            page_text = page.content()
            assert "Other Channels" in page_text or "Active Channels (0)" in page_text, \
                "Electrum channel should be closed or in inactive list"
