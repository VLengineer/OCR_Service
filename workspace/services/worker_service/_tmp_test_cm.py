import asyncio
from unittest.mock import AsyncMock

class _MockSessionContextManager:
    def __init__(self, session):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, exc_type, exc, tb):
        return False

async def async_session_factory():
    return _MockSessionContextManager(AsyncMock())

async def main():
    cm1 = await async_session_factory()
    print(type(cm1), hasattr(cm1, '__aenter__'))
    async with cm1 as s1:
        print('entered', s1)
    print('exit done')

asyncio.run(main())
