"""Load the provider modules without Home Assistant or aiohttp installed.

The providers only need aiohttp for typing and the HTTP helpers, which these
parser tests never call. The integration package itself imports Home Assistant,
so it is registered as a bare namespace to skip its __init__.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "be_health_status"
FIXTURES = Path(__file__).parent / "fixtures"

if "aiohttp" not in sys.modules:
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        stub = types.ModuleType("aiohttp")

        class ClientTimeout:  # noqa: D101
            def __init__(self, total=None):
                self.total = total

        class ClientError(Exception):
            """Stub."""

        stub.ClientTimeout = ClientTimeout
        stub.ClientError = ClientError
        stub.ClientSession = object
        sys.modules["aiohttp"] = stub

sys.path.insert(0, str(ROOT))
for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.be_health_status", PKG_DIR),
):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = [str(path)]
        sys.modules[name] = mod


@pytest.fixture
def load_json():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def load_text():
    def _load(name: str):
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _load
