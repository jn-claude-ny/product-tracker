"""
Admin user management flow (admin-channel only):
  /users  — paginated list of discord users with Ban / Kick / Reactivate actions
"""
import logging
import os
from typing import Optional

import discord
from discord import ui

from discord_bot.utils.database import (
    list_discord_users,
    count_discord_users,
    ban_discord_user,
    kick_discord_user,
    reactivate_discord_user,
)

log = logging.getLogger(__name__)

PAGE_SIZE = 4

COLOR_NEUTRAL  = discord.Color.from_rgb(88, 101, 242)
COLOR_DANGER   = discord.Color.from_rgb(254, 75,  75)
COLOR_WARNING  = discord.Color.from_rgb(254, 172, 94)
COLOR_SUCCESS  = discord.Color.from_rgb(87,  242, 135)


# ---------------------------------------------------------------------------
# Modals for optional messages
# ---------------------------------------------------------------------------

class BanMessageModal(ui.Modal, title="Ban User"):
    message = ui.TextInput(
        label="Reason / message to user (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
        placeholder="They'll receive this as a DM before being removed.",
    )

    def __init__(self, discord_id: str, discord_name: str, users_view: "UsersView"):
        super().__init__()
        self._discord_id   = discord_id
        self._discord_name = discord_name
        self._users_view   = users_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if self.message.value:
            try:
                target = await interaction.client.fetch_user(int(self._discord_id))
                await target.send(
                    f"🚫 **You have been banned from the product tracker.**\n"
                    f"**Reason:** {self.message.value}"
                )
            except Exception:
                pass

        row = await ban_discord_user(self._discord_id)
        if not row:
            await interaction.followup.send("⚠️ User not found or already removed.", ephemeral=True)
            return

        log.info("Admin %s banned discord user %s (%s)", interaction.user, self._discord_name, self._discord_id)
        await interaction.followup.send(
            f"🚫 **Banned** `{self._discord_name}` — account and all data deleted.",
            ephemeral=True,
        )
        await self._users_view.refresh(interaction, edit_original=True)


class KickMessageModal(ui.Modal, title="Kick User"):
    message = ui.TextInput(
        label="Reason / message to user (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
        placeholder="They'll receive this as a DM.",
    )

    def __init__(self, discord_id: str, discord_name: str, users_view: "UsersView"):
        super().__init__()
        self._discord_id   = discord_id
        self._discord_name = discord_name
        self._users_view   = users_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if self.message.value:
            try:
                target = await interaction.client.fetch_user(int(self._discord_id))
                await target.send(
                    f"⚠️ **Your access to the product tracker has been suspended.**\n"
                    f"**Reason:** {self.message.value}"
                )
            except Exception:
                pass

        row = await kick_discord_user(self._discord_id)
        if not row:
            await interaction.followup.send("⚠️ User not found.", ephemeral=True)
            return

        log.info("Admin %s kicked discord user %s (%s)", interaction.user, self._discord_name, self._discord_id)
        await interaction.followup.send(
            f"⏸️ **Suspended** `{self._discord_name}` — access deactivated. Use Reactivate to restore.",
            ephemeral=True,
        )
        await self._users_view.refresh(interaction, edit_original=True)


# ---------------------------------------------------------------------------
# Per-user action select
# ---------------------------------------------------------------------------

class UserActionSelect(ui.Select):
    def __init__(self, discord_id: str, discord_name: str, is_active: bool, users_view: "UsersView"):
        self._discord_id   = discord_id
        self._discord_name = discord_name
        self._users_view   = users_view

        options = [
            discord.SelectOption(
                label=f"🚫 Ban  {discord_name[:40]}",
                value=f"ban|{discord_id}",
                description="Permanently delete account & all data",
                emoji="🚫",
            ),
        ]
        if is_active:
            options.append(discord.SelectOption(
                label=f"⏸️ Kick  {discord_name[:40]}",
                value=f"kick|{discord_id}",
                description="Suspend access (reversible)",
                emoji="⏸️",
            ))
        else:
            options.append(discord.SelectOption(
                label=f"▶️ Reactivate  {discord_name[:40]}",
                value=f"reactivate|{discord_id}",
                description="Restore suspended access",
                emoji="▶️",
            ))

        super().__init__(
            placeholder=f"Action on {discord_name[:30]}…",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        value  = self.values[0]
        action, discord_id = value.split("|", 1)

        if action == "ban":
            await interaction.response.send_modal(
                BanMessageModal(discord_id, self._discord_name, self._users_view)
            )

        elif action == "kick":
            await interaction.response.send_modal(
                KickMessageModal(discord_id, self._discord_name, self._users_view)
            )

        elif action == "reactivate":
            await interaction.response.defer(ephemeral=True)
            row = await reactivate_discord_user(discord_id)
            if not row:
                await interaction.followup.send("⚠️ User not found.", ephemeral=True)
                return
            try:
                target = await interaction.client.fetch_user(int(discord_id))
                await target.send("✅ **Your access to the product tracker has been restored.**")
            except Exception:
                pass
            await interaction.followup.send(
                f"✅ **Reactivated** `{self._discord_name}`.", ephemeral=True
            )
            await self._users_view.refresh(interaction, edit_original=True)


# ---------------------------------------------------------------------------
# Main users list view
# ---------------------------------------------------------------------------

def _users_embed(users: list, page: int, total: int) -> discord.Embed:
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    embed = discord.Embed(
        title="👥  User Management",
        color=COLOR_NEUTRAL,
        description=(
            f"**{total}** registered Discord users  •  "
            f"Page **{page + 1}** / **{total_pages}**\n"
            "Select a user's action from the dropdowns below."
        ),
    )

    if not users:
        embed.add_field(name="No users", value="No Discord users registered yet.", inline=False)
        return embed

    for u in users:
        status = "🟢 Active" if u["is_active"] else "🔴 Suspended"
        role_tag = "👑 Admin" if u["role"] == "admin" else "👤 User"
        joined = u["created_at"].strftime("%d %b %Y") if u.get("created_at") else "?"
        embed.add_field(
            name=f"{u['discord_name']}",
            value=(
                f"`{u['discord_id']}`\n"
                f"{status}  ·  {role_tag}  ·  joined {joined}"
            ),
            inline=True,
        )

    embed.set_footer(text="Ban = permanent deletion  ·  Kick = temporary suspension")
    return embed


class UsersView(ui.View):
    def __init__(self, admin_user: discord.User, page: int = 0):
        super().__init__(timeout=300)
        self._admin  = admin_user
        self.page    = page
        self._users: list = []
        self._total: int  = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        admin_channel_id = os.environ.get("DISCORD_ADMIN_CHANNEL_ID")
        if admin_channel_id and str(interaction.channel_id) != admin_channel_id:
            await interaction.response.send_message(
                "⛔ User management is only available in the admin channel.", ephemeral=True
            )
            return False
        return True

    async def load(self):
        self._total = await count_discord_users()
        self._users = [dict(u) for u in await list_discord_users(
            limit=PAGE_SIZE,
            offset=self.page * PAGE_SIZE,
        )]

    def _rebuild_items(self):
        self.clear_items()

        for i, u in enumerate(self._users[:4]):
            sel = UserActionSelect(
                discord_id=u["discord_id"],
                discord_name=u["discord_name"],
                is_active=u["is_active"],
                users_view=self,
            )
            self.add_item(sel)

        total_pages = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)

        prev_btn = ui.Button(
            label="◀ Prev",
            style=discord.ButtonStyle.secondary,
            custom_id="users_prev",
            disabled=(self.page <= 0),
            row=4,
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)

        next_btn = ui.Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            custom_id="users_next",
            disabled=(self.page >= total_pages - 1),
            row=4,
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)

    async def refresh(self, interaction: discord.Interaction, edit_original: bool = False):
        await self.load()
        self._rebuild_items()
        embed = _users_embed(self._users, self.page, self._total)
        if edit_original:
            try:
                await interaction.edit_original_response(embed=embed, view=self)
            except Exception:
                pass
        else:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    async def send_initial(self, interaction: discord.Interaction):
        await self.load()
        self._rebuild_items()
        embed = _users_embed(self._users, self.page, self._total)
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def _prev_page(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        await self.refresh(interaction)

    async def _next_page(self, interaction: discord.Interaction):
        self.page += 1
        await self.refresh(interaction)
