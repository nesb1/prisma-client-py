from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Union
from functools import lru_cache

import tomlkit
from pydantic import BaseSettings, Extra, Field

if TYPE_CHECKING:
    from pydantic.env_settings import SettingsSourceCallable


class DefaultConfig(BaseSettings):
    # CLI version
    # TODO: if this version changes but the engine version
    #       doesn't change then the CLI is incorrectly cached
    prisma_version: str = '3.13.0'

    # Engine binary versions can be found under https://github.com/prisma/prisma-engine/commits/main
    engine_version: str = Field(
        env='PRISMA_ENGINE_VERSION',
        default='efdf9b1183dddfd4258cd181a72125755215ab7b',
    )

    # CLI binaries are stored here
    prisma_url: str = Field(
        env='PRISMA_CLI_URL',
        default='https://prisma-photongo.s3-eu-west-1.amazonaws.com/prisma-cli-{version}-{platform}.gz',
    )

    # Engine binaries are stored here
    engine_url: str = Field(
        env='PRISMA_ENGINE_URL',
        default='https://binaries.prisma.sh/all_commits/{0}/{1}/{2}.gz',
    )

    # Where to store the downloaded binaries
    binary_cache_dir: Union[Path, None] = Field(
        env='PRISMA_BINARY_CACHE_DIR',
        default=None,
    )

    class Config(BaseSettings.Config):
        extra: Extra = Extra.ignore

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            # prioritise env settings over init settings
            return env_settings, init_settings, file_secret_settings


class Config(DefaultConfig):
    binary_cache_dir: Path

    @classmethod
    def from_base(cls, config: DefaultConfig) -> Config:
        if config.binary_cache_dir is None:
            config.binary_cache_dir = (
                Path(tempfile.gettempdir())
                / 'prisma'
                / 'binaries'
                / 'engines'
                / config.engine_version
            )

        return cls.parse_obj(config.dict())

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        if path is None:
            path = Path('pyproject.toml')

        if path.exists():
            config = (
                tomlkit.loads(path.read_text())
                .get('tool', {})
                .get('prisma', {})
            )
        else:
            config = {}

        return cls.from_base(DefaultConfig.parse_obj(config))


# TODO: ensure things like __name__, __dir__ are proxied correctly
class LazyConfigProxy:
    def __getattr__(self, attr: str) -> object:
        return getattr(self.__get_proxied(), attr)

    @lru_cache(maxsize=None)
    def __get_proxied(self) -> Config:
        return Config.load()

    def __repr__(self) -> str:
        return repr(self.__get_proxied())

    def __str__(self) -> str:
        return str(self.__get_proxied())
