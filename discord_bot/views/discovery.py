"""
Product discovery flow:
  /discover → DiscoveryView (store select, filters, search, paginated results)
  Selecting a product hands off to OrderCreationView (views/order.py)

View modes:
  grid — one embed with thumbnail of first product, all products as inline fields
  list — one embed per product with full image, rich detail lines
"""
import logging
from typing import Optional

import discord
from discord import ui

from discord_bot.utils.database import (
    get_websites,
    get_products,
    get_distinct_brands,
)

log = logging.getLogger(__name__)

GENDERS = ["men", "women", "unisex"]
PAGE_SIZE = 5

# Accent colours
COLOR_DEFAULT = discord.Color.from_rgb(88, 101, 242)   # Discord blurple
COLOR_SALE    = discord.Color.from_rgb(254, 75, 75)    # Red for sale
COLOR_NEW     = discord.Color.from_rgb(87, 242, 135)   # Green for new


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------

class SearchModal(ui.Modal, title="Search Products"):
    query = ui.TextInput(label="Search term", placeholder="e.g. Air Max, Jordan…", max_length=100)

    def __init__(self, discovery_view: "DiscoveryView"):
        super().__init__()
        self._dv = discovery_view

    async def on_submit(self, interaction: discord.Interaction):
        self._dv.search_query = self.query.value
        self._dv.page = 1
        await self._dv.refresh(interaction)


class PriceRangeModal(ui.Modal, title="Set Price Range"):
    min_price = ui.TextInput(label="Min price (leave blank for none)", required=False, max_length=10)
    max_price = ui.TextInput(label="Max price (leave blank for none)", required=False, max_length=10)

    def __init__(self, discovery_view: "DiscoveryView"):
        super().__init__()
        self._dv = discovery_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self._dv.min_price = float(self.min_price.value) if self.min_price.value else None
        except ValueError:
            self._dv.min_price = None
        try:
            self._dv.max_price = float(self.max_price.value) if self.max_price.value else None
        except ValueError:
            self._dv.max_price = None
        self._dv.page = 1
        await self._dv.refresh(interaction)


# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------

def _flags(p: dict) -> str:
    parts = []
    if p.get("is_on_sale"):
        parts.append("🏷️ **SALE**")
    if p.get("is_new"):
        parts.append("🆕 **NEW**")
    if not p.get("available"):
        parts.append("❌ **OOS**")
    return "  ".join(parts) if parts else "✅ In Stock"


def _price_str(p: dict) -> str:
    if p.get("price_current"):
        return f"**${p['price_current']:.2f}**"
    return "N/A"


def _build_grid_embed(state: "DiscoveryView", products: list, total: int) -> discord.Embed:
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    has_active = _has_active_filters(state)
    color = COLOR_SALE if state.is_on_sale else (COLOR_NEW if state.is_new else COLOR_DEFAULT)

    embed = discord.Embed(
        title="🛍️  Product Discovery",
        color=color,
    )
    embed.set_footer(text=f"Page {state.page} / {total_pages}  •  {total:,} result(s)  •  Grid view")

    filter_line = _filter_summary_line(state)
    if filter_line:
        embed.description = f"╔ **Active filters:** {filter_line}"
    else:
        embed.description = "Browse the full catalogue or use the filters below."

    if not products:
        embed.add_field(name="No results", value="Try adjusting your filters.", inline=False)
        return embed

    for p in products:
        title = (p.get("title") or "Unknown")[:50]
        brand = p.get("brand") or ""
        img = p.get("image") or ""
        img_line = f"\n[🖼]({img})" if img else ""
        embed.add_field(
            name=f"**{brand}** — {title}",
            value=f"{_price_str(p)}\n{_flags(p)}{img_line}",
            inline=True,
        )

    return embed


def _build_list_embed(state: "DiscoveryView", products: list, total: int) -> discord.Embed:
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    has_active = _has_active_filters(state)
    color = COLOR_SALE if state.is_on_sale else (COLOR_NEW if state.is_new else COLOR_DEFAULT)

    embed = discord.Embed(
        title="🛍️  Product Discovery",
        color=color,
    )
    embed.set_footer(text=f"Page {state.page} / {total_pages}  •  {total:,} result(s)  •  List view")

    filter_line = _filter_summary_line(state)
    if filter_line:
        embed.description = f"╔ **Active filters:** {filter_line}"
    else:
        embed.description = "Browse the full catalogue or use the filters below."

    if not products:
        embed.add_field(name="No results", value="Try adjusting your filters.", inline=False)
        return embed

    for i, p in enumerate(products):
        title = (p.get("title") or "Unknown")[:60]
        brand = p.get("brand") or "Unknown Brand"
        gender_tag = f"`{p.get('gender', '').capitalize()}`  " if p.get("gender") else ""
        img = p.get("image") or ""
        lines = [
            f"💰 {_price_str(p)}   {gender_tag}{_flags(p)}",
        ]
        if p.get("url"):
            lines.append(f"[🔗 View Product]({p['url']})")
        if img:
            lines.append(f"[🖼 Image]({img})")
        embed.add_field(
            name=f"{i+1}. {brand} — {title}",
            value="\n".join(lines),
            inline=False,
        )

    return embed


# ---------------------------------------------------------------------------
# Main DiscoveryView (state container)
# ---------------------------------------------------------------------------

class DiscoveryView(ui.View):
    def __init__(self, interaction_user: discord.User):
        super().__init__(timeout=300)
        self.user = interaction_user

        # Filter state
        self.website_id: Optional[int] = None
        self.brand: Optional[str] = None
        self.gender: Optional[str] = None
        self.search_query: Optional[str] = None
        self.is_on_sale: Optional[bool] = None
        self.is_new: Optional[bool] = None
        self.min_price: Optional[float] = None
        self.max_price: Optional[float] = None
        self.page: int = 1
        self.view_mode: str = "grid"   # "grid" | "list"

        self._result_data: dict = {"total": 0, "products": []}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your panel.", ephemeral=True)
            return False
        return True

    def reset_filters(self):
        self.website_id = None
        self.brand = None
        self.gender = None
        self.search_query = None
        self.is_on_sale = None
        self.is_new = None
        self.min_price = None
        self.max_price = None
        self.page = 1

    async def refresh(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        self._result_data = await get_products(
            website_id=self.website_id,
            brand=self.brand,
            gender=self.gender,
            search=self.search_query,
            is_on_sale=self.is_on_sale,
            is_new=self.is_new,
            min_price=self.min_price,
            max_price=self.max_price,
            page=self.page,
            per_page=PAGE_SIZE,
        )
        embed, view = await self._build(interaction)
        await interaction.edit_original_response(embed=embed, view=view)

    async def _build(self, interaction: discord.Interaction):
        total = self._result_data["total"]
        products = self._result_data["products"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

        if self.view_mode == "list":
            embed = _build_list_embed(self, products, total)
        else:
            embed = _build_grid_embed(self, products, total)

        view = _DiscoveryControlView(self, interaction, products, self.page, total_pages)
        await view.populate_stores()
        return embed, view

    async def send_initial(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self._result_data = await get_products(page=1, per_page=PAGE_SIZE)
        embed, view = await self._build(interaction)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ---------------------------------------------------------------------------
# Control view (rebuilt fresh on every render)
# ---------------------------------------------------------------------------

class _DiscoveryControlView(ui.View):
    def __init__(
        self,
        state: DiscoveryView,
        source_interaction: discord.Interaction,
        products: list,
        page: int,
        total_pages: int,
    ):
        super().__init__(timeout=300)
        self._state = state
        self._src = source_interaction

        # Row 0: store select (added async via populate_stores)
        self._store_select: Optional[ui.Select] = None

        # Row 1: gender select
        gender_select = ui.Select(
            placeholder="👤 Gender (all)",
            custom_id="gender_select",
            min_values=0,
            max_values=1,
            options=[discord.SelectOption(
                label=g.capitalize(),
                value=g,
                default=(state.gender == g),
            ) for g in GENDERS],
            row=1,
        )
        gender_select.callback = self._on_gender_select
        self.add_item(gender_select)

        # Row 2: action buttons
        sale_active = bool(state.is_on_sale)
        sale_btn = ui.Button(
            label="🏷️ Sale ✓" if sale_active else "🏷️ Sale",
            style=discord.ButtonStyle.success if sale_active else discord.ButtonStyle.secondary,
            custom_id="toggle_sale",
            row=2,
        )
        sale_btn.callback = self._toggle_sale
        self.add_item(sale_btn)

        new_active = bool(state.is_new)
        new_btn = ui.Button(
            label="🆕 New ✓" if new_active else "🆕 New",
            style=discord.ButtonStyle.success if new_active else discord.ButtonStyle.secondary,
            custom_id="toggle_new",
            row=2,
        )
        new_btn.callback = self._toggle_new
        self.add_item(new_btn)

        price_label = (
            f"💰 ${state.min_price:.0f}–${state.max_price:.0f}"
            if state.min_price or state.max_price
            else "💰 Price"
        )
        price_btn = ui.Button(label=price_label, style=discord.ButtonStyle.secondary, custom_id="price_range", row=2)
        price_btn.callback = self._open_price_modal
        self.add_item(price_btn)

        search_label = ("🔎 '" + state.search_query[:12] + "…'") if state.search_query else "🔎 Search"
        search_btn = ui.Button(label=search_label, style=discord.ButtonStyle.primary, custom_id="search", row=2)
        search_btn.callback = self._open_search_modal
        self.add_item(search_btn)

        # Row 3: product select (only when results exist)
        if products:
            prod_options = [
                discord.SelectOption(
                    label=f"{(p.get('brand') or '')[:20]} — {(p.get('title') or '')[:55]}",
                    value=str(p["id"]),
                    description=f"${p['price_current']:.2f}" if p.get("price_current") else "N/A",
                )
                for p in products
            ]
            product_select = ui.Select(
                placeholder="📦 Select a product to track…",
                custom_id="product_select",
                options=prod_options,
                row=3,
            )
            product_select.callback = self._on_product_select
            self.add_item(product_select)

        # Row 4: pagination + view toggle + reset
        prev_btn = ui.Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            custom_id="prev_page",
            disabled=(page <= 1),
            row=4,
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)

        next_btn = ui.Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            custom_id="next_page",
            disabled=(page >= total_pages),
            row=4,
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)

        toggle_label = "☰ List" if state.view_mode == "grid" else "⊞ Grid"
        view_toggle = ui.Button(
            label=toggle_label,
            style=discord.ButtonStyle.secondary,
            custom_id="view_toggle",
            row=4,
        )
        view_toggle.callback = self._toggle_view
        self.add_item(view_toggle)

        has_active = _has_active_filters(state)
        reset_btn = ui.Button(
            label="✖ Reset",
            style=discord.ButtonStyle.danger if has_active else discord.ButtonStyle.secondary,
            custom_id="reset_filters",
            disabled=not has_active,
            row=4,
        )
        reset_btn.callback = self._reset_filters
        self.add_item(reset_btn)

    async def populate_stores(self):
        websites = await get_websites()
        if not websites:
            return
        options = []
        for w in websites:
            options.append(discord.SelectOption(
                label=w["name"],
                value=str(w["id"]),
                default=(self._state.website_id == w["id"]),
            ))
        store_select = ui.Select(
            placeholder="🏪 Store (all)",
            custom_id="store_select",
            min_values=0,
            max_values=1,
            options=options,
            row=0,
        )
        store_select.callback = self._on_store_select
        self._store_select = store_select
        self.add_item(store_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._state.user.id:
            await interaction.response.send_message("This is not your panel.", ephemeral=True)
            return False
        return True

    # --- Callbacks ---

    async def _on_store_select(self, interaction: discord.Interaction):
        values = interaction.data.get("values", [])
        self._state.website_id = int(values[0]) if values else None
        self._state.page = 1
        await self._state.refresh(interaction)

    async def _on_gender_select(self, interaction: discord.Interaction):
        values = interaction.data.get("values", [])
        self._state.gender = values[0] if values else None
        self._state.page = 1
        await self._state.refresh(interaction)

    async def _toggle_sale(self, interaction: discord.Interaction):
        self._state.is_on_sale = None if self._state.is_on_sale else True
        self._state.page = 1
        await self._state.refresh(interaction)

    async def _toggle_new(self, interaction: discord.Interaction):
        self._state.is_new = None if self._state.is_new else True
        self._state.page = 1
        await self._state.refresh(interaction)

    async def _open_price_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PriceRangeModal(self._state))

    async def _open_search_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SearchModal(self._state))

    async def _prev_page(self, interaction: discord.Interaction):
        self._state.page = max(1, self._state.page - 1)
        await self._state.refresh(interaction)

    async def _next_page(self, interaction: discord.Interaction):
        self._state.page += 1
        await self._state.refresh(interaction)

    async def _toggle_view(self, interaction: discord.Interaction):
        self._state.view_mode = "list" if self._state.view_mode == "grid" else "grid"
        await self._state.refresh(interaction)

    async def _reset_filters(self, interaction: discord.Interaction):
        self._state.reset_filters()
        await self._state.refresh(interaction)

    async def _on_product_select(self, interaction: discord.Interaction):
        product_id = int(interaction.data["values"][0])
        from discord_bot.views.order import OrderCreationView
        view = OrderCreationView(interaction_user=interaction.user, product_id=product_id)
        await view.send(interaction)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_active_filters(state: "DiscoveryView") -> bool:
    return any([
        state.website_id,
        state.brand,
        state.gender,
        state.search_query,
        state.is_on_sale,
        state.is_new,
        state.min_price,
        state.max_price,
    ])


def _filter_summary_line(state: "DiscoveryView") -> str:
    parts = []
    if state.website_id:
        parts.append(f"Store #{state.website_id}")
    if state.brand:
        parts.append(f"Brand: {state.brand}")
    if state.gender:
        parts.append(state.gender.capitalize())
    if state.search_query:
        parts.append("'" + state.search_query + "'")
    if state.is_on_sale:
        parts.append("On Sale")
    if state.is_new:
        parts.append("New Arrivals")
    if state.min_price or state.max_price:
        lo = f"${state.min_price:.0f}" if state.min_price else "$0"
        hi = f"${state.max_price:.0f}" if state.max_price else "∞"
        parts.append(f"{lo}–{hi}")
    return "  ·  ".join(parts)
