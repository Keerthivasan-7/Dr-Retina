import httpx
from fastapi import HTTPException

from .config import settings


async def storage_request(method, path, **kwargs):
    cfg = settings()
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.request(
            method,
            f"{cfg.supabase_url}/storage/v1/{path}",
            headers={
                "apikey": cfg.supabase_service_role_key.get_secret_value(),
                "Authorization": f"Bearer {cfg.supabase_service_role_key.get_secret_value()}",
                **kwargs.pop("headers", {}),
            },
            **kwargs,
        )
    if response.is_error:
        raise HTTPException(503, "Private image storage is unavailable")
    return response


async def upload(path, data, mime):
    await storage_request(
        "POST",
        f"object/{settings().storage_bucket}/{path}",
        content=data,
        headers={"Content-Type": mime, "x-upsert": "false"},
    )


async def download(path):
    return (await storage_request("GET", f"object/{settings().storage_bucket}/{path}")).content
