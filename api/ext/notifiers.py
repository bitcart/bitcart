def parse_notifier_schema(schema):
    return list(filter(lambda x: x != "message" and not schema["properties"][x].get("duplicate"), schema["properties"].keys()))
