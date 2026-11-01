import os
import re

from supabase import create_client


MEMBERS_TABLE = "guild_ranking_members_v1"
SETTINGS_TABLE = "guild_ranking_settings_v1"
DISCORD_ID_PATTERN = re.compile(r"[0-9]{17,20}\Z")
DISCORD_MENTION_PATTERN = re.compile(r"<@!?(?P<user_id>[0-9]{17,20})>\Z")


class RankingStore:
    def __init__(self):
        url = os.environ.get("RANKING_SUPABASE_URL", "").strip()
        key = os.environ.get("RANKING_SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError(
                "RANKING_SUPABASE_URL과 "
                "RANKING_SUPABASE_SERVICE_ROLE_KEY를 설정하세요."
            )
        self.client = create_client(url, key)

    @staticmethod
    def _nickname(nickname):
        value = str(nickname).strip()
        if not value or len(value) > 32 or any(ord(char) < 32 for char in value):
            raise ValueError("게임 닉네임은 공백 제외 1~32자로 입력하세요.")
        return value

    def _member(self, discord_user_id):
        rows = (
            self.client.table(MEMBERS_TABLE)
            .select("*")
            .eq("discord_user_id", str(discord_user_id))
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    @staticmethod
    def _resolve_from_records(identifier, records, allow_unregistered_discord_id=False):
        value = str(identifier).strip()
        mention = DISCORD_MENTION_PATTERN.fullmatch(value)
        discord_user_id = mention.group("user_id") if mention else value
        if DISCORD_ID_PATTERN.fullmatch(discord_user_id):
            matches = [
                record
                for record in records
                if str(record["discord_user_id"]) == discord_user_id
            ]
            if matches:
                return matches[0]["discord_user_id"]
            if allow_unregistered_discord_id:
                return discord_user_id
            raise ValueError("해당 디스코드 ID의 등록 정보를 찾을 수 없습니다.")

        nickname = value.casefold()
        matches = [
            record
            for record in records
            if record["nickname"].casefold() == nickname
        ]
        if len(matches) > 1:
            raise ValueError("같은 닉네임이 여러 개입니다. 디스코드 ID를 입력하세요.")
        if not matches:
            raise ValueError("해당 디스코드 ID 또는 게임 닉네임을 찾을 수 없습니다.")
        return matches[0]["discord_user_id"]

    def _all_member_records(self):
        return (
            self.client.table(MEMBERS_TABLE)
            .select("discord_user_id,nickname,status")
            .execute()
            .data
            or []
        )

    def _ensure_nickname_available(self, nickname, discord_user_id):
        members = (
            self.client.table(MEMBERS_TABLE)
            .select("discord_user_id,nickname")
            .execute()
            .data
            or []
        )
        normalized = nickname.casefold()
        if any(
            row["discord_user_id"] != str(discord_user_id)
            and row["nickname"].casefold() == normalized
            for row in members
        ):
            raise ValueError("이미 다른 디스코드 계정에 등록된 닉네임입니다.")

    def register_account(self, discord_user_id, nickname):
        discord_user_id = str(discord_user_id)
        nickname = self._nickname(nickname)
        current = self._member(discord_user_id)
        self._ensure_nickname_available(nickname, discord_user_id)
        self.client.table(MEMBERS_TABLE).upsert(
            {
                "discord_user_id": discord_user_id,
                "nickname": nickname,
                "status": "approved",
                "level": int(current.get("level") or 0) if current else 0,
                "damage_jo": int(current.get("damage_jo") or 0) if current else 0,
            },
            on_conflict="discord_user_id",
        ).execute()

    def activate_pending_members(self):
        self.client.table(MEMBERS_TABLE).update(
            {"status": "approved"}
        ).eq("status", "pending").execute()

    def list_members(self):
        return (
            self.client.table(MEMBERS_TABLE)
            .select("discord_user_id,nickname,level,damage_jo")
            .eq("status", "approved")
            .execute()
            .data
            or []
        )

    def set_damage(self, discord_user_id, damage_jo):
        rows = (
            self.client.table(MEMBERS_TABLE)
            .update({"damage_jo": damage_jo})
            .eq("discord_user_id", str(discord_user_id))
            .eq("status", "approved")
            .select("nickname")
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        return rows[0]["nickname"]

    def set_level(self, discord_user_id, level):
        rows = (
            self.client.table(MEMBERS_TABLE)
            .update({"level": level})
            .eq("discord_user_id", str(discord_user_id))
            .eq("status", "approved")
            .select("nickname")
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("등록된 계정이 없습니다. 먼저 /인증을 사용하세요.")
        return rows[0]["nickname"]

    def register_member(self, discord_user_id, nickname, level, damage_jo):
        discord_user_id = self._resolve_from_records(
            discord_user_id,
            self._all_member_records(),
            allow_unregistered_discord_id=True,
        )
        discord_user_id = str(discord_user_id)
        nickname = self._nickname(nickname)
        self._ensure_nickname_available(nickname, discord_user_id)
        self.client.table(MEMBERS_TABLE).upsert(
            {
                "discord_user_id": discord_user_id,
                "nickname": nickname,
                "level": level,
                "damage_jo": damage_jo,
                "status": "approved",
            },
            on_conflict="discord_user_id",
        ).execute()

    def update_member(self, discord_user_id, nickname=None, level=None, damage_jo=None):
        discord_user_id = self._resolve_from_records(
            discord_user_id,
            self.list_members(),
        )
        changes = {}
        if nickname is not None:
            nickname = self._nickname(nickname)
            self._ensure_nickname_available(nickname, discord_user_id)
            changes["nickname"] = nickname
        if level is not None:
            changes["level"] = level
        if damage_jo is not None:
            changes["damage_jo"] = damage_jo
        if not changes:
            raise ValueError("변경할 닉네임, 레벨 또는 추딜을 하나 이상 입력하세요.")
        rows = (
            self.client.table(MEMBERS_TABLE)
            .update(changes)
            .eq("discord_user_id", str(discord_user_id))
            .eq("status", "approved")
            .select("nickname")
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("수정할 승인 계정을 찾을 수 없습니다.")
        return rows[0]["nickname"]

    def delete_member(self, discord_user_id):
        discord_user_id = self._resolve_from_records(
            discord_user_id,
            self._all_member_records(),
        )
        rows = (
            self.client.table(MEMBERS_TABLE)
            .delete()
            .eq("discord_user_id", str(discord_user_id))
            .select("nickname")
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("삭제할 등록 정보를 찾을 수 없습니다.")
        return rows[0]["nickname"]

    def get_settings(self, guild_id, channel_id):
        guild_id = str(guild_id)
        rows = (
            self.client.table(SETTINGS_TABLE)
            .select("channel_id,message_id")
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            settings = rows[0]
            if settings["channel_id"] != str(channel_id):
                self.client.table(SETTINGS_TABLE).update(
                    {"channel_id": str(channel_id), "message_id": None}
                ).eq("guild_id", guild_id).execute()
                return {"channel_id": str(channel_id), "message_id": None}
            return settings
        settings = {"guild_id": guild_id, "channel_id": str(channel_id)}
        self.client.table(SETTINGS_TABLE).insert(settings).execute()
        return {"channel_id": str(channel_id), "message_id": None}

    def set_board_message_id(self, guild_id, channel_id, message_id):
        self.client.table(SETTINGS_TABLE).upsert(
            {
                "guild_id": str(guild_id),
                "channel_id": str(channel_id),
                "message_id": str(message_id),
            },
            on_conflict="guild_id",
        ).execute()