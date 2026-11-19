import ast

import pytest

from tests.architecture.source import APP_DIR, imported_modules, python_files

# The bottom layers import nothing from the layers above them. app/utils may import app/core.
UPPER_LAYERS = ("app.api", "app.features", "app.integrations", "app.main", "app.models", "app.services", "app.workers")
# Shared services and integrations serve each feature, so they import no feature.
ENTRY_LAYERS = ("app.api", "app.features", "app.main", "app.models", "app.workers")
FORBIDDEN_IMPORTS = {
    "core": UPPER_LAYERS,
    "utils": UPPER_LAYERS,
    "services": ENTRY_LAYERS,
    "integrations": ENTRY_LAYERS,
}
# Inside a feature, imports go down: routes, dependencies, services, repository, models.
HTTP_MODULES = ("routes", "ai_routes", "dependencies")
FEATURE_FORBIDDEN = {
    "services": HTTP_MODULES,
    "agents": HTTP_MODULES,
    "repository.py": (*HTTP_MODULES, "services", "agents"),
    "models.py": (*HTTP_MODULES, "services", "agents", "repository"),
}


def _in_package(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def _forbidden(path: str, module: str) -> bool:
    # path is relative to app/, for example "features/items/repository.py".
    layer, *rest = path.split("/")
    if layer in FORBIDDEN_IMPORTS:
        return any(_in_package(module, package) for package in FORBIDDEN_IMPORTS[layer])
    part = rest[1] if layer == "features" and len(rest) > 1 else ""
    target = module.split(".")
    return target[:2] == ["app", "features"] and len(target) > 3 and target[3] in FEATURE_FORBIDDEN.get(part, ())


def _layer_problems(path: str, source: str) -> list[str]:
    # One problem for each import statement, also when it names several modules.
    return [
        f"{node.lineno}: {module}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        and (module := next((name for name in imported_modules(node) if _forbidden(path, name)), None))
    ]


@pytest.mark.parametrize(
    ("path", "source", "expected"),
    [
        ("core/config.py", "from app.features.items.models import Item", ["1: app.features.items.models"]),
        ("core/config.py", "def f():\n    import app.workers.enqueue", ["2: app.workers.enqueue"]),
        ("core/config.py", "from app import features", ["1: app.features"]),
        ("core/config.py", "import app.apiary", []),
        ("utils/time.py", "from app.core.config import api_config", []),
        ("services/base.py", "from app.features.items import repository", ["1: app.features.items"]),
        ("integrations/sentry/client.py", "from app.workers.celery import celery", ["1: app.workers.celery"]),
        ("integrations/sentry/client.py", "from app.services.base import Service", []),
        (
            "features/items/services/create.py",
            "from app.features.items import routes",
            ["1: app.features.items.routes"],
        ),
        (
            "features/items/services/create.py",
            "import app.features.users.dependencies",
            ["1: app.features.users.dependencies"],
        ),
        (
            "features/items/agents/summarizer.py",
            "from app.features.items.ai_routes import router",
            ["1: app.features.items.ai_routes"],
        ),
        (
            "features/items/repository.py",
            "from app.features.items.services.create import CreateItem",
            ["1: app.features.items.services.create"],
        ),
        ("features/items/models.py", "from app.features.items import repository", ["1: app.features.items.repository"]),
        ("features/items/services/create.py", "from app.features.items import repository", []),
        ("features/items/routes.py", "from app.features.items.services.create import CreateItem", []),
        ("workers/registry.py", "from app.features.items.services.summarize import SummarizeItemService", []),
    ],
    ids=[
        "core_imports_a_feature",
        "import_in_a_function_body",
        "package_import_of_features",
        "name_that_only_starts_like_a_layer",
        "utils_imports_core",
        "shared_service_imports_a_feature",
        "integration_imports_workers",
        "integration_imports_a_shared_service",
        "service_imports_routes",
        "service_imports_dependencies_of_another_feature",
        "agent_imports_ai_routes",
        "repository_imports_a_service",
        "model_imports_the_repository",
        "service_imports_the_repository",
        "routes_import_a_service",
        "worker_imports_a_service",
    ],
)
def test_finds_imports_against_the_layer_direction(path: str, source: str, expected: list[str]):
    assert _layer_problems(path, source) == expected


def test_imports_follow_the_layer_direction():
    offenders = []
    for file in python_files(APP_DIR):
        relative = file.relative_to(APP_DIR).as_posix()
        offenders += [f"app/{relative}:{problem}" for problem in _layer_problems(relative, file.read_text())]
    assert offenders == [], (
        "Move the shared code down a layer: routes -> dependencies -> services -> repository -> models. "
        "app/core and app/utils import no upper layer."
    )
