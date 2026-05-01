from typing import Callable, Type, cast

from fastapi import FastAPI, Request

from app.setups.base import DependencySetup


class DependencyInjector:
    """DI engine: builds a registry from a Setup and provides dependencies to routes."""

    def __init__(self, setup: DependencySetup) -> None:
        self._setup = setup
        self._registry: dict[type, object] = {
            t: next(v for v in vars(setup).values() if isinstance(v, t))
            for t in setup.INJECTABLE
        }

    def inject(self, app: FastAPI) -> None:
        app.state.deps = self

    @staticmethod
    def load(request: Request) -> "DependencyInjector":
        return cast(DependencyInjector, request.app.state.deps)

    @classmethod
    def provide[T](cls, service_type: Type[T]) -> Callable[[Request], T]:
        def _load(request: Request) -> T:
            injector = DependencyInjector.load(request)
            service = injector._registry.get(service_type)
            if service is None:
                raise RuntimeError(
                    f"{service_type.__name__} not found in setup container. Did you register it via INJECTABLE?"
                )
            return cast(T, service)

        return _load

    async def init(self) -> None:
        await self._setup.init()

    async def dispose(self) -> None:
        await self._setup.dispose()
