"""
Access request flow:
  /request  → ReasonModal → creates pending record → notifies admin channel
  Admin channel → AdminApprovalView (persistent) → Approve/Reject buttons
"""
import logging
import os

import discord
from discord import ui

from discord_bot.utils.database import (
    create_pending_user,
    get_pending_user_by_id,
    approve_pending_user,
    reject_pending_user,
    get_user_by_discord_id,
    create_user_from_discord,
    update_pending_user_message,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modal: ask for optional reason
# ---------------------------------------------------------------------------

class ReasonModal(ui.Modal, title="Request Access"):
    reason = ui.TextInput(
        label="Why do you want access? (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
        placeholder="Let the admin know why you'd like access…",
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = interaction.user
        pending = await create_pending_user(
            discord_id=str(user.id),
            discord_name=str(user),
            discord_avatar_url=str(user.display_avatar.url) if user.display_avatar else None,
            reason=self.reason.value or None,
        )

        admin_channel_id = os.environ.get("DISCORD_ADMIN_CHANNEL_ID")
        if not admin_channel_id:
            await interaction.followup.send(
                "⚠️ Admin channel not configured. Contact an admin directly.",
                ephemeral=True,
            )
            return

        try:
            channel = interaction.client.get_channel(int(admin_channel_id))
            if channel is None:
                channel = await interaction.client.fetch_channel(int(admin_channel_id))
        except Exception:
            await interaction.followup.send(
                "⚠️ Could not reach admin channel. Contact an admin directly.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="New Access Request",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
        embed.add_field(name="Reason", value=self.reason.value or "_No reason given_", inline=False)
        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)

        view = AdminApprovalView(pending_id=pending["id"])
        msg = await channel.send(embed=embed, view=view)

        await update_pending_user_message(
            pending_id=pending["id"],
            message_id=str(msg.id),
            channel_id=str(msg.channel.id),
        )

        await interaction.followup.send(
            "✅ Request sent to the admin. You will be notified when it's reviewed.",
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# Persistent admin approval view
# ---------------------------------------------------------------------------

class AdminApprovalView(ui.View):
    def __init__(self, pending_id: int):
        super().__init__(timeout=None)
        self.pending_id = pending_id
        self.custom_id_prefix = f"admin_approval_{pending_id}"

        approve_btn = ui.Button(
            label="Approve",
            style=discord.ButtonStyle.success,
            custom_id=f"approve_{pending_id}",
            emoji="✅",
        )
        reject_btn = ui.Button(
            label="Reject",
            style=discord.ButtonStyle.danger,
            custom_id=f"reject_{pending_id}",
            emoji="❌",
        )
        approve_btn.callback = self._approve_callback
        reject_btn.callback = self._reject_callback
        self.add_item(approve_btn)
        self.add_item(reject_btn)

    async def _approve_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        pending = await approve_pending_user(self.pending_id)
        if pending is None:
            await interaction.followup.send("Already processed or not found.", ephemeral=True)
            return

        import bcrypt
        password_hash = bcrypt.hashpw(
            os.urandom(24).hex().encode(), bcrypt.gensalt()
        ).decode()

        await create_user_from_discord(
            discord_id=pending["discord_id"],
            discord_name=pending["discord_name"],
            discord_avatar_url=pending["discord_avatar_url"],
            password_hash=password_hash,
        )

        try:
            discord_user = await interaction.client.fetch_user(int(pending["discord_id"]))
            await discord_user.send(
                "✅ **Access granted!** Use `/discover` to browse products and start tracking. "
                "Use `/orders` to view your order history."
            )
        except Exception:
            pass

        for item in self.children:
            item.disabled = True
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(text=f"Approved by {interaction.user}")
        await interaction.message.edit(embed=embed, view=self)

        await interaction.followup.send(
            f"✅ Approved `{pending['discord_name']}`.", ephemeral=True
        )

    async def _reject_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RejectReasonModal(pending_id=self.pending_id, view=self))


class RejectReasonModal(ui.Modal, title="Rejection Reason"):
    reason = ui.TextInput(
        label="Reason for rejection (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    def __init__(self, pending_id: int, view: AdminApprovalView):
        super().__init__()
        self.pending_id = pending_id
        self._approval_view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        pending = await reject_pending_user(self.pending_id, self.reason.value or None)
        if pending is None:
            await interaction.followup.send("Already processed or not found.", ephemeral=True)
            return

        try:
            discord_user = await interaction.client.fetch_user(int(pending["discord_id"]))
            msg = "❌ **Your access request was declined.**"
            if self.reason.value:
                msg += f"\n**Reason:** {self.reason.value}"
            await discord_user.send(msg)
        except Exception:
            pass

        for item in self._approval_view.children:
            item.disabled = True
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_footer(text=f"Rejected by {interaction.user}")
        await interaction.message.edit(embed=embed, view=self._approval_view)

        await interaction.followup.send(
            f"❌ Rejected `{pending['discord_name']}`.", ephemeral=True
        )
