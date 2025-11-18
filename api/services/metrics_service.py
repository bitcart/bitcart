from api.db import AsyncSession


class MetricsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate_metrics(self) -> None:
        pass
