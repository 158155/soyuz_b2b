import pytest

from app.config import get_openai_client, get_settings


@pytest.fixture(autouse=True)
def _clear_caches():
    get_settings.cache_clear()
    get_openai_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_openai_client.cache_clear()
