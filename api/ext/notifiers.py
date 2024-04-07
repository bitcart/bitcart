from apprise import Apprise


def all_notifers():
    return Apprise().details()["schemas"]


def get_notifier(name):
    res = list(filter(lambda x: x["service_name"] == name, all_notifers()))
    return None if not res else res[0]


def merge_details(schema):
    a = schema["details"]["args"]
    a.update(schema["details"]["tokens"])
    return a


def get_params(schema, need_required=False):
    in_group = set()

    list_of_sets = list(
        map(
            lambda x: x[1]["group"],
            filter(
                lambda kv: "group" in kv[1],
                merge_details(schema).items(),
            ),
        )
    )
    for s in list_of_sets:
        in_group |= s
    return list(
        map(
            lambda x: x[0],
            filter(
                lambda kv: kv[0] != "schema"
                and "required" in kv[1]
                and (kv[1]["required"] or not need_required)
                and "alias_of" not in kv[1]
                and kv[0] not in in_group,
                merge_details(schema).items(),
            ),
        )
    )
