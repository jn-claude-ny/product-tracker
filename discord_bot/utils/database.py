"""
Async-compatible database helpers for the Discord bot.
Uses asyncpg for non-blocking queries so the Discord event loop is never blocked.
"""
import asyncpg
import os
from typing import Optional, List, Dict, Any


_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# DiscordPendingUser helpers
# ---------------------------------------------------------------------------

async def get_pending_user(discord_id: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM discord_pending_users WHERE discord_id = $1", discord_id
    )


async def create_pending_user(
    discord_id: str,
    discord_name: str,
    discord_avatar_url: Optional[str],
    reason: Optional[str],
) -> asyncpg.Record:
    pool = await get_pool()
    return await pool.fetchrow(
        """
        INSERT INTO discord_pending_users
            (discord_id, discord_name, discord_avatar_url, reason,
             request_status, created_at, updated_at)
        VALUES ($1, $2, $3, $4, 'pending', NOW(), NOW())
        ON CONFLICT (discord_id) DO UPDATE
            SET discord_name = EXCLUDED.discord_name,
                discord_avatar_url = EXCLUDED.discord_avatar_url,
                reason = EXCLUDED.reason,
                request_status = 'pending',
                updated_at = NOW()
        RETURNING *
        """,
        discord_id, discord_name, discord_avatar_url, reason,
    )


async def update_pending_user_message(pending_id: int, message_id: str, channel_id: str):
    pool = await get_pool()
    await pool.execute(
        """UPDATE discord_pending_users
           SET admin_message_id = $1, admin_channel_id = $2, updated_at = NOW()
           WHERE id = $3""",
        message_id, channel_id, pending_id,
    )


async def get_pending_user_by_id(pending_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM discord_pending_users WHERE id = $1", pending_id
    )


async def approve_pending_user(pending_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        """UPDATE discord_pending_users
           SET request_status = 'approved', updated_at = NOW()
           WHERE id = $1 AND request_status = 'pending'
           RETURNING *""",
        pending_id,
    )


async def reject_pending_user(pending_id: int, rejection_reason: Optional[str]) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        """UPDATE discord_pending_users
           SET request_status = 'rejected', rejection_reason = $2, updated_at = NOW()
           WHERE id = $1 AND request_status = 'pending'
           RETURNING *""",
        pending_id, rejection_reason,
    )


async def get_all_pending_requests() -> List[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM discord_pending_users WHERE request_status = 'pending' ORDER BY created_at"
    )


# ---------------------------------------------------------------------------
# User & UserDiscordLink helpers
# ---------------------------------------------------------------------------

async def get_user_by_discord_id(discord_id: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        """SELECT u.*, udl.discord_id, udl.discord_name, udl.discord_avatar_url
           FROM users u
           JOIN user_discord_links udl ON udl.user_id = u.id
           WHERE udl.discord_id = $1
             AND u.is_active = TRUE""",
        discord_id,
    )


async def get_suspended_user_by_discord_id(discord_id: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        """SELECT u.id FROM users u
           JOIN user_discord_links udl ON udl.user_id = u.id
           WHERE udl.discord_id = $1
             AND u.is_active = FALSE""",
        discord_id,
    )


async def create_user_from_discord(
    discord_id: str,
    discord_name: str,
    discord_avatar_url: Optional[str],
    password_hash: str,
) -> asyncpg.Record:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            email = f"discord_{discord_id}@tracker.local"
            user = await conn.fetchrow(
                """INSERT INTO users (email, password_hash, created_at, is_active, role)
                   VALUES ($1, $2, NOW(), TRUE, 'user')
                   ON CONFLICT (email) DO NOTHING
                   RETURNING *""",
                email, password_hash,
            )
            if user is None:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE email = $1", email
                )
            await conn.execute(
                """INSERT INTO user_discord_links
                       (user_id, discord_id, discord_name, discord_avatar_url, created_at)
                   VALUES ($1, $2, $3, $4, NOW())
                   ON CONFLICT (discord_id) DO NOTHING""",
                user["id"], discord_id, discord_name, discord_avatar_url,
            )
            return user


# ---------------------------------------------------------------------------
# Website helpers
# ---------------------------------------------------------------------------

async def get_websites() -> List[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT id, name, base_url FROM websites ORDER BY name"
    )


# ---------------------------------------------------------------------------
# Product helpers
# ---------------------------------------------------------------------------

async def get_products(
    website_id: Optional[int] = None,
    brand: Optional[str] = None,
    gender: Optional[str] = None,
    search: Optional[str] = None,
    is_on_sale: Optional[bool] = None,
    is_new: Optional[bool] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    page: int = 1,
    per_page: int = 5,
) -> Dict[str, Any]:
    pool = await get_pool()
    conditions = ["1=1"]
    params: list = []
    idx = 1

    if website_id is not None:
        conditions.append(f"website_id = ${idx}")
        params.append(website_id)
        idx += 1
    if brand:
        conditions.append(f"brand ILIKE ${idx}")
        params.append(f"%{brand}%")
        idx += 1
    if gender:
        conditions.append(f"gender = ${idx}")
        params.append(gender)
        idx += 1
    if search:
        conditions.append(f"(title ILIKE ${idx} OR brand ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1
    if is_on_sale is not None:
        conditions.append(f"is_on_sale = ${idx}")
        params.append(is_on_sale)
        idx += 1
    if is_new is not None:
        conditions.append(f"is_new = ${idx}")
        params.append(is_new)
        idx += 1
    if min_price is not None:
        conditions.append(f"price_current >= ${idx}")
        params.append(min_price)
        idx += 1
    if max_price is not None:
        conditions.append(f"price_current <= ${idx}")
        params.append(max_price)
        idx += 1

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    total = await pool.fetchval(f"SELECT COUNT(*) FROM products WHERE {where}", *params)
    rows = await pool.fetch(
        f"SELECT id, title, brand, price_current, image, url, gender, is_on_sale, is_new, available "
        f"FROM products WHERE {where} ORDER BY updated_at DESC LIMIT ${idx} OFFSET ${idx+1}",
        *params, per_page, offset,
    )
    return {"total": total, "page": page, "per_page": per_page, "products": [dict(r) for r in rows]}


async def get_product_by_id(product_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow("SELECT * FROM products WHERE id = $1", product_id)


async def get_product_variants(product_id: int) -> List[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM product_variants WHERE product_id = $1 ORDER BY size",
        product_id,
    )


async def get_distinct_brands(website_id: Optional[int] = None) -> List[str]:
    pool = await get_pool()
    if website_id:
        rows = await pool.fetch(
            "SELECT DISTINCT brand FROM products WHERE website_id = $1 AND brand IS NOT NULL ORDER BY brand",
            website_id,
        )
    else:
        rows = await pool.fetch(
            "SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand"
        )
    return [r["brand"] for r in rows]


# ---------------------------------------------------------------------------
# DiscordOrder helpers
# ---------------------------------------------------------------------------

async def create_discord_order(
    discord_user_id: str,
    discord_channel_id: Optional[str],
    user_id: int,
    product_id: int,
    alert_type: str,
    size_filter: Optional[str],
) -> asyncpg.Record:
    pool = await get_pool()
    return await pool.fetchrow(
        """INSERT INTO discord_orders
               (discord_user_id, discord_channel_id, user_id, product_id,
                alert_type, size_filter, status, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, 'active', NOW(), NOW())
           RETURNING *""",
        discord_user_id, discord_channel_id, user_id, product_id,
        alert_type, size_filter,
    )


async def get_discord_orders(discord_user_id: str) -> List[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        """SELECT o.*, p.title as product_title, p.brand as product_brand,
                  p.image as product_image, p.price_current as product_price
           FROM discord_orders o
           JOIN products p ON p.id = o.product_id
           WHERE o.discord_user_id = $1
           ORDER BY o.created_at DESC""",
        discord_user_id,
    )


async def get_discord_order_by_id(order_id: int, discord_user_id: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        """SELECT o.*, p.title as product_title, p.brand as product_brand
           FROM discord_orders o
           JOIN products p ON p.id = o.product_id
           WHERE o.id = $1 AND o.discord_user_id = $2""",
        order_id, discord_user_id,
    )


async def cancel_discord_order(order_id: int, discord_user_id: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        """UPDATE discord_orders
           SET status = 'cancelled', updated_at = NOW()
           WHERE id = $1 AND discord_user_id = $2 AND status = 'active'
           RETURNING *""",
        order_id, discord_user_id,
    )


async def get_active_discord_orders_for_alert(product_id: int, alert_type: str) -> List[asyncpg.Record]:
    """Used by the alert engine to find orders to notify."""
    pool = await get_pool()
    return await pool.fetch(
        """SELECT o.*, p.title as product_title, p.price_current as product_price,
                  p.price_previous as product_price_previous, p.image as product_image
           FROM discord_orders o
           JOIN products p ON p.id = o.product_id
           WHERE o.product_id = $1
             AND o.alert_type = $2
             AND o.status = 'active'""",
        product_id, alert_type,
    )


async def update_order_last_alert(order_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE discord_orders SET last_alert_at = NOW(), updated_at = NOW() WHERE id = $1",
        order_id,
    )


# ---------------------------------------------------------------------------
# Admin user management helpers
# ---------------------------------------------------------------------------

async def list_discord_users(limit: int = 20, offset: int = 0) -> List[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        """SELECT u.id, u.email, u.is_active, u.role, u.created_at,
                  udl.discord_id, udl.discord_name, udl.discord_avatar_url
           FROM users u
           JOIN user_discord_links udl ON udl.user_id = u.id
           ORDER BY u.created_at DESC
           LIMIT $1 OFFSET $2""",
        limit, offset,
    )


async def count_discord_users() -> int:
    pool = await get_pool()
    return await pool.fetchval(
        "SELECT COUNT(*) FROM users u JOIN user_discord_links udl ON udl.user_id = u.id"
    )


async def ban_discord_user(discord_id: str) -> Optional[asyncpg.Record]:
    """Hard ban: delete user record and all associated data (cascades via FK)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT u.id, u.email, udl.discord_name
                   FROM users u
                   JOIN user_discord_links udl ON udl.user_id = u.id
                   WHERE udl.discord_id = $1""",
                discord_id,
            )
            if not row:
                return None
            await conn.execute("DELETE FROM users WHERE id = $1", row["id"])
            return row


async def kick_discord_user(discord_id: str) -> Optional[asyncpg.Record]:
    """Soft kick: deactivate user (is_active = FALSE). Can be reversed."""
    pool = await get_pool()
    return await pool.fetchrow(
        """UPDATE users SET is_active = FALSE
           FROM user_discord_links udl
           WHERE users.id = udl.user_id
             AND udl.discord_id = $1
           RETURNING users.id, users.email, udl.discord_name""",
        discord_id,
    )


async def reactivate_discord_user(discord_id: str) -> Optional[asyncpg.Record]:
    """Reverse a kick."""
    pool = await get_pool()
    return await pool.fetchrow(
        """UPDATE users SET is_active = TRUE
           FROM user_discord_links udl
           WHERE users.id = udl.user_id
             AND udl.discord_id = $1
           RETURNING users.id, users.email, udl.discord_name""",
        discord_id,
    )
