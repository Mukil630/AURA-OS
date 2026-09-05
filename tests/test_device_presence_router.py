import asyncio
import pytest
from brain.device_presence_router import DevicePresenceRouter, PresentationResult


class MockBridgeOnline:
    def is_pc_online(self):
        return True

    async def dispatch_task(self, command, task_type):
        return {"status": "SUCCESS", "screenshot_path": "storage/screenshots/screen_proof.png"}


class MockBridgeOffline:
    def is_pc_online(self):
        return False


def test_presentation_pc_online():
    router = DevicePresenceRouter(bridge_server=MockBridgeOnline())
    res = asyncio.run(router.route_presentation("C:/reports/Karur_Mills.xlsx"))
    assert res.is_pc_online is True
    assert res.mode_selected == "PC_SCREEN_LAUNCH"
    assert "active-aa irukku" in res.status_message


def test_presentation_pc_offline():
    router = DevicePresenceRouter(bridge_server=MockBridgeOffline())
    res = asyncio.run(router.route_presentation("C:/reports/Karur_Mills.xlsx"))
    assert res.is_pc_online is False
    assert res.mode_selected == "MOBILE_TELEGRAM_PREVIEW"
    assert "standby / closed-la irukku" in res.status_message
    assert res.drive_link is not None
