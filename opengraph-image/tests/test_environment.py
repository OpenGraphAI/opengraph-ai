"""Importing the library must not change the caller's environment."""

import subprocess
import sys

import pytest

_LIBRARY_MODULES = ["opengraph_image.extract", "opengraph_image.graph", "opengraph_image.query"]

# Runs in a fresh interpreter so the import is real and no module is reloaded here.
_PROBE = """
import dotenv
calls = []
dotenv.load_dotenv = lambda *args, **kwargs: calls.append(args) or True
import {module}
print(len(calls))
"""


@pytest.mark.parametrize("module_name", _LIBRARY_MODULES)
def test_importing_a_library_module_does_not_load_dotenv(module_name: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(module=module_name)],
        capture_output=True, text=True, check=True,
    )

    assert result.stdout.strip() == "0"
