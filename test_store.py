import unittest
from unittest.mock import Mock

from store import RankingStore


class RankingTargetResolutionTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "discord_user_id": "123456789012345678",
                "nickname": "조은",
                "status": "pending",
            },
            {
                "discord_user_id": "987654321098765432",
                "nickname": "배달통",
                "status": "approved",
            },
        ]

    def test_resolves_discord_id_and_mention(self):
        expected = "123456789012345678"
        self.assertEqual(
            RankingStore._resolve_from_records(expected, self.records), expected
        )
        self.assertEqual(
            RankingStore._resolve_from_records(f"<@{expected}>", self.records),
            expected,
        )
        self.assertEqual(
            RankingStore._resolve_from_records(f"<@!{expected}>", self.records),
            expected,
        )

    def test_resolves_game_nickname_case_insensitively(self):
        self.assertEqual(
            RankingStore._resolve_from_records("  조은  ", self.records),
            "123456789012345678",
        )

    def test_allows_new_user_only_when_target_is_discord_id(self):
        new_user_id = "555555555555555555"
        self.assertEqual(
            RankingStore._resolve_from_records(
                new_user_id,
                self.records,
                allow_unregistered_discord_id=True,
            ),
            new_user_id,
        )
        with self.assertRaises(ValueError):
            RankingStore._resolve_from_records(
                "아직없는닉네임",
                self.records,
                allow_unregistered_discord_id=True,
            )

    def test_rejects_missing_or_ambiguous_nicknames(self):
        with self.assertRaises(ValueError):
            RankingStore._resolve_from_records("없는닉", self.records)
        duplicated = self.records + [
            {
                "discord_user_id": "111111111111111111",
                "nickname": "조은",
                "status": "pending",
            }
        ]
        with self.assertRaises(ValueError):
            RankingStore._resolve_from_records("조은", duplicated)


class DirectRegistrationTests(unittest.TestCase):
    def _store_with_current_member(self, current):
        store = RankingStore.__new__(RankingStore)
        store._member = Mock(return_value=current)
        store._ensure_nickname_available = Mock()
        store.client = Mock()
        return store

    def test_new_registration_is_immediately_active(self):
        store = self._store_with_current_member(None)
        store.register_account("123456789012345678", "새멤버")
        payload = store.client.table.return_value.upsert.call_args.args[0]
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["nickname"], "새멤버")
        self.assertEqual(payload["level"], 0)
        self.assertEqual(payload["damage_jo"], 0)

    def test_reregistration_preserves_stats_and_updates_nickname(self):
        current = {"status": "pending", "level": 2010, "damage_jo": 800}
        store = self._store_with_current_member(current)
        store.register_account("123456789012345678", "새닉네임")
        payload = store.client.table.return_value.upsert.call_args.args[0]
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["nickname"], "새닉네임")
        self.assertEqual(payload["level"], 2010)
        self.assertEqual(payload["damage_jo"], 800)

    def test_pending_members_are_activated(self):
        store = self._store_with_current_member(None)
        store.activate_pending_members()
        store.client.table.return_value.update.assert_called_once_with(
            {"status": "approved"}
        )
        store.client.table.return_value.update.return_value.eq.assert_called_once_with(
            "status", "pending"
        )


if __name__ == "__main__":
    unittest.main()