"""
Discord bot entry point.

Commands:
  /request   – Request access (opens reason modal)
  /discover  – Browse products
  /orders    – View order history

Persistent views are re-registered on startup for all pending approval requests.
Redis pub/sub listener runs as a background task for alert delivery.
"""
import asyncio
import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import tasks

from discord_bot.views.request import ReasonModal, AdminApprovalView
from discord_bot.views.discovery import DiscoveryView
from discord_bot.views.orders import OrdersView, _orders_list_embed
from discord_bot.views.admin import UsersView
from discord_bot.utils.database import (
    get_discord_orders,
    get_user_by_discord_id,
    get_suspended_user_by_discord_id,
    get_all_pending_requests,
    get_pool,
    close_pool,
)
from discord_bot.utils.redis_listener import start_redis_listener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.members = True


class ProductTrackerBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Register slash commands globally (or use guild= for instant testing)
        guild_id = os.environ.get("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Commands synced to guild %s", guild_id)
        else:
            await self.tree.sync()
            log.info("Commands synced globally")

        # Re-register persistent admin approval views for all pending requests
        await _restore_pending_views(self)

        # Start Redis listener as a background task
        self.loop.create_task(start_redis_listener(self))
        log.info("Redis listener task started")

    async def on_ready(self):
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)

    async def close(self):
        await close_pool()
        await super().close()


bot = ProductTrackerBot()


# ---------------------------------------------------------------------------
# Helper: restore persistent views on restart
# ---------------------------------------------------------------------------

async def _restore_pending_views(client: ProductTrackerBot):
    try:
        pending_requests = await get_all_pending_requests()
        for req in pending_requests:
            view = AdminApprovalView(pending_id=req["id"])
            client.add_view(view)
            log.info("Restored AdminApprovalView for pending_id=%s", req["id"])
    except Exception as exc:
        log.error("Failed to restore pending views: %s", exc)


# ---------------------------------------------------------------------------
# /request  — access request
# ---------------------------------------------------------------------------

@bot.tree.command(name="request", description="Request access to the product tracker")
async def cmd_request(interaction: discord.Interaction):
    existing_user = await get_user_by_discord_id(str(interaction.user.id))
    if existing_user:
        await interaction.response.send_message(
            "✅ You already have access! Use `/discover` to browse products.",
            ephemeral=True,
        )
        return
    await interaction.response.send_modal(ReasonModal())


# ---------------------------------------------------------------------------
# /discover  — product discovery
# ---------------------------------------------------------------------------

@bot.tree.command(name="discover", description="Browse and discover products to track")
async def cmd_discover(interaction: discord.Interaction):
    user = await get_user_by_discord_id(str(interaction.user.id))
    if not user:
        suspended = await get_suspended_user_by_discord_id(str(interaction.user.id))
        if suspended:
            await interaction.response.send_message(
                "⏸️ Your access has been **suspended**. Contact an admin for more information.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ You don't have access yet. Run `/request` to request access.",
                ephemeral=True,
            )
        return

    view = DiscoveryView(interaction_user=interaction.user)
    await view.send_initial(interaction)


# ---------------------------------------------------------------------------
# /orders   — order history
# ---------------------------------------------------------------------------

@bot.tree.command(name="orders", description="View your tracking order history")
async def cmd_orders(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user = await get_user_by_discord_id(str(interaction.user.id))
    if not user:
        suspended = await get_suspended_user_by_discord_id(str(interaction.user.id))
        msg = (
            "⏸️ Your access has been **suspended**. Contact an admin for more information."
            if suspended else
            "❌ You don't have access yet. Run `/request` to request access."
        )
        await interaction.followup.send(msg, ephemeral=True)
        return

    orders = await get_discord_orders(str(interaction.user.id))
    orders = [dict(o) for o in orders]

    if not orders:
        await interaction.followup.send(
            "You have no orders yet. Use `/discover` to find products to track.",
            ephemeral=True,
        )
        return

    embed = _orders_list_embed(orders, page=0)
    view = OrdersView(interaction_user=interaction.user, orders=orders, page=0)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ---------------------------------------------------------------------------
# /users  — admin user management (admin channel only)
# ---------------------------------------------------------------------------

@bot.tree.command(name="users", description="[Admin] List and manage users")
@app_commands.default_permissions(administrator=True)
async def cmd_users(interaction: discord.Interaction):
    admin_channel_id = os.environ.get("DISCORD_ADMIN_CHANNEL_ID")
    if admin_channel_id and str(interaction.channel_id) != admin_channel_id:
        await interaction.response.send_message(
            "⛔ This command is only available in the admin channel.",
            ephemeral=True,
        )
        return

    view = UsersView(admin_user=interaction.user)
    await view.send_initial(interaction)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        log.error("DISCORD_BOT_TOKEN is not set.")
        sys.exit(1)
    bot.run(token)


if __name__ == "__main__":
    main()
