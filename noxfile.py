from enum import Enum, auto
from functools import partial
from typing import Set, Dict, Any
from typing_extensions import TypedDict, Literal

import nox
from pydantic import BaseModel

from prisma.generator import render_template
from prisma.generator.models import raise_err
from prisma.generator.utils import resolve_template_path


# TODO: split this up properly
# TODO: add reuse_venv ?


class Feature(Enum):
    enum = auto()
    json = auto()
    arrays = auto()
    create_many = auto()
    case_sensitivity = auto()


class Defaults(BaseModel):
    case_sensitive_filtering: bool


class DatabaseConfig(TypedDict):
    disable_features: Set[Feature]
    defaults: Defaults


CONFIG: Dict[str, DatabaseConfig] = {
    'postgresql': {
        'disable_features': set(),
        'defaults': Defaults(
            case_sensitive_filtering=True,
        ),
    },
    'sqlite': {
        'disable_features': {
            Feature.enum,
            Feature.json,
            Feature.arrays,
            Feature.create_many,
            Feature.case_sensitivity,
        },
        'defaults': Defaults(
            case_sensitive_filtering=False,
        ),
    },
}
TEMPLATE_TO_FEATURE = {
    'base/test_enums.py.jinja': Feature.enum,
    'base/test_arrays.py.jinja': Feature.arrays,
    'base/test_create_many.py.jinja': Feature.create_many,
    'base/test_case_sensitivity.py.jinja': Feature.case_sensitivity,
    'base/types/test_json.py.jinja': Feature.json,
}


@nox.session
def postgresql(session: nox.Session) -> None:
    # TODO: ensure templates up to date
    session.install('-r', 'databases/requirements.txt')
    session.install('.')

    with session.chdir('databases/postgresql'):
        session.run(
            'prisma', 'db', 'push', '--accept-data-loss', '--force-reset'
        )
        session.run(
            'coverage',
            'run',
            '-m',
            'pytest',
            '--confcutdir=.',
            *session.posargs,
        )

        # TODO: ensure this is running in strict mode
        session.run('pyright', '.')


@nox.session
def sqlite(session: nox.Session) -> None:
    # TODO: ensure templates up to date
    session.install('-r', 'databases/requirements.txt')
    session.install('.')

    with session.chdir('databases/sqlite'):
        session.run(
            'prisma', 'db', 'push', '--accept-data-loss', '--force-reset'
        )
        session.run(
            'coverage',
            'run',
            '-m',
            'pytest',
            '--confcutdir=.',
            *session.posargs,
        )

        # TODO: ensure this is running in strict mode
        session.run('pyright', '.')


@nox.session
def databases(session: nox.Session) -> None:
    with session.chdir('databases'):
        generate('postgresql')
        generate('sqlite')


# TODO: add tests that the templates are all included


from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


def generate(target: Literal['postgresql', 'sqlite']) -> None:
    config = CONFIG.get(target)
    if config is None:
        raise RuntimeError(f'No database config for {target}')

    disabled = config['disable_features']

    output_dir = Path.cwd()
    env = Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        loader=FileSystemLoader(Path.cwd() / 'templates'),
    )

    # utility functions
    params: Dict[str, Any] = {
        name: func
        for name, func in [
            ('raise_err', raise_err),
            ('has_feature', partial(has_feature, config)),
        ]
    }
    params['config'] = config

    for template in env.list_templates():
        # TODO: cleanup
        # TODO: switch back to filter_func ?
        if template.startswith('base'):
            name = template.replace('base', target, 1)

            try:
                env.get_template(name)
            except TemplateNotFound:
                file = resolve_template_path(Path.cwd(), name)
            else:
                continue

            feature = TEMPLATE_TO_FEATURE.get(template)
            if feature is not None and feature in disabled:
                continue
        elif template.startswith(target):
            file = resolve_template_path(Path.cwd(), template)
        else:
            continue

        render_template(
            output_dir,
            template,
            env=env,
            params=params,
            file=file,
        )


def has_feature(config: DatabaseConfig, feature: str) -> bool:
    enum = getattr(Feature, feature)
    return enum not in config['disable_features']