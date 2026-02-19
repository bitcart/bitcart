VERSION = "0.10.2.0"  # Version, used for openapi schemas and update checks


def append_otel_version() -> None:
    import os

    resource_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    version_attr = f"service.version={VERSION}"
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"{resource_attrs},{version_attr}" if resource_attrs else version_attr
