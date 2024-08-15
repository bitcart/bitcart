import csv
import io

from api.schemes import DisplayInvoice


def merge_keys(k1, k2):
    return f"{k1}_{k2}" if k1 is not None and k2 is not None else k1 if k1 is not None else k2


def process_invoice(invoice, add_payments=False):
    if not add_payments:
        invoice.pop("payments", None)
    return invoice


def db_to_json(data, add_payments=False):
    return map(lambda x: process_invoice(DisplayInvoice.model_validate(x).model_dump(), add_payments), data)


def get_leaves(item, key=None):  # pragma: no cover
    if isinstance(item, list) and key is not None and key != "payments":
        return {key: "[" + ",".join(map(str, item)) + "]"}
    elif isinstance(item, dict):
        leaves = {}
        for i in item.keys():
            leaves.update(get_leaves(item[i], merge_keys(key, i)))
        return leaves
    elif isinstance(item, list):
        leaves = {}
        for index, i in enumerate(item):
            leaves.update(get_leaves(i, merge_keys(key, index)))
        return leaves
    else:
        return {key: item}


def json_to_csv(json_data):
    result = io.StringIO()
    # First parse all entries to get the complete fieldname list
    fieldnames = set()
    rows = [get_leaves(entry) for entry in json_data]
    for row in rows:
        fieldnames.update(row.keys())

    csv_output = csv.DictWriter(result, fieldnames=sorted(fieldnames))
    csv_output.writeheader()
    csv_output.writerows(rows)
    return result
