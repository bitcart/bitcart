import os

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Request, Response, Security
from prometheus_client import CollectorRegistry, multiprocess
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST, generate_latest

from api import models, utils
from api.constants import AuthScopes
from api.services.metrics_service import MetricsService

router = APIRouter(route_class=DishkaRoute)


@router.get("/metrics", include_in_schema=False)
async def metrics(
    request: Request,
    metrics_service: FromDishka[MetricsService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.METRICS_MANAGEMENT]),
) -> Response:
    await metrics_service.calculate_metrics()
    ephemeral_registry = request.app.state.instrumentator.registry
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        ephemeral_registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(ephemeral_registry)
    return Response(content=generate_latest(ephemeral_registry), media_type=CONTENT_TYPE_LATEST)
