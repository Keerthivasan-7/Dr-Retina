from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app import worker


async def test_quality_rejection_never_calls_classifier(monkeypatch):
    conn = AsyncMock()
    screen = {"id": uuid4(), "org_id": uuid4(), "created_by": uuid4(), "status": "IMAGE_UPLOADED"}
    job = {"id": uuid4(), "screening_id": screen["id"], "lease_token": uuid4()}

    @asynccontextmanager
    async def tx():
        yield conn

    monkeypatch.setattr(worker, "transaction", tx)
    monkeypatch.setattr(worker, "locked", AsyncMock(return_value=screen))
    monkeypatch.setattr(
        worker, "one", AsyncMock(side_effect=[{"object_path": "private/original", "mime": "image/png"}, None])
    )
    monkeypatch.setattr(worker.storage, "download", AsyncMock(return_value=b"original"))
    model = AsyncMock(
        return_value=b'{"score":0.2,"accepted":false,"reasons":["Blurred"],"model_version":"quality-test"}'
    )
    monkeypatch.setattr(worker, "call_model", model)
    await worker.process(job)
    model.assert_awaited_once()
    assert model.await_args.args[0] == "quality"
    assert screen["status"] == "QUALITY_REJECTED"
    statements = [call.args[0] for call in conn.execute.await_args_list]
    assert not any("insert into retina.ai_results" in sql for sql in statements)
    assert any("state='DONE'" in sql for sql in statements)


async def test_stale_worker_cannot_commit(monkeypatch):
    monkeypatch.setattr(worker, "one", AsyncMock(return_value={"lease_token": uuid4(), "state": "RUNNING"}))
    with pytest.raises(RuntimeError, match="LEASE_LOST"):
        await worker.locked(AsyncMock(), {"id": uuid4(), "lease_token": uuid4()})
