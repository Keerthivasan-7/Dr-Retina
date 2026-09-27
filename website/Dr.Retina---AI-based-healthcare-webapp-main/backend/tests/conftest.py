import pytest

from app.runtime import loop_factory


@pytest.fixture(scope="session")
def _asyncio_loop_factory():
    # Factory fixture provided by our locked pytest-asyncio version.
    return loop_factory
