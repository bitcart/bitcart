import os

if os.getenv("OTEL_AUTO_INSTRUMENT_APP", "false").lower() == "true":
    from opentelemetry.instrumentation.auto_instrumentation import initialize

    initialize()


from api.bootstrap import configure_production_app

app = configure_production_app()
