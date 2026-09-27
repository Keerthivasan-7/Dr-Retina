import asyncio

import uvicorn

from .runtime import loop_factory

if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config("app.main:app", host="127.0.0.1", port=8000, access_log=False))
    asyncio.run(server.serve(), loop_factory=loop_factory)
