from apprise import Apprise

USELESS_PARAMS = ["rto", "cto", "overflow", "verify", "emojis", "image"]


def all_notifers():
    return Apprise().details("en")["schemas"]


def get_notifier(name):
    res = list(filter(lambda x: str(x["service_name"]) == name, all_notifers()))
    return None if not res else res[0]


def merge_details(schema):
    a = schema["details"]["args"]
    a.update(schema["details"]["tokens"])
    return a


def prepare_param(kv, need_required):
    return kv[0] if need_required else {"key": kv[0], "name": kv[1].get("name", kv[0]), "type": kv[1].get("type", "string")}


def get_params(schema, need_required=False):
    in_group = set()

    list_of_sets = [
        x[1]["group"]
        for x in filter(
            lambda kv: "group" in kv[1],
            merge_details(schema).items(),
        )
    ]
    for s in list_of_sets:
        in_group |= s
    return [
        prepare_param(x, need_required)
        for x in filter(
            lambda kv: kv[0] != "schema"
            and "required" in kv[1]
            and (kv[1]["required"] or not need_required or kv[0] == "targets")
            and "alias_of" not in kv[1]
            and kv[0] not in in_group
            and kv[0] not in USELESS_PARAMS,
            merge_details(schema).items(),
        )
    ]
