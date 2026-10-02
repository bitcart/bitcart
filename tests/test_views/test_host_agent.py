from __future__ import annotations

import asyncio
import pathlib
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from dishka import Scope
from fastapi import FastAPI

from api.ext.agent import AgentClient
from api.schemas.misc import HostAgentJob
from api.schemas.policies import BackupsPolicy
from api.services import backup_manager as backup_manager_module
from api.services.backup_manager import BackupManager
from api.services.host_agent import STALE_STATE_SECONDS, STATE_KEY, HostAgentService
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from tests.fixtures.pytest.agent import FakeAgent
from tests.helper import enabled_logs

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

pytestmark = pytest.mark.anyio


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def record_hook(registry: PluginRegistry, name: str) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    async def hook(*args: Any) -> None:
        calls.append(args)

    registry.register_hook(name, hook)
    return calls


async def get_service(app: FastAPI, service: type[Any]) -> Any:
    return await app.state.dishka_container.get(service)


async def test_management_without_agent(
    client: TestClient, token: str, limited_token: str, host_agent: HostAgentService
) -> None:
    resp = await client.post("/manage/restart", headers=auth(token))
    assert resp.json() == {
        "status": "error",
        "message": "The host agent is unavailable: the worker has not checked it yet. "
        "See https://github.com/bitcart/bitcart-docker#host-agent",
    }
    await host_agent.refresh_state()
    resp = await client.post("/manage/backups/backup", headers=auth(token))
    assert resp.json()["message"] == (
        "The host agent is unavailable: not configured. See https://github.com/bitcart/bitcart-docker#host-agent"
    )
    resp = await client.get("/manage/jobs/20260101T000000Z-000000", headers=auth(token))
    assert resp.status_code == 503
    assert resp.json()["detail"].startswith("The host agent is unavailable: not configured. See ")
    resp = await client.post("/configurator/server-settings", headers=auth(token))
    assert resp.status_code == 503
    assert resp.json()["detail"].startswith("The host agent is unavailable: not configured. See ")
    overview = (await client.get("/manage/agent", headers=auth(token))).json()
    assert overview["state"]["configured"] is False
    assert overview["state"]["available"] is False
    assert overview["state"]["unreachable_since"] is None
    assert overview["jobs"] == {}
    assert (await client.get("/manage/agent")).status_code == 401
    assert (await client.get("/manage/agent", headers=auth(limited_token))).status_code == 403
    assert (await client.get("/manage/jobs/20260101T000000Z-000000")).status_code == 401
    state = await host_agent.get_state()
    state.checked_at = int(time.time()) - STALE_STATE_SECONDS - 1
    await host_agent.redis_pool.set(STATE_KEY, state.model_dump_json())
    resp = await client.post("/manage/restart", headers=auth(token))
    assert resp.json()["message"].startswith("The host agent is unavailable: the worker has not checked it recently")


async def test_state_unreachable_and_recovered(host_agent: HostAgentService, fake_agent: FakeAgent) -> None:
    state = await host_agent.get_state()
    assert state.available is True
    assert state.capabilities is not None
    client = host_agent.client
    host_agent.client = AgentClient("unix:///nonexistent/agent.sock")
    state = await host_agent.refresh_state()
    assert state.available is False
    assert state.configured is True
    assert state.error is not None and state.error.startswith("Could not reach the host agent")
    assert state.capabilities is not None
    since = state.unreachable_since
    assert since is not None
    assert (await host_agent.refresh_state()).unreachable_since == since
    host_agent.client = client
    state = await host_agent.refresh_state()
    assert state.available is True
    assert state.unreachable_since is None
    assert state.error is None


async def test_management_jobs(
    app: FastAPI,
    client: TestClient,
    token: str,
    settings: Settings,
    tmp_path: pathlib.Path,
    host_agent: HostAgentService,
    fake_agent: FakeAgent,
) -> None:
    registry = await get_service(app, PluginRegistry)
    hooks = record_hook(registry, "server_restart")
    finished = record_hook(registry, "host_agent_job_finished")
    resp = (await client.post("/manage/restart", headers=auth(token))).json()
    assert resp["status"] == "success"
    job_id = resp["job_id"]
    assert fake_agent.requests[-1] == ("restart", {})
    assert hooks == [()]
    overview = (await client.get("/manage/agent", headers=auth(token))).json()
    assert overview["jobs"]["restart"] == {"job_id": job_id, "command": "restart", "state": "running"}
    assert (await client.post("/manage/update", headers=auth(token))).json() == {
        "status": "error",
        "message": "Another server operation is running",
        "job_id": job_id,
    }
    assert (await client.post("/manage/cleanup", headers=auth(token))).json() == {
        "status": "error",
        "message": (
            "Image cleanup did not start: Another server operation is running\nLog cleanup failed: Log file unconfigured"
        ),
        "job_id": job_id,
    }
    fake_agent.finish(job_id, log=b"Restarting\ndone\n")
    resp = await client.get(f"/manage/jobs/{job_id}", headers=auth(token))
    assert resp.status_code == 200
    status = resp.json()
    assert status["state"] == "done"
    assert status["command"] == "restart"
    assert status["log"] == "Restarting\ndone"
    assert await host_agent.get_job("restart") == HostAgentJob(job_id=job_id, command="restart")
    assert finished == []
    await host_agent.check_jobs()
    assert await host_agent.get_job("restart") == HostAgentJob(job_id=job_id, command="restart", state="done")
    assert finished == [(HostAgentJob(job_id=job_id, command="restart", state="done"),)]
    resp = await client.get(f"/manage/jobs/{job_id}?log_lines=1", headers=auth(token))
    assert resp.json()["log"] == "done"
    assert resp.json()["log_complete"] is False
    await client.post("/manage/policies", json={"staging_updates": True}, headers=auth(token))
    resp = (await client.post("/manage/update", headers=auth(token))).json()
    assert resp["status"] == "success"
    assert fake_agent.requests[-1] == ("update", {"channel": "staging"})
    fake_agent.finish(resp["job_id"])
    for path, command in (("plugin-reload", "reload"), ("cleanup/images", "cleanup")):
        resp = (await client.post(f"/manage/{path}", headers=auth(token))).json()
        assert resp["status"] == "success"
        assert fake_agent.requests[-1] == (command, {})
        fake_agent.finish(resp["job_id"])
    with enabled_logs(settings, str(tmp_path)):
        resp = (await client.post("/manage/cleanup", headers=auth(token))).json()
    assert resp == {"status": "success", "message": "Successfully started cleanup process!", "job_id": fake_agent.running}


async def test_job_status_errors(client: TestClient, token: str, host_agent: HostAgentService, fake_agent: FakeAgent) -> None:
    job_url = "/manage/jobs/20260101T000000Z-000000"
    resp = await client.get(job_url, headers=auth(token))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "no such job"
    assert (await client.get("/manage/jobs/1?log_lines=-1", headers=auth(token))).status_code == 422
    resp = await client.get("/manage/jobs/1", headers=auth(token))
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Invalid id: id is not a job id"
    fake_agent.token = "secret"
    resp = await client.get(job_url, headers=auth(token))
    assert resp.status_code == 502
    assert resp.json() == {"error": "Host agent error", "detail": "authentication failed"}
    fake_agent.token = ""
    fake_agent.commands = ["capabilities"]
    await host_agent.refresh_state()
    resp = await client.get(job_url, headers=auth(token))
    assert resp.status_code == 501
    assert resp.json()["detail"] == "The host agent does not support job_status. Update the server to use it"


async def test_manual_backup(
    app: FastAPI, client: TestClient, token: str, host_agent: HostAgentService, fake_agent: FakeAgent
) -> None:
    registry = await get_service(app, PluginRegistry)
    pre_backup = record_hook(registry, "pre_backup")
    post_backup = record_hook(registry, "post_backup")
    variables = {"BACKUP_ENCRYPTION": "true", "BACKUP_PROVIDER": "LOCAL", "S3_BUCKET": "b"}
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        setting_service = await container.get(SettingService)
        await setting_service.set_setting(BackupsPolicy(provider="local", environment_variables=variables))
    resp = (await client.post("/manage/backups/backup", headers=auth(token))).json()
    assert resp["status"] == "success"
    job_id = resp["job_id"]
    assert fake_agent.requests[-1] == ("backup", {**variables, "BACKUP_PROVIDER": "local"})
    assert len(pre_backup) == 1
    fake_agent.finish(job_id, log=b"Backed up\n", result={"filename": "shop.tar.zst.enc", "provider": "local"})
    status = (await client.get(f"/manage/jobs/{job_id}", headers=auth(token))).json()
    assert status["state"] == "done"
    assert status["result"]["filename"] == "shop.tar.zst.enc"
    assert post_backup == []
    await host_agent.check_jobs()
    assert await host_agent.get_job("backup") == HostAgentJob(job_id=job_id, command="backup", state="done")
    assert post_backup[0][0].environment_variables == variables
    assert post_backup[0][1] == {"status": "success", "message": "Backed up\n"}
    await host_agent.check_jobs()
    assert len(post_backup) == 1
    job_id = (await client.post("/manage/backups/backup", headers=auth(token))).json()["job_id"]
    fake_agent.finish(job_id, state="failed", log=b"upload failed\n")
    await host_agent.check_jobs()
    assert await host_agent.get_job("backup") == HostAgentJob(job_id=job_id, command="backup", state="failed")
    assert post_backup[1][1] == {"status": "error", "message": "upload failed\n"}


@pytest.fixture
def backups_dir(settings: Settings, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    monkeypatch.setattr(settings, "BACKUPS_DIR", str(tmp_path))
    return tmp_path


async def test_download_backup(
    client: TestClient,
    token: str,
    host_agent: HostAgentService,
    fake_agent: FakeAgent,
    backups_dir: pathlib.Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    async def finished_job(**result: Any) -> str:
        job_id = (await host_agent.call("backup"))["job_id"]
        fake_agent.finish(job_id, result=result)
        return job_id

    async def download(job_id: str) -> Any:
        return await client.get(f"/manage/backups/download/{job_id}", headers=auth(token))

    (backups_dir / "shop.tar.zst.enc").write_bytes(b"archive")
    job_id = await finished_job(filename="shop.tar.zst.enc")
    assert (await client.get(f"/manage/backups/download/{job_id}")).status_code == 401
    resp = await download(job_id)
    assert resp.status_code == 200
    assert resp.content == b"archive"
    assert resp.headers["content-disposition"] == 'attachment; filename="shop.tar.zst.enc"'
    (backups_dir / "shop.tar.zst.enc").unlink()
    outside = tmp_path_factory.mktemp("outside") / "shop.tar.zst"
    outside.write_bytes(b"archive")
    traversal_id = await finished_job(filename=f"../{outside.parent.name}/shop.tar.zst")
    running_id = (await host_agent.call("backup"))["job_id"]
    for missing_id in (job_id, traversal_id, running_id):
        resp = await download(missing_id)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "This backup file doesn't exist"


async def test_backup_start_failures(
    app: FastAPI, client: TestClient, token: str, host_agent: HostAgentService, fake_agent: FakeAgent
) -> None:
    registry = await get_service(app, PluginRegistry)
    pre_backup = record_hook(registry, "pre_backup")
    post_backup = record_hook(registry, "post_backup")
    running = "20260101T000000Z-aaaaaa"
    busy = {"status": "error", "message": "Another server operation is running", "job_id": running}
    fake_agent.running = running
    assert (await client.post("/manage/backups/backup", headers=auth(token))).json() == busy
    assert len(pre_backup) == 1
    assert [call[1] for call in post_backup] == [{"status": "error", "message": "Another server operation is running"}]
    await host_agent.refresh_state()
    assert (await client.post("/manage/backups/backup", headers=auth(token))).json() == busy
    assert len(pre_backup) == len(post_backup) == 1
    fake_agent.running = None
    await host_agent.refresh_state()
    resp = await client.post("/manage/backups", json={"environment_variables": {"PATH": "/tmp"}}, headers=auth(token))
    assert resp.status_code == 200
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        setting_service = await container.get(SettingService)
        await setting_service.set_setting(BackupsPolicy(environment_variables={"PATH": "/tmp"}))
    resp = (await client.post("/manage/backups/backup", headers=auth(token))).json()
    assert resp == {"status": "error", "message": "Invalid PATH: unknown argument"}
    assert post_backup[1][1] == {"status": "error", "message": "Invalid PATH: unknown argument"}
    fake_agent.commands = [command for command in fake_agent.commands if command != "backup"]
    await host_agent.refresh_state()
    resp = (await client.post("/manage/backups/backup", headers=auth(token))).json()
    assert resp["status"] == "error"
    assert len(pre_backup) == len(post_backup) == 2


async def test_scheduled_backup_retries(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, host_agent: HostAgentService, fake_agent: FakeAgent
) -> None:
    monkeypatch.setattr(backup_manager_module, "START_RETRY_INTERVAL", 0.05)
    monkeypatch.setattr(backup_manager_module, "START_RETRY_SECONDS", 0.5)
    registry = await get_service(app, PluginRegistry)
    pre_backup = record_hook(registry, "pre_backup")
    post_backup = record_hook(registry, "post_backup")
    backup_manager: BackupManager = await get_service(app, BackupManager)

    async def later(change: Callable[[], Awaitable[None]]) -> None:
        await asyncio.sleep(0.12)
        await change()

    fake_agent.running = "20260101T000000Z-aaaaaa"
    await host_agent.refresh_state()
    await backup_manager.perform_backup()
    assert [command for command, _ in fake_agent.requests if command == "backup"] == []
    assert pre_backup == post_backup == []

    async def free() -> None:
        fake_agent.running = None
        await host_agent.refresh_state()

    freeing = asyncio.create_task(later(free))
    await backup_manager.perform_backup()
    await freeing
    job = await host_agent.get_job("backup")
    assert job is not None
    assert job.job_id == fake_agent.running
    assert len(pre_backup) == 1
    assert post_backup == []
    fake_agent.finish(job.job_id)
    await host_agent.check_jobs()

    state = await host_agent.get_state()
    state.checked_at = int(time.time()) - STALE_STATE_SECONDS - 1
    await host_agent.redis_pool.set(STATE_KEY, state.model_dump_json())
    refreshing = asyncio.create_task(later(host_agent.refresh))
    await backup_manager.perform_backup()
    await refreshing
    assert fake_agent.running is not None
    assert await host_agent.get_job("backup") == HostAgentJob(job_id=fake_agent.running, command="backup")
    assert len(pre_backup) == 2

    host_agent.client = AgentClient("")
    await host_agent.refresh_state()
    started = time.monotonic()
    await backup_manager.perform_backup()
    assert time.monotonic() - started < 0.05
    assert len(pre_backup) == 2


async def test_check_jobs(app: FastAPI, host_agent: HostAgentService, fake_agent: FakeAgent) -> None:
    post_backup = record_hook(await get_service(app, PluginRegistry), "post_backup")
    backup_id = (await host_agent.call("backup"))["job_id"]
    fake_agent.finish(backup_id, state="failed")
    await host_agent.check_jobs()
    assert post_backup[0][1] == {"status": "error", "message": "The backup job ended as failed (exit)"}
    restart_id = (await host_agent.call("restart"))["job_id"]
    await host_agent.check_jobs()
    assert await host_agent.get_job("restart") == HostAgentJob(job_id=restart_id, command="restart")
    del fake_agent.jobs[restart_id]
    await host_agent.check_jobs()
    assert await host_agent.get_job("restart") == HostAgentJob(job_id=restart_id, command="restart", state="unknown")
    requests = len(fake_agent.requests)
    await host_agent.check_jobs()
    assert len(fake_agent.requests) == requests


async def test_restore_backup(
    app: FastAPI,
    client: TestClient,
    token: str,
    host_agent: HostAgentService,
    fake_agent: FakeAgent,
    backups_dir: pathlib.Path,
) -> None:
    restore_hook = record_hook(await get_service(app, PluginRegistry), "restore_backup")

    async def restore(filename: str) -> tuple[dict[str, Any], pathlib.Path]:
        resp = await client.post("/manage/backups/restore", files={"backup": (filename, b"data")}, headers=auth(token))
        return resp.json(), backups_dir / fake_agent.requests[-1][1]["name"]

    resp = await client.post("/manage/backups/restore", files={"backup": ("backup.zip", b"test")}, headers=auth(token))
    assert resp.json()["message"].startswith("The backup must be a .tar.zst or .tar.gz archive")
    data, upload = await restore("shop.tar.gz.enc")
    assert data["status"] == "success"
    assert fake_agent.requests[-1][0] == "restore"
    assert upload.name.startswith("restore-")
    assert upload.name.endswith(".tar.gz.enc")
    assert upload.read_bytes() == b"data"
    assert restore_hook == [(str(upload),)]
    fake_agent.running = "20260101T000000Z-aaaaaa"
    data, upload = await restore("shop.tar.zst")
    assert data["job_id"] == fake_agent.running
    assert upload.name.endswith(".tar.zst")
    assert not upload.exists()
    fake_agent.running = None
    host_agent.client = AgentClient("unix:///nonexistent/agent.sock")
    data, _ = await restore("shop.tar.zst")
    assert data["status"] == "error"
    assert len(list(backups_dir.glob("restore-*"))) == 1


async def test_configurator_current_instance(
    app: FastAPI, client: TestClient, token: str, host_agent: HostAgentService, fake_agent: FakeAgent
) -> None:
    registry = await get_service(app, PluginRegistry)
    pre_deploy = record_hook(registry, "pre_deploy")
    post_deploy = record_hook(registry, "post_deploy")
    resp = await client.post("/configurator/server-settings", headers=auth(token))
    assert resp.json() == {
        "domain_settings": {"domain": "shop.example.com", "https": True},
        "coins": {
            "btc": {"enabled": True, "network": "mainnet", "lightning": False},
            "ltc": {"enabled": True, "network": "testnet", "lightning": False},
        },
        "additional_services": [],
        "advanced_settings": {"installation_pack": "all", "bitcart_docker_repository": "", "additional_components": []},
    }
    deploy_settings: dict[str, Any] = {
        "mode": "Current",
        "domain_settings": {"domain": "new.example.com", "https": False},
        "coins": {"btc": {"network": "mainnet", "lightning": True}},
        "additional_services": ["tor"],
        "advanced_settings": {"installation_pack": "frontend", "additional_components": ["custom"]},
    }

    async def deploy_result(deploy_id: str) -> dict[str, Any]:
        return (await client.get(f"/configurator/deploy-result/{deploy_id}", headers=auth(token))).json()

    data = (await client.post("/configurator/deploy", json=deploy_settings, headers=auth(token))).json()
    assert data["finished"] is False
    assert fake_agent.requests[-1] == (
        "reconfigure",
        {
            "BITCART_HOST": "new.example.com",
            "BITCART_REVERSEPROXY": "nginx",
            "BITCART_CRYPTOS": "btc",
            "BITCART_INSTALL": "frontend",
            "BITCART_ADDITIONAL_COMPONENTS": "custom,tor",
            "BTC_NETWORK": "mainnet",
            "BTC_LIGHTNING": "true",
        },
    )
    assert len(pre_deploy) == 1
    job_id = fake_agent.running
    assert job_id is not None
    fake_agent.finish(job_id, log=b"".join(b"line %d\n" % i for i in range(150)))
    assert (await deploy_result(data["id"]))["finished"] is False
    assert post_deploy == []
    await host_agent.check_jobs()
    await host_agent.check_jobs()
    result = await deploy_result(data["id"])
    assert result["finished"] is True
    assert result["success"] is True
    assert result["output"].count("\n") == 150
    assert len(post_deploy) == 1
    assert post_deploy[0][2] is True
    deploy_settings["advanced_settings"]["bitcart_docker_repository"] = "https://github.com/someone/bitcart-docker"
    fake_agent.running = "20260101T000000Z-aaaaaa"
    data = (await client.post("/configurator/deploy", json=deploy_settings, headers=auth(token))).json()
    assert data["output"] == "Another server operation is running"
    assert len(pre_deploy) == len(post_deploy) == 2
    fake_agent.running = None
    job_id = (await host_agent.call("reconfigure"))["job_id"]
    fake_agent.finish(job_id)
    await host_agent.check_jobs()
    assert len(post_deploy) == 2


async def test_check_jobs_deadline(host_agent: HostAgentService, fake_agent: FakeAgent) -> None:
    recent_id = (await host_agent.call("restart"))["job_id"]
    await host_agent.set_job(HostAgentJob(job_id="20200101T000000Z-aaaaaa", command="backup"))
    host_agent.client = AgentClient("unix:///nonexistent/agent.sock")
    await host_agent.check_jobs()
    assert await host_agent.get_job("restart") == HostAgentJob(job_id=recent_id, command="restart")
    assert await host_agent.get_job("backup") == HostAgentJob(
        job_id="20200101T000000Z-aaaaaa", command="backup", state="unknown"
    )


async def test_replaced_running_job_is_completed(
    app: FastAPI, host_agent: HostAgentService, fake_agent: FakeAgent, background_tasks: MagicMock
) -> None:
    registry = await get_service(app, PluginRegistry)
    finished = record_hook(registry, "host_agent_job_finished")
    post_backup = record_hook(registry, "post_backup")
    first_id = (await host_agent.call("backup"))["job_id"]
    fake_agent.finish(first_id, state="failed", log=b"bad S3 settings\n")
    second_id = (await host_agent.call("backup"))["job_id"]
    await asyncio.gather(*background_tasks.spy_return_list)
    assert post_backup[0][1] == {"status": "error", "message": "bad S3 settings\n"}
    assert finished == [(HostAgentJob(job_id=first_id, command="backup", state="failed"),)]
    assert await host_agent.get_job("backup") == HostAgentJob(job_id=second_id, command="backup")
    fake_agent.finish(second_id, log=b"Backed up\n")
    await host_agent.check_jobs()
    await host_agent.check_jobs()
    assert [call[1] for call in post_backup] == [
        {"status": "error", "message": "bad S3 settings\n"},
        {"status": "success", "message": "Backed up\n"},
    ]
    vanished_id = (await host_agent.call("backup"))["job_id"]
    del fake_agent.jobs[vanished_id]
    fake_agent.running = None
    await host_agent.call("backup")
    await asyncio.gather(*background_tasks.spy_return_list)
    assert finished[-1] == (HostAgentJob(job_id=vanished_id, command="backup", state="unknown"),)
    assert post_backup[-1][1] == {"status": "error", "message": "The backup job was lost: no such job"}
