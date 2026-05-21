import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def setup_telemetry(app: object, settings: object, engine: object | None = None) -> None:
    """Configure OpenTelemetry tracing, metrics, and logging."""
    # Import here to avoid circular imports at module level
    from deploytracker.infrastructure.config import Settings

    if not isinstance(settings, Settings):
        raise TypeError("settings must be a Settings instance")

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.env,
        }
    )

    # Tracing
    tracer_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_exporter = OTLPMetricExporter(endpoint=settings.otlp_endpoint, insecure=True)
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=30_000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Logging
    LoggingInstrumentor().instrument(set_logging_format=True)

    # FastAPI auto-instrumentation
    FastAPIInstrumentor.instrument_app(app)

    # SQLAlchemy auto-instrumentation (only if engine is provided)
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine)

    logger.info("OpenTelemetry configured", extra={"otlp_endpoint": settings.otlp_endpoint})
