import asyncio
import logging
import os
from time import perf_counter

import discord
from discord import app_commands
from discord.ext import commands

from board import MAX_DAMAGE, MAX_LEVEL, parse_damage_message, parse_level_message, render_board
from store import RankingStore


logger = logging.getLogger(__name__)
BOARD_REFRESH_DEBOUNCE_SECONDS = 0.25


def _is_admin(interaction, admin_role_id=None):
    permissions = getattr(interaction.user, "guild_permissions", None)
    has_server_permission = bool(
        permissions
        and (permissions.administrator or permissions.manage_guild)
    )
    if has_server_permission:
        return True
    if not admin_role_id:
        return False
    return any(
        str(role.id) == str(admin_role_id)
        for role in getattr(interaction.user, "roles", ())
    )


class RankingBot(commands.Bot):
    def __init__(self, token, guild_id, channel_id, store=None, admin_role_id=None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.token = token
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.admin_role_id = admin_role_id
        self.store = store or RankingStore()
        self.board_lock = asyncio.Lock()
        self._board_refresh_requested = False
        self._board_refresh_task = None

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=self.guild_id))

    async def refresh_board(self):
        async with self.board_lock:
            total_started = perf_counter()
            stage_started = total_started
            channel = self.get_channel(self.channel_id)
            if channel is None:
                channel = await self.fetch_channel(self.channel_id)
            members = await asyncio.to_thread(self.store.list_members)
            members_seconds = perf_counter() - stage_started

            stage_started = perf_counter()
            image = await asyncio.to_thread(render_board, members)
            render_seconds = perf_counter() - stage_started

            stage_started = perf_counter()
            settings = await asyncio.to_thread(
                self.store.get_settings,
                self.guild_id,
                self.channel_id,
            )
            settings_seconds = perf_counter() - stage_started

            stage_started = perf_counter()
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
            logger.info(
                "Ranking refresh timing: members=%.3fs render=%.3fs "
                "settings=%.3fs discord=%.3fs total=%.3fs",
                members_seconds,
                render_seconds,
                settings_seconds,
                perf_counter() - stage_started,
                perf_counter() - total_started,
            )

    def schedule_board_refresh(self):
        self._board_refresh_requested = True
        if self._board_refresh_task is None or self._board_refresh_task.done():
            self._board_refresh_task = asyncio.create_task(
                self._flush_scheduled_board_refreshes()
            )

    async def _flush_scheduled_board_refreshes(self):
        try:
            while self._board_refresh_requested:
                self._board_refresh_requested = False
                await asyncio.sleep(BOARD_REFRESH_DEBOUNCE_SECONDS)
                if self._board_refresh_requested:
                    continue
                try:
                    await self.refresh_board()
                except Exception:
                    logger.exception("Could not refresh the ranking board")
        finally:
            self._board_refresh_task = None
            if self._board_refresh_requested and not self.is_closed():
                self.schedule_board_refresh()


def create_bot():
    token = os.environ.get("RANKING_DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.environ.get("RANKING_GUILD_ID", "").strip()
    channel_id = os.environ.get("RANKING_CHANNEL_ID", "").strip()
    admin_role_id = os.environ.get("RANKING_ADMIN_ROLE_ID", "").strip()
    if not all((token, guild_id, channel_id)):
        raise RuntimeError(
            "RANKING_DISCORD_BOT_TOKEN, RANKING_GUILD_ID, "
            "RANKING_CHANNEL_ID를 설정하세요."
        )

    if admin_role_id and not admin_role_id.isdecimal():
        raise RuntimeError("RANKING_ADMIN_ROLE_ID는 Discord 역할 ID여야 합니다.")
    bot = RankingBot(
        token,
        int(guild_id),
        int(channel_id),
        admin_role_id=admin_role_id or None,
    )
    guild = discord.Object(id=bot.guild_id)

    async def admin_only(interaction):
        if interaction.guild_id != bot.guild_id:
            await interaction.response.send_message(
                "등록된 서버에서만 사용할 수 있습니다.", ephemeral=True
            )
            return False
        if not _is_admin(interaction, bot.admin_role_id):
            await interaction.response.send_message(
                "서버 관리자 또는 랭킹 관리자 역할이 있어야 사용할 수 있습니다.",
                ephemeral=True,
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

    @bot.tree.command(name="인증", description="게임 닉네임을 등록합니다.", guild=guild)
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
                bot.store.register_account,
                interaction.user.id,
                nickname,
            )
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        bot.schedule_board_refresh()
        await interaction.followup.send(
            f"`{nickname.strip()}` 등록을 완료했습니다. 이제 랭킹 채널에서 추뎀을 입력할 수 있습니다.",
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
            database_started = perf_counter()
            nickname = await asyncio.to_thread(
                bot.store.set_level, interaction.user.id, level
            )
            logger.info(
                "Slash level update timing: database=%.3fs",
                perf_counter() - database_started,
            )
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        bot.schedule_board_refresh()
        await interaction.followup.send(
            f"`{nickname}` 레벨을 {level:,}(으)로 변경했습니다.", ephemeral=True
        )

    @bot.tree.command(name="회원등록", description="관리자가 회원을 직접 등록합니다.", guild=guild)
    @app_commands.describe(
        target="디스코드 ID 또는 등록된 게임 닉네임",
        nickname="게임 닉네임",
        level="레벨",
        damage_jo="추뎀(조 단위 숫자)",
    )
    @app_commands.rename(
        target="대상", nickname="닉네임", level="레벨", damage_jo="추뎀"
    )
    async def admin_register(
        interaction: discord.Interaction,
        target: str,
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
                target,
                nickname,
                level,
                damage_jo,
            )
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        bot.schedule_board_refresh()
        await interaction.followup.send(
            f"`{target.strip()}` 대상을 `{nickname.strip()}`으로 등록했습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="회원수정", description="관리자가 회원 정보를 수정합니다.", guild=guild)
    @app_commands.describe(
        target="디스코드 ID 또는 등록된 게임 닉네임",
        nickname="새 게임 닉네임",
        level="새 레벨",
        damage_jo="새 추뎀(조 단위 숫자)",
    )
    @app_commands.rename(
        target="대상", nickname="닉네임", level="레벨", damage_jo="추뎀"
    )
    async def admin_update(
        interaction: discord.Interaction,
        target: str,
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
                target,
                nickname,
                level,
                damage_jo,
            )
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        bot.schedule_board_refresh()
        await interaction.followup.send(
            f"`{target.strip()}` 대상의 `{new_nickname}` 정보를 수정했습니다.",
            ephemeral=True,
        )

    @bot.tree.command(name="회원삭제", description="관리자가 회원 정보를 삭제합니다.", guild=guild)
    @app_commands.describe(target="디스코드 ID 또는 등록된 게임 닉네임")
    @app_commands.rename(target="대상")
    async def admin_delete(interaction: discord.Interaction, target: str):
        if not await admin_only(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            nickname = await asyncio.to_thread(bot.store.delete_member, target)
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        bot.schedule_board_refresh()
        await interaction.followup.send(
            f"`{target.strip()}` 대상의 `{nickname}` 정보를 삭제했습니다.",
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
            await asyncio.to_thread(bot.store.activate_pending_members)
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
        level = parse_level_message(message.content)
        if level is not None:
            try:
                database_started = perf_counter()
                await asyncio.to_thread(
                    bot.store.set_level, message.author.id, level
                )
                logger.info(
                    "Level message update timing: database=%.3fs",
                    perf_counter() - database_started,
                )
                bot.schedule_board_refresh()
                await message.delete()
            except ValueError:
                await message.add_reaction("🔒")
                try:
                    await message.author.send(
                        "등록된 랭킹 계정이 없습니다. 먼저 `/인증`으로 등록해주세요."
                    )
                except discord.Forbidden:
                    pass
            except discord.Forbidden:
                logger.exception("Could not delete a level update message")
                try:
                    await message.add_reaction("✅")
                except discord.HTTPException:
                    pass
            except Exception:
                logger.exception("Could not update level from a ranking message")
                try:
                    await message.add_reaction("⚠️")
                except discord.HTTPException:
                    pass
            return
        damage = parse_damage_message(message.content)
        if damage is None:
            return
        try:
            database_started = perf_counter()
            nickname = await asyncio.to_thread(
                bot.store.set_damage, message.author.id, damage
            )
            logger.info(
                "Damage message update timing: database=%.3fs",
                perf_counter() - database_started,
            )
            if nickname is None:
                await message.add_reaction("🔒")
                try:
                    await message.author.send(
                        "등록된 랭킹 계정이 없습니다. 먼저 `/인증`으로 등록해주세요."
                    )
                except discord.Forbidden:
                    pass
                return
            bot.schedule_board_refresh()
            await message.add_reaction("✅")
        except Exception:
            logger.exception("Could not update damage from a ranking message")
            try:
                await message.add_reaction("⚠️")
            except discord.HTTPException:
                pass

    return bot