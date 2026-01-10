import os

if os.getenv("BITCART_OTEL_ENABLED", "false").lower() == "true":
    from opentelemetry.instrumentation.auto_instrumentation import initialize

    initialize()


from api.bootstrap import configure_production_app

app = configure_production_app()
