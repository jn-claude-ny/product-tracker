"""
Order history flow (/orders):
  - Ephemeral select menu (up to 25 orders, paginated with Next button)
  - Selecting an order shows its detail embed + Cancel button (if active)
"""
import logging
from typing import List

import discord
from discord import ui

from discord_bot.utils.database import (
    get_discord_orders,
    get_discord_order_by_id,
    cancel_discord_order,
)

log = logging.getLogger(__name__)

PAGE_SIZE = 25  # Discord select menu hard limit


class OrdersView(ui.View):
    """Top-level orders list view."""

    def __init__(self, interaction_user: discord.User, orders: List[dict], page: int = 0):
        super().__init__(timeout=300)
        self.user = interaction_user
        self.all_orders = orders
        self.page = page
        self._build_select()

    def _build_select(self):
        self.clear_items()
        start = self.page * PAGE_SIZE
        end = start + PAGE_SIZE
        slice_ = self.all_orders[start:end]

        if not slice_:
            return

        options = []
        for o in slice_:
            status_icon = "🟢" if o["status"] == "active" else "🔴"
            label = f"{status_icon} #{o['id']} — {(o.get('product_brand') or '')} {(o.get('product_title') or '')}".strip()
            label = label[:100]
            desc = f"{o['alert_type']} | size: {o.get('size_filter') or 'all'} | {o['status']}"
            options.append(discord.SelectOption(label=label, value=str(o["id"]), description=desc[:100]))

        select = ui.Select(
            placeholder="📋 Select an order to view…",
            custom_id="orders_select",
            options=options,
            row=0,
        )
        select.callback = self._on_order_select
        self.add_item(select)

        total_pages = max(1, (len(self.all_orders) + PAGE_SIZE - 1) // PAGE_SIZE)

        if self.page > 0:
            prev_btn = ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, custom_id="orders_prev", row=1)
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)

        if end < len(self.all_orders):
            next_btn = ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="orders_next", row=1)
            next_btn.callback = self._next_page
            self.add_item(next_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your panel.", ephemeral=True)
            return False
        return True

    async def _on_order_select(self, interaction: discord.Interaction):
        order_id = int(interaction.data["values"][0])
        order = await get_discord_order_by_id(order_id, str(interaction.user.id))

        if not order:
            await interaction.response.send_message("Order not found.", ephemeral=True)
            return

        embed = _build_order_embed(order)

        if order["status"] == "active":
            view = OrderDetailView(
                interaction_user=interaction.user,
                order=order,
                parent_orders=self.all_orders,
                parent_page=self.page,
            )
        else:
            view = _BackView(interaction_user=interaction.user, all_orders=self.all_orders, page=self.page)

        await interaction.response.edit_message(embed=embed, view=view)

    async def _prev_page(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        self._build_select()
        embed = _orders_list_embed(self.all_orders, self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _next_page(self, interaction: discord.Interaction):
        self.page += 1
        self._build_select()
        embed = _orders_list_embed(self.all_orders, self.page)
        await interaction.response.edit_message(embed=embed, view=self)


class OrderDetailView(ui.View):
    """Shows a single order with a Cancel button."""

    def __init__(
        self,
        interaction_user: discord.User,
        order: dict,
        parent_orders: list,
        parent_page: int,
    ):
        super().__init__(timeout=300)
        self.user = interaction_user
        self.order = order
        self.parent_orders = parent_orders
        self.parent_page = parent_page

        cancel_btn = ui.Button(
            label="🚫 Cancel Order",
            style=discord.ButtonStyle.danger,
            custom_id="cancel_order",
            row=0,
        )
        cancel_btn.callback = self._cancel_order
        self.add_item(cancel_btn)

        back_btn = ui.Button(
            label="◀ Back to Orders",
            style=discord.ButtonStyle.secondary,
            custom_id="back_orders",
            row=0,
        )
        back_btn.callback = self._back_to_orders
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your panel.", ephemeral=True)
            return False
        return True

    async def _cancel_order(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        cancelled = await cancel_discord_order(
            order_id=self.order["id"],
            discord_user_id=str(interaction.user.id),
        )

        if not cancelled:
            await interaction.followup.send("Order already cancelled or not found.", ephemeral=True)
            return

        # Update local copy in parent list
        for o in self.parent_orders:
            if o["id"] == self.order["id"]:
                o["status"] = "cancelled"
                break

        embed = discord.Embed(
            title="🚫 Order Cancelled",
            color=discord.Color.red(),
            description=(
                f"Order **#{self.order['id']}** has been cancelled.\n"
                f"Product: **{self.order.get('product_brand', '')} {self.order.get('product_title', '')}**"
            ),
        )
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(embed=embed, view=self)

    async def _back_to_orders(self, interaction: discord.Interaction):
        view = OrdersView(
            interaction_user=interaction.user,
            orders=self.parent_orders,
            page=self.parent_page,
        )
        embed = _orders_list_embed(self.parent_orders, self.parent_page)
        await interaction.response.edit_message(embed=embed, view=view)


class _BackView(ui.View):
    """Minimal view for cancelled/completed orders (no cancel button)."""

    def __init__(self, interaction_user: discord.User, all_orders: list, page: int):
        super().__init__(timeout=300)
        self.user = interaction_user
        self._all_orders = all_orders
        self._page = page

        back_btn = ui.Button(
            label="◀ Back to Orders",
            style=discord.ButtonStyle.secondary,
            custom_id="back_orders_ro",
            row=0,
        )
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your panel.", ephemeral=True)
            return False
        return True

    async def _back(self, interaction: discord.Interaction):
        view = OrdersView(
            interaction_user=interaction.user,
            orders=self._all_orders,
            page=self._page,
        )
        embed = _orders_list_embed(self._all_orders, self._page)
        await interaction.response.edit_message(embed=embed, view=view)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _orders_list_embed(orders: list, page: int) -> discord.Embed:
    total = len(orders)
    active = sum(1 for o in orders if o["status"] == "active")
    embed = discord.Embed(
        title="📋 Your Orders",
        color=discord.Color.blurple(),
        description=f"**{total}** total order(s) — **{active}** active",
    )
    if not orders:
        embed.description = "You have no orders yet. Use `/discover` to find products."
    return embed


def _build_order_embed(order: dict) -> discord.Embed:
    status_color = discord.Color.green() if order["status"] == "active" else discord.Color.red()
    status_icon = "🟢" if order["status"] == "active" else "🔴"
    alert_label = "Restock" if order["alert_type"] == "restock" else "Price Drop"

    embed = discord.Embed(
        title=f"Order #{order['id']}",
        color=status_color,
    )
    embed.add_field(
        name="Product",
        value=f"{order.get('product_brand', '')} {order.get('product_title', '')}".strip() or "Unknown",
        inline=False,
    )
    embed.add_field(name="Alert Type", value=alert_label, inline=True)
    embed.add_field(name="Size", value=order.get("size_filter") or "All sizes", inline=True)
    embed.add_field(name="Status", value=f"{status_icon} {order['status'].capitalize()}", inline=True)
    if order.get("last_alert_at"):
        embed.add_field(name="Last Alert", value=str(order["last_alert_at"])[:19], inline=True)
    embed.add_field(name="Created", value=str(order["created_at"])[:19], inline=True)
    return embed
