import json
import unittest
from types import SimpleNamespace

from main import discord_health, health


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_reports_process_liveness(self):
        response = await health(None)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text), {"status": "ok"})

    async def test_discord_health_reports_connected_gateway(self):
        bot = SimpleNamespace(
            is_ready=lambda: True,
            is_connected=lambda: True,
            guild_id=1,
            channel_id=2,
            get_guild=lambda guild_id: object(),
            get_channel=lambda channel_id: object(),
        )
        request = SimpleNamespace(app={"bot": bot})
        response = await discord_health(request)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text), {"status": "connected"})

    async def test_discord_health_reports_disconnected_gateway(self):
        bot = SimpleNamespace(
            is_ready=lambda: False,
            is_connected=lambda: False,
            guild_id=1,
            channel_id=2,
        )
        request = SimpleNamespace(app={"bot": bot})
        response = await discord_health(request)
        self.assertEqual(response.status, 503)
        self.assertEqual(json.loads(response.text), {"status": "disconnected"})

    async def test_discord_health_reports_missing_guild(self):
        bot = SimpleNamespace(
            is_ready=lambda: True,
            is_connected=lambda: True,
            guild_id=1,
            channel_id=2,
            get_guild=lambda guild_id: None,
        )
        request = SimpleNamespace(app={"bot": bot})
        response = await discord_health(request)
        self.assertEqual(response.status, 503)
        self.assertEqual(json.loads(response.text), {"status": "guild_missing"})

    async def test_discord_health_reports_unavailable_channel(self):
        bot = SimpleNamespace(
            is_ready=lambda: True,
            is_connected=lambda: True,
            guild_id=1,
            channel_id=2,
            get_guild=lambda guild_id: object(),
            get_channel=lambda channel_id: None,
        )
        request = SimpleNamespace(app={"bot": bot})
        response = await discord_health(request)
        self.assertEqual(response.status, 503)
        self.assertEqual(
            json.loads(response.text), {"status": "channel_unavailable"}
        )


if __name__ == "__main__":
    unittest.main()