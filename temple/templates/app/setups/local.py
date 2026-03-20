from app.config import Config
from app.setups.base import DependencySetup


class LocalSetup(DependencySetup):
    INJECTABLE = ()

    def __init__(self, config: Config) -> None:
        pass

    async def init(self) -> None:
        pass

    async def dispose(self) -> None:
        pass
