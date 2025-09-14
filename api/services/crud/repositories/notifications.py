from api import models
from api.services.crud import CRUDRepository


class NotificationRepository(CRUDRepository[models.Notification]):
    model_type = models.Notification
