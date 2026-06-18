"""Guard test: the carbon-aware example service imports and wires its routes.

Loaded from its file (examples/ isn't a package). Building the app is network-free --
the middleware and SDK client only fetch on a real request, not at import.
"""

import importlib.util


def _load_example():
    spec = importlib.util.spec_from_file_location(
        "carbon_aware_example", "examples/carbon-aware-service/app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_app_wires_its_routes():
    module = _load_example()
    paths = {route.path for route in module.app.routes}
    assert {"/infer", "/media", "/recommendations"} <= paths
