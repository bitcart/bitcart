import csv
import io
from collections.abc import Generator
from typing import Any, cast

from api import models
from api.schemas.invoices import DisplayInvoice


def merge_keys(k1: str | None, k2: str | None) -> str | None:
    return f"{k1}_{k2}" if k1 is not None and k2 is not None else k1 if k1 is not None else k2


def process_invoice(invoice: dict[str, Any], add_payments: bool = False) -> dict[str, Any]:
    if not add_payments:
        invoice.pop("payments", None)
    return invoice


def db_to_json(data: list[models.Invoice], add_payments: bool = False) -> Generator[dict[str, Any], None, None]:
    return (process_invoice(DisplayInvoice.model_validate(x).model_dump(), add_payments) for x in data)


def get_leaves(item: Any, key: str | None = None) -> dict[str, Any]:  # pragma: no cover
    if isinstance(item, list) and key is not None and key != "payments":
        return {key: "[" + ",".join(map(str, item)) + "]"}
    if isinstance(item, dict):
        leaves = {}
        for i in item:
            leaves.update(get_leaves(item[i], merge_keys(key, i)))
        return leaves
    if isinstance(item, list):
        leaves = {}
        for index, i in enumerate(item):
            leaves.update(get_leaves(i, merge_keys(key, str(index))))
        return leaves
    return {cast(str, key): item}


def json_to_csv(json_data: list[dict[str, Any]]) -> io.StringIO:
    result = io.StringIO()
    # First parse all entries to get the complete fieldname list
    fieldnames: set[str] = set()
    rows = [get_leaves(entry) for entry in json_data]
    for row in rows:
        fieldnames.update(row.keys())

    csv_output = csv.DictWriter(result, fieldnames=sorted(fieldnames))
    csv_output.writeheader()
    csv_output.writerows(rows)
    return result
