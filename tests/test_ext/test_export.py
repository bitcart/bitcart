import io
from typing import Any

import pytest
from dishka import Scope
from fastapi import FastAPI

from api.ext.export import db_to_json, json_to_csv, merge_keys
from api.services.crud.invoices import InvoiceService


def test_merge_keys() -> None:
    assert merge_keys(None, "test") == "test"
    assert merge_keys("test", None) == "test"
    assert merge_keys("test", "test") == "test_test"


@pytest.mark.anyio
async def test_invoice_db_to_json(app: FastAPI, invoice: dict[str, Any]) -> None:
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        invoice_service = await container.get(InvoiceService)
        items, _ = await invoice_service.list_and_count()
    json = list(db_to_json(items))
    assert len(json) == 1
    assert isinstance(json[0], dict)


def test_json_to_csv() -> None:
    converted = json_to_csv([{"test": 1, "list": [1, 2, 3], "obj": {"obj2": {"field": 4}}}])
    assert isinstance(converted, io.StringIO)
    value = converted.getvalue()
    assert value.strip() == 'list,obj_obj2_field,test\r\n"[1,2,3]",4,1'
