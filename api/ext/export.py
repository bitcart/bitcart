import csv
import io

from api.schemes import DisplayInvoice


def merge_keys(k1, k2):
    return f"{k1}_{k2}" if k1 and k2 else k1 or k2


def db_to_json(data):
    return map(lambda x: DisplayInvoice.from_orm(x).dict(), data)


def get_leaves(item, key=None):
    if isinstance(item, dict):
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
