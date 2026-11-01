import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

from board import MAX_DAMAGE, parse_damage_message, render_board
from store import RankingStore


logger = logging.getLogger(__name__)
MAX_LEVEL = 9999


def _is_admin(interaction):
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(
        permissions
        and (permissions.administrator or permissions.manage_guild)
    )


class RankingBot(commands.Bot):
    def __init__(self, token, guild_id, channel_id, store=None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.token = token
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.store = store or RankingStore()
        self.board_lock = asyncio.Lock()

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=self.guild_id))

    async def refresh_board(self):
        async with self.board_lock:
            channel = self.get_channel(self.channel_id)
            if channel is None:
                channel = await self.fetch_channel(self.channel_id)
            members = await asyncio.to_thread(self.store.list_members)
            image = await asyncio.to_thread(render_board, members)
            settings = await asyncio.to_thread(
                self.store.get_settings,
                self.guild_id,
                self.channel_id,
            )
            message = None
            message_id = settings.get("message_id")
            if message_id:
                try:
                    message = await channel.fetch_message(int(message_id))
                except discord.NotFound:
                    message = None
            file = discord.File(image, filename="ranking.png")
            if message is None:
                message = await channel.send("보스 길드 전투력 순위", file=file)
                await asyncio.to_thread(
                    self.store.set_board_message_id,
                    self.guild_id,
                    self.channel_id,
                    message.id,
                )
            else:
                await message.edit(content="보스 길드 전투력 순위", attachments=[file])


def create_bot():
    token = os.environ.get("RANKING_DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.environ.get("RANKING_GUILD_ID", "").strip()
    channel_id = os.environ.get("RANKING_CHANNEL_ID", "").strip()
    if not all((token, guild_id, channel_id)):
        raise RuntimeError(
            "RANKING_DISCORD_BOT_TOKEN, RANKING_GUILD_ID, "
            "RANKING_CHANNEL_ID를 설정하세요."
        )

    bot = RankingBot(token, int(guild_id), int(channel_id))
    guild = discord.Object(id=bot.guild_id)

    async def admin_only(interaction):
        if interaction.guild_id != bot.guild_id:
            await interaction.response.send_message(
                "등록된 서버에서만 사용할 수 있습니다.", ephemeral=True
            )
            return False
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "서버 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return False
        return True

    @bot.tree.error
    async def on_app_command_error(interaction, error):
        logger.error(
            "Ranking command failed",
            exc_info=(type(error), error, error.__traceback__),
        )
        message = "명령 처리 중 오류가 발생했습니다. 봇 로그를 확인하세요."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.exception("Could not send a command error")

    @bot.tree.command(name="인증", description="게임 닉네임 등록을 요청합니다.", guild=guild)
    @app_commands.describe(nickname="등록할 게임 닉네임")
    @app_commands.rename(nickname="닉네임")
    async def register(interaction: discord.Interaction, nickname: str):
        if interaction.guild_id != bot.guild_id:
            await interaction.response.send_message(
                "등록된 서버에서만 사용할 수 있습니다.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await asyncio.to_thread(
                bot.store.request_registration,
                interaction.user.id,
                nickname,
            )
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"`{nickname.strip()}` 등록 요청을 보냈습니다. 관리자 승인 후 이용할 수 있습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="레벨", description="내 등록 레벨을 변경합니다.", guild=guild)
    @app_commands.describe(level="변경할 레벨")
    @app_commands.rename(level="레벨")
    async def set_own_level(
        interaction: discord.Interaction,
        level: app_commands.Range[int, 0, MAX_LEVEL],
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            nickname = await asyncio.to_thread(
                bot.store.set_level, interaction.user.id, level
            )
            await bot.refresh_board()
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"`{nickname}` 레벨을 {level:,}(으)로 변경했습니다.", ephemeral=True
        )

    @bot.tree.command(name="대기목록", description="승인 대기 중인 닉네임을 확인합니다.", guild=guild)
    async def pending_list(interaction: discord.Interaction):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            pending = await asyncio.to_thread(bot.store.list_pending)
        except Exception:
            logger.exception("Could not load pending registrations")
            await interaction.followup.send(
                "대기 목록을 불러오지 못했습니다. 봇 로그를 확인하세요.",
                ephemeral=True,
            )
            return
        if not pending:
            await interaction.followup.send("승인 대기 요청이 없습니다.", ephemeral=True)
            return
        lines = [
            f"<@{item['discord_user_id']}> · `{item['nickname']}`"
            for item in pending[:25]
        ]
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @bot.tree.command(name="승인", description="닉네임 등록 요청을 승인합니다.", guild=guild)
    @app_commands.describe(nickname="/대기목록에 표시된 게임 닉네임")
    @app_commands.rename(nickname="닉네임")
    async def approve(interaction: discord.Interaction, nickname: str):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            approved = await asyncio.to_thread(
                bot.store.approve_registration, nickname
            )
            await bot.refresh_board()
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"<@{approved['discord_user_id']}>님의 `{approved['nickname']}` 등록을 승인했습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="거절", description="닉네임 등록 요청을 거절합니다.", guild=guild)
    @app_commands.describe(member="거절할 사용자")
    @app_commands.rename(member="사용자")
    async def reject(interaction: discord.Interaction, member: discord.Member):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            nickname = await asyncio.to_thread(
                bot.store.reject_registration, member.id
            )
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"{member.mention}님의 `{nickname}` 등록 요청을 거절했습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="회원등록", description="관리자가 회원을 직접 등록합니다.", guild=guild)
    @app_commands.describe(
        member="등록할 사용자",
        nickname="게임 닉네임",
        level="레벨",
        damage_jo="추딜(조 단위 숫자)",
    )
    @app_commands.rename(
        member="사용자", nickname="닉네임", level="레벨", damage_jo="추딜"
    )
    async def admin_register(
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str,
        level: app_commands.Range[int, 0, MAX_LEVEL],
        damage_jo: app_commands.Range[int, 0, MAX_DAMAGE],
    ):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await asyncio.to_thread(
                bot.store.register_member,
                member.id,
                nickname,
                level,
                damage_jo,
            )
            await bot.refresh_board()
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"{member.mention}님을 `{nickname.strip()}`으로 등록했습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="회원수정", description="관리자가 회원 정보를 수정합니다.", guild=guild)
    @app_commands.describe(
        member="수정할 사용자",
        nickname="새 게임 닉네임",
        level="새 레벨",
        damage_jo="새 추딜(조 단위 숫자)",
    )
    @app_commands.rename(
        member="사용자", nickname="닉네임", level="레벨", damage_jo="추딜"
    )
    async def admin_update(
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str | None = None,
        level: app_commands.Range[int, 0, MAX_LEVEL] | None = None,
        damage_jo: app_commands.Range[int, 0, MAX_DAMAGE] | None = None,
    ):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            new_nickname = await asyncio.to_thread(
                bot.store.update_member,
                member.id,
                nickname,
                level,
                damage_jo,
            )
            await bot.refresh_board()
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"{member.mention}님의 `{new_nickname}` 정보를 수정했습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="회원삭제", description="관리자가 회원 정보를 삭제합니다.", guild=guild)
    @app_commands.describe(member="삭제할 사용자")
    @app_commands.rename(member="사용자")
    async def admin_delete(interaction: discord.Interaction, member: discord.Member):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            nickname = await asyncio.to_thread(bot.store.delete_member, member.id)
            await bot.refresh_board()
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(
            f"{member.mention}님의 `{nickname}` 정보를 삭제했습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="랭킹갱신", description="랭킹 이미지를 다시 만듭니다.", guild=guild)
    async def refresh(interaction: discord.Interaction):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await bot.refresh_board()
        await interaction.followup.send("랭킹 이미지를 갱신했습니다.", ephemeral=True)

    @bot.event
    async def on_ready():
        logger.info("Ranking bot connected as %s", bot.user)
        try:
            await bot.refresh_board()
        except Exception:
            logger.exception("Could not initialize the ranking image")

    @bot.event
    async def on_message(message: discord.Message):
        if (
            message.author.bot
            or message.guild is None
            or message.guild.id != bot.guild_id
            or message.channel.id != bot.channel_id
        ):
            return
        damage = parse_damage_message(message.content)
        if damage is None:
            return
        try:
            nickname = await asyncio.to_thread(
                bot.store.set_damage, message.author.id, damage
            )
            if nickname is None:
                await message.add_reaction("🔒")
                try:
                    await message.author.send(
                        "승인된 랭킹 계정이 없습니다. 먼저 `/인증`으로 등록 요청을 해주세요."
                    )
                except discord.Forbidden:
                    pass
                return
            await bot.refresh_board()
            await message.add_reaction("✅")
        except Exception:
            logger.exception("Could not update damage from a ranking message")
            try:
                await message.add_reaction("⚠️")
            except discord.HTTPException:
                pass

    return bot