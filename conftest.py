import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _cache_limpo():
    """O limite de pedidos do RF03 usa o cache: sem isto, um teste herdaria o bloqueio do anterior."""
    cache.clear()
