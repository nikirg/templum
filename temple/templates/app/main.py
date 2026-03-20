from fastapi.concurrency import asynccontextmanager
from fastapi import FastAPI

from loguru import logger

from app.config import Config
from app.deps import DependencyInjector
from app.auth import build_auth_dependency

config = Config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup = config.build_setup()
    deps = DependencyInjector(setup)
    deps.inject(app)
    await deps.init()
    yield
    await deps.dispose()


app_deps = []

if config.APP_AUTH_TOKEN:
    app_deps.append(build_auth_dependency(config.APP_AUTH_TOKEN.get_secret_value()))
else:
    logger.warning(
        "APP_AUTH_TOKEN is not set. If you deploy this in production, you should set it."
    )


app = FastAPI(lifespan=lifespan, title=config.APP_NAME, dependencies=app_deps)

# app.include_router(...)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=config.APP_PORT)
