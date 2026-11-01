import asyncio
import logging
import os

from aiohttp import web

from bot import create_bot


async def health(_request):
    return web.json_response({"status": "ok"})


async def discord_health(request):
    bot = request.app["bot"]
    if not bot.is_ready() or not bot.is_connected():
        status = "disconnected"
    elif bot.get_guild(bot.guild_id) is None:
        status = "guild_missing"
    elif bot.get_channel(bot.channel_id) is None:
        status = "channel_unavailable"
    else:
        status = "connected"
    return web.json_response(
        {"status": status},
        status=200 if status == "connected" else 503,
    )


async def main():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bot = create_bot()
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/healthz", health)
    app.router.add_get("/discordz", discord_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", "10000")))
    await site.start()
    try:
        await bot.start(bot.token)
    finally:
        await bot.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())