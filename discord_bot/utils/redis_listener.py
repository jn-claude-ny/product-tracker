"""
Background Redis pub/sub listener.
Subscribes to discord_alert:* channels and dispatches DMs to users.

Message format (JSON published by Celery alert engine):
{
  "discord_user_id": "123456789",
  "order_id": 42,
  "product_title": "Air Max 90",
  "product_brand": "Nike",
  "product_price": 110.0,
  "product_price_previous": 130.0,
  "product_image": "https://...",
  "alert_type": "price_drop"   # or "restock"
}
"""
import asyncio
import json
import logging
import os

import redis.asyncio as aioredis
import discord

log = logging.getLogger(__name__)


async def start_redis_listener(bot: discord.Client):
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")

    while True:
        redis = None
        pubsub = None
        try:
            redis = await aioredis.from_url(redis_url, decode_responses=True)
            pubsub = redis.pubsub()
            await pubsub.psubscribe("discord_alert:*")
            log.info("[redis_listener] Subscribed to discord_alert:*")

            async for message in pubsub.listen():
                if message["type"] not in ("pmessage", "message"):
                    continue
                try:
                    data = json.loads(message["data"])
                    await _handle_alert(bot, data)
                except Exception as exc:
                    log.exception("[redis_listener] Error handling message: %s", exc)

        except Exception as exc:
            log.error("[redis_listener] Connection error: %s — retrying in 5s", exc)
        finally:
            try:
                if pubsub:
                    await pubsub.unsubscribe()
                    await pubsub.aclose()
            except Exception:
                pass
            try:
                if redis:
                    await redis.aclose()
            except Exception:
                pass
            await asyncio.sleep(5)


async def _handle_alert(bot: discord.Client, data: dict):
    discord_user_id = data.get("discord_user_id")
    if not discord_user_id:
        return

    try:
        user = await bot.fetch_user(int(discord_user_id))
    except discord.NotFound:
        log.warning("[redis_listener] Discord user %s not found", discord_user_id)
        return

    alert_type = data.get("alert_type", "restock")
    product_title = data.get("product_title", "Unknown Product")
    product_brand = data.get("product_brand", "")
    product_price = data.get("product_price")
    product_price_previous = data.get("product_price_previous")
    product_image = data.get("product_image")
    order_id = data.get("order_id")

    embed = discord.Embed(color=discord.Color.green() if alert_type == "restock" else discord.Color.orange())

    if alert_type == "restock":
        embed.title = "🔔 Back In Stock!"
        embed.description = (
            f"**{product_brand} {product_title}** is back in stock!\n"
            f"Order #{order_id}"
        )
    else:
        price_str = f"~~${product_price_previous:.2f}~~ → **${product_price:.2f}**" if product_price_previous else f"**${product_price:.2f}**"
        embed.title = "💸 Price Drop!"
        embed.description = (
            f"**{product_brand} {product_title}**\n"
            f"Price: {price_str}\n"
            f"Order #{order_id}"
        )

    if product_image:
        embed.set_thumbnail(url=product_image)

    try:
        await user.send(content=f"<@{discord_user_id}>", embed=embed)
        log.info("[redis_listener] Sent %s alert to %s for order #%s", alert_type, discord_user_id, order_id)

        if order_id:
            from discord_bot.utils.database import update_order_last_alert
            await update_order_last_alert(order_id)
    except discord.Forbidden:
        log.warning("[redis_listener] Cannot DM user %s (DMs disabled)", discord_user_id)
    except Exception as exc:
        log.exception("[redis_listener] Failed to send DM: %s", exc)
