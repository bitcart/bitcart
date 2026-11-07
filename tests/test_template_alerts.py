from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
import pytest_mock
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from httpx import AsyncClient as TestClient

from api.exceptions import EmailSendError
from api.schemas.misc import EmailSettings
from api.schemas.policies import Policy
from api.services.notification_manager import NotifyResult
from api.services.template_alerts import ALERT_SUBJECT, TemplateAlertService
from tests.helper import create_store, create_token, create_user

pytestmark = pytest.mark.anyio


@pytest.fixture
async def container(app: FastAPI) -> AsyncIterator[AsyncContainer]:
    async with app.state.dishka_container(scope=Scope.REQUEST) as request_container:
        yield request_container


@pytest.fixture
async def alerts(container: AsyncContainer, mocker: pytest_mock.MockerFixture) -> TemplateAlertService:
    service = await container.get(TemplateAlertService)
    mocker.patch.object(service.notification_manager, "notify", new=AsyncMock(return_value=NotifyResult()))
    mocker.patch.object(service.email_service, "send", new=AsyncMock())
    mocker.patch.object(service.email_service, "is_enabled", return_value=True)
    return service


def email_recipients(alerts: TemplateAlertService) -> list[str]:
    return [call.args[1] for call in alerts.email_service.send.call_args_list]  # type: ignore[attr-defined]


async def current_user_email(client: TestClient, token: str) -> str:
    return (await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})).json()["email"]


async def test_store_alert_emails_the_owner_without_providers(
    client: TestClient, token: str, alerts: TemplateAlertService
) -> None:
    store = await create_store(client, token)
    resp = await client.patch(
        f"/stores/{store['id']}",
        json={"email_settings": {"address": "store@example.com"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    await alerts.send(store["id"], "broken")
    notified_store, notified_text = alerts.notification_manager.notify.call_args.args  # type: ignore[attr-defined]
    assert notified_store.id == store["id"]
    assert notified_text == "broken"
    settings, recipient, subject, body = alerts.email_service.send.call_args.args  # type: ignore[attr-defined]
    assert settings.address == "store@example.com"
    assert recipient == await current_user_email(client, token)
    assert subject == ALERT_SUBJECT
    assert body == "broken"


async def test_store_alert_skips_email_when_a_provider_delivered(
    client: TestClient, token: str, alerts: TemplateAlertService
) -> None:
    store = await create_store(client, token)
    alerts.notification_manager.notify.return_value = NotifyResult(sent=1, failed=1)  # type: ignore[attr-defined]
    await alerts.send(store["id"], "broken")
    assert email_recipients(alerts) == []


async def test_store_alert_emails_when_every_provider_failed(
    client: TestClient, token: str, alerts: TemplateAlertService
) -> None:
    store = await create_store(client, token)
    alerts.notification_manager.notify.return_value = NotifyResult(failed=2)  # type: ignore[attr-defined]
    await alerts.send(store["id"], "broken")
    assert email_recipients(alerts) == [await current_user_email(client, token)]


async def test_store_alert_emails_when_notifying_raises(client: TestClient, token: str, alerts: TemplateAlertService) -> None:
    store = await create_store(client, token)
    alerts.notification_manager.notify.side_effect = RuntimeError("provider is down")  # type: ignore[attr-defined]
    await alerts.send(store["id"], "broken")
    assert email_recipients(alerts) == [await current_user_email(client, token)]


async def test_store_alert_skips_email_when_not_configured(
    client: TestClient, token: str, alerts: TemplateAlertService, mocker: pytest_mock.MockerFixture
) -> None:
    store = await create_store(client, token)
    mocker.patch.object(alerts.email_service, "is_enabled", return_value=False)
    await alerts.send(store["id"], "broken")
    assert alerts.notification_manager.notify.called  # type: ignore[attr-defined]
    assert email_recipients(alerts) == []


async def test_store_alert_without_an_owner_only_notifies_providers(
    client: TestClient, token: str, alerts: TemplateAlertService
) -> None:
    owner = await create_user(client, token=token)
    owner_token = await create_token(client, owner)
    store = await create_store(client, owner_token["access_token"])
    resp = await client.delete(f"/users/{owner['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    await alerts.send(store["id"], "broken")
    assert alerts.notification_manager.notify.called  # type: ignore[attr-defined]
    assert email_recipients(alerts) == []


async def test_alert_for_a_deleted_store_does_nothing(alerts: TemplateAlertService) -> None:
    await alerts.send("missing", "broken")
    assert not alerts.notification_manager.notify.called  # type: ignore[attr-defined]
    assert email_recipients(alerts) == []


async def test_global_alert_emails_enabled_superusers_with_policy_settings(
    client: TestClient, token: str, alerts: TemplateAlertService, mocker: pytest_mock.MockerFixture
) -> None:
    policy = Policy(email_settings=EmailSettings(address="policy@example.com"))
    mocker.patch.object(alerts.setting_service, "get_setting", new=AsyncMock(return_value=policy))
    enabled = await create_user(client, token=token)
    disabled = await create_user(client, token=token)
    regular = await create_user(client, token=token, is_superuser=False)
    resp = await client.patch(
        f"/users/{disabled['id']}", json={"is_enabled": False}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    await alerts.send(None, "renderer is down")
    recipients = email_recipients(alerts)
    assert enabled["email"] in recipients
    assert disabled["email"] not in recipients
    assert regular["email"] not in recipients
    assert not alerts.notification_manager.notify.called  # type: ignore[attr-defined]
    settings, _, subject, body = alerts.email_service.send.call_args.args  # type: ignore[attr-defined]
    assert settings.address == "policy@example.com"
    assert subject == ALERT_SUBJECT
    assert body == "renderer is down"


async def test_global_alert_keeps_going_after_a_failed_email(
    client: TestClient, token: str, alerts: TemplateAlertService
) -> None:
    await create_user(client, token=token)
    alerts.email_service.send.side_effect = EmailSendError("SMTP is down")  # type: ignore[attr-defined]
    await alerts.send(None, "renderer is down")
    assert len(email_recipients(alerts)) >= 2
