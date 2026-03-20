from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.setups.base import DependencySetup


class Setup(StrEnum):
    LOCAL = "local"


class Config(BaseSettings):
    APP_PORT: int = 8000
    APP_NAME: str = "{{project_name}}"
    APP_AUTH_TOKEN: SecretStr | None = None
    APP_SETUP: Setup = Setup.LOCAL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    def build_setup(self) -> "DependencySetup":
        match self.APP_SETUP:
            case Setup.LOCAL:
                from app.setups.local import LocalSetup

                return LocalSetup(self)
