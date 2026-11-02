import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bot import RankingBot, _delete_input_message, _is_admin, _is_rank_input
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


class BoardRefreshSchedulingTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_refresh_requests_are_coalesced(self):
        bot = RankingBot("test-token", 1, 2, store=Mock())
        bot.refresh_board = AsyncMock()
        bot.schedule_board_refresh()
        bot.schedule_board_refresh()
        bot.schedule_board_refresh()

        await bot._board_refresh_task

        bot.refresh_board.assert_awaited_once()
        await bot.close()


class RankingChannelInputPolicyTests(unittest.IsolatedAsyncioTestCase):
    def test_only_supported_formats_are_rank_inputs(self):
        self.assertTrue(_is_rank_input("추뎀 777"))
        self.assertTrue(_is_rank_input("추뎀 777조"))
        self.assertTrue(_is_rank_input("레벨 200"))
        self.assertFalse(_is_rank_input("안녕하세요"))
        self.assertFalse(_is_rank_input("추뎀"))
        self.assertFalse(_is_rank_input("777"))

    def test_ranking_admin_role_and_server_managers_are_exempt(self):
        role_admin = SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=False, manage_guild=False),
            roles=[SimpleNamespace(id=42)],
        )
        server_manager = SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=False, manage_guild=True),
            roles=[],
        )
        server_admin = SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=True, manage_guild=False),
            roles=[],
        )
        regular_member = SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=False, manage_guild=False),
            roles=[],
        )

        self.assertTrue(_is_admin(role_admin, "42"))
        self.assertTrue(_is_admin(server_manager, "42"))
        self.assertTrue(_is_admin(server_admin, "42"))
        self.assertFalse(_is_admin(regular_member, "42"))

    async def test_invalid_input_deletion_does_not_send_a_dm(self):
        message = SimpleNamespace(delete=AsyncMock(), author=Mock())
        await _delete_input_message(message)
        message.delete.assert_awaited_once()
        message.author.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()