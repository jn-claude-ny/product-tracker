"""
Order creation flow:
  After a product is selected in discovery, this view shows:
    - Product embed (image, title, brand, price, availability)
    - Alert type select (restock / price_drop)
    - Size select (from product_variants, plus "All sizes")
    - Confirm Order button
"""
import logging
from typing import Optional

import discord
from discord import ui

from discord_bot.utils.database import (
    get_product_by_id,
    get_product_variants,
    get_user_by_discord_id,
    create_discord_order,
)

log = logging.getLogger(__name__)

ALERT_TYPE_OPTIONS = [
    discord.SelectOption(label="🔔 Restock Alert", value="restock", description="Notify when back in stock"),
    discord.SelectOption(label="💸 Price Drop Alert", value="price_drop", description="Notify when price drops"),
]


class OrderCreationView(ui.View):
    def __init__(self, interaction_user: discord.User, product_id: int):
        super().__init__(timeout=300)
        self.user = interaction_user
        self.product_id = product_id
        self.alert_type: str = "restock"
        self.size_filter: Optional[str] = None
        self._product = None
        self._variants = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your panel.", ephemeral=True)
            return False
        return True

    async def send(self, interaction: discord.Interaction):
        self._product = await get_product_by_id(self.product_id)
        if not self._product:
            await interaction.response.send_message("Product not found.", ephemeral=True)
            return

        self._variants = await get_product_variants(self.product_id)
        self._rebuild_components()
        embed = self._build_embed()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    def _build_embed(self) -> discord.Embed:
        p = self._product
        price = p.get("price_current")
        price_str = f"${float(price):.2f}" if price else "N/A"

        embed = discord.Embed(
            title=f"{p.get('brand', '')} {p.get('title', '')}".strip(),
            color=discord.Color.blurple(),
            url=p.get("url"),
        )
        embed.add_field(name="Price", value=price_str, inline=True)
        embed.add_field(
            name="Availability",
            value="✅ In Stock" if p.get("available") else "❌ Out of Stock",
            inline=True,
        )
        if p.get("gender"):
            embed.add_field(name="Gender", value=p["gender"].capitalize(), inline=True)
        if p.get("image"):
            embed.set_thumbnail(url=p["image"])
        embed.set_footer(text=f"Product #{self.product_id} | SKU: {p.get('sku', 'N/A')}")
        return embed

    def _rebuild_components(self):
        self.clear_items()

        # Alert type select
        alert_select = ui.Select(
            placeholder="🔔 Alert type",
            custom_id="alert_type_select",
            options=ALERT_TYPE_OPTIONS,
            row=0,
        )
        alert_select.callback = self._on_alert_type
        self.add_item(alert_select)

        # Size select
        size_options = [discord.SelectOption(label="All sizes", value="all")]
        seen = set()
        for v in self._variants:
            sz = v.get("size")
            if sz and sz not in seen:
                seen.add(sz)
                avail = "✅" if v.get("available") else "❌"
                size_options.append(
                    discord.SelectOption(label=f"{avail} {sz}", value=sz)
                )
        # Discord limit: 25 options
        size_options = size_options[:25]

        size_select = ui.Select(
            placeholder="📐 Size (All sizes)",
            custom_id="size_select",
            options=size_options,
            row=1,
        )
        size_select.callback = self._on_size_select
        self.add_item(size_select)

        # Confirm button
        confirm_btn = ui.Button(
            label="✅ Confirm Order",
            style=discord.ButtonStyle.success,
            custom_id="confirm_order",
            row=2,
        )
        confirm_btn.callback = self._confirm_order
        self.add_item(confirm_btn)

        # Back button
        back_btn = ui.Button(
            label="◀ Back to Discovery",
            style=discord.ButtonStyle.secondary,
            custom_id="back_to_discovery",
            row=2,
        )
        back_btn.callback = self._back_to_discovery
        self.add_item(back_btn)

    async def _on_alert_type(self, interaction: discord.Interaction):
        self.alert_type = interaction.data["values"][0]
        await interaction.response.defer()

    async def _on_size_select(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        self.size_filter = None if value == "all" else value
        await interaction.response.defer()

    async def _confirm_order(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        db_user = await get_user_by_discord_id(str(interaction.user.id))
        if not db_user:
            await interaction.followup.send(
                "❌ You don't have access yet. Run `/request` to request access.",
                ephemeral=True,
            )
            return

        order = await create_discord_order(
            discord_user_id=str(interaction.user.id),
            discord_channel_id=str(interaction.channel_id) if interaction.channel_id else None,
            user_id=db_user["id"],
            product_id=self.product_id,
            alert_type=self.alert_type,
            size_filter=self.size_filter,
        )

        p = self._product
        size_label = self.size_filter or "All sizes"
        alert_label = "Restock" if self.alert_type == "restock" else "Price Drop"

        embed = discord.Embed(
            title="✅ Order Confirmed!",
            color=discord.Color.green(),
            description=(
                f"**Order #{order['id']}** created.\n"
                f"Product: **{p.get('brand', '')} {p.get('title', '')}**\n"
                f"Alert: **{alert_label}**\n"
                f"Size: **{size_label}**\n\n"
                "You'll be @mentioned when the product matches your alert."
            ),
        )

        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(embed=embed, view=self)

    async def _back_to_discovery(self, interaction: discord.Interaction):
        from discord_bot.views.discovery import DiscoveryView
        dv = DiscoveryView(interaction_user=interaction.user)
        await dv.send_initial(interaction)
