import signal
import time

import pytest
from starlette.testclient import TestClient

from tests.functional import utils


@pytest.fixture
def worker():
    process = utils.start_worker()
    yield
    process.send_signal(signal.SIGINT)
    process.wait()


def test_pay_flow(client: TestClient, invoice, worker):
    pay_details = invoice["payments"][0]
    address = pay_details["payment_address"]
    amount = pay_details["amount"]
    utils.run_shell(["sendtoaddress", address, amount])
    utils.run_shell(["newblocks", "3"])
    time.sleep(10)  # TODO: find a better way
    invoice_id = invoice["id"]
    resp = client.get(f"/invoices/{invoice_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"
