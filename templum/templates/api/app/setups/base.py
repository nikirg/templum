from abc import ABC


class DependencySetup(ABC):
    """Base class for defining dependencies and their lifecycle."""

    INJECTABLE: tuple[type, ...] = ()

    async def init(self) -> None:
        pass

    async def dispose(self) -> None:
        pass
