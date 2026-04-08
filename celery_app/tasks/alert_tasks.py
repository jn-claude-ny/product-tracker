# ---------------------------------------------------------------------------
# alert_tasks.py
# ---------------------------------------------------------------------------
# TWO SEPARATE ALERT PIPELINES live here:
#
# 1. RULE-BASED ALERTS  (evaluate_alerts)
#    Triggered during bulk crawls for every new product snapshot.
#    Checks TrackingRule rows (keyword / brand / category rules set per website).
#    e.g. "Alert me for any Nike product under $100 on ShopWSS"
#
# 2. TRACKED PRODUCT ALERTS  (evaluate_tracked_product_alerts)
#    Triggered after scraping a specific product a user is watching.
#    Checks TrackedProduct rows (per-product rules set by users).
#    Supports price direction (above/below), size filters, availability filters.
#    e.g. "Alert me when this exact ASOS product, size US 10, comes back in stock"
#
# BOTH pipelines share:
#   - State hashing       -> prevents duplicate alerts for the same state
#   - Cooldown windows    -> website.alert_cooldown_minutes (default 60 min)
#   - send_discord_alert  -> builds embed, POSTs to Discord webhook(s)
#   - _publish_realtime_alert -> pushes to Redis pub/sub for WebSocket clients
#
# DISCORD WEBHOOK PRIORITY:
#   1. tracked_product.discord_webhook_url  (per-product, set by user)
#   2. DiscordWebhook rows linked to website (site-level, set by admin)
#   Both are sent to if both are configured.
# ---------------------------------------------------------------------------

from celery_app.celery import celery
from datetime import datetime, timedelta
import logging
import httpx
import hashlib
import redis
from app.extensions import db
from app.models.alert import Alert
from app.models.product import Product
from app.models.product_snapshot import ProductSnapshot
from app.models.tracking_rule import TrackingRule
from app.models.discord_webhook import DiscordWebhook
from app.models.website import Website
from app.config import Config

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def evaluate_alerts(self, product_id, snapshot_id):
    """
    Rule-based alert evaluation for bulk crawls.

    Called after a product snapshot is created during a site-wide crawl.
    Checks every active TrackingRule for the website and fires alerts for
    any matching rule that isn't in cooldown.

    Alert types produced: new_match, price_drop, back_in_stock
    """
    logger.info(f'Evaluating alerts for product {product_id}, snapshot {snapshot_id}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            product = Product.query.get(product_id)
            if not product:
                logger.error(f'Product {product_id} not found')
                return {'status': 'error', 'message': 'Product not found'}
            
            current_snapshot = ProductSnapshot.query.get(snapshot_id)
            if not current_snapshot:
                logger.error(f'Snapshot {snapshot_id} not found')
                return {'status': 'error', 'message': 'Snapshot not found'}
            
            previous_snapshot = ProductSnapshot.query.filter(
                ProductSnapshot.product_id == product_id,
                ProductSnapshot.id < snapshot_id
            ).order_by(ProductSnapshot.created_at.desc()).first()
            
            website = Website.query.get(product.website_id)
            tracking_rules = TrackingRule.query.filter_by(
                website_id=product.website_id,
                is_active=True
            ).all()
            
            alerts_created = 0
            
            for rule in tracking_rules:
                if not _matches_rule(product, rule):
                    continue
                
                alert_type = _determine_alert_type(
                    rule, current_snapshot, previous_snapshot
                )
                
                if not alert_type:
                    continue
                
                if _is_in_cooldown(product, rule, alert_type, current_snapshot, website):
                    logger.debug(f'Alert in cooldown for product {product_id}, rule {rule.id}')
                    continue
                
                state_hash = _compute_state_hash(rule.id, current_snapshot)
                
                alert = Alert(
                    user_id=website.user_id,
                    product_id=product_id,
                    alert_type=alert_type,
                    state_hash=state_hash
                )
                db.session.add(alert)
                db.session.commit()
                
                send_discord_alert.apply_async(
                    args=[alert.id],
                    queue='alert_queue'
                )
                
                alerts_created += 1
            
            return {
                'status': 'success',
                'alerts_created': alerts_created
            }
            
    except Exception as e:
        logger.error(f'Error evaluating alerts: {e}')
        raise


def _matches_rule(product: Product, rule: TrackingRule) -> bool:
    """
    Check whether a product matches a TrackingRule.
    rule_type options: 'keyword' (title/brand), 'brand' (exact), 'category'
    """
    if rule.rule_type == 'keyword':
        keyword = rule.rule_value.lower()
        title = (product.title or '').lower()
        brand = (product.brand or '').lower()
        return keyword in title or keyword in brand
    
    elif rule.rule_type == 'brand':
        brand = (product.brand or '').lower()
        return brand == rule.rule_value.lower()
    
    elif rule.rule_type == 'category':
        categories = [c.lower() for c in (product.categories or [])]
        return rule.rule_value.lower() in categories
    
    return False


def _determine_alert_type(rule: TrackingRule, current: ProductSnapshot,
                          previous: ProductSnapshot) -> str:
    """
    Determine which alert type to fire (if any) by comparing two snapshots.
    Returns: 'new_match', 'price_drop', 'back_in_stock', or None.
    """
    if not previous and rule.alert_on_new:
        if rule.min_price and current.price and float(current.price) < float(rule.min_price):
            return None
        if rule.max_price and current.price and float(current.price) > float(rule.max_price):
            return None
        return 'new_match'
    
    if previous and rule.alert_on_price_drop:
        if current.price and previous.price:
            current_price = float(current.price)
            previous_price = float(previous.price)
            
            if current_price < previous_price:
                drop_amount = previous_price - current_price
                
                if rule.price_threshold_type == 'absolute':
                    if rule.price_threshold_value and drop_amount >= float(rule.price_threshold_value):
                        return 'price_drop'
                elif rule.price_threshold_type == 'percentage':
                    if rule.price_threshold_value:
                        drop_percentage = (drop_amount / previous_price) * 100
                        if drop_percentage >= float(rule.price_threshold_value):
                            return 'price_drop'
                else:
                    return 'price_drop'
    
    if previous and rule.alert_on_back_in_stock:
        prev_avail = (previous.availability or '').lower()
        curr_avail = (current.availability or '').lower()
        
        if 'out' in prev_avail and 'in' in curr_avail:
            return 'back_in_stock'
    
    return None


def _is_in_cooldown(product: Product, rule: TrackingRule, alert_type: str,
                    snapshot: ProductSnapshot, website: Website) -> bool:
    """
    Returns True if an identical alert was already sent within the cooldown window.

    'Identical' is defined by state_hash: same rule + same price + same availability.
    This prevents spam when a product stays in the same state across multiple crawls.
    """
    state_hash = _compute_state_hash(rule.id, snapshot)

    cooldown_minutes = website.alert_cooldown_minutes
    cutoff_time = datetime.utcnow() - timedelta(minutes=cooldown_minutes)

    existing_alert = Alert.query.filter(
        Alert.product_id == product.id,
        Alert.alert_type == alert_type,
        Alert.state_hash == state_hash,
        Alert.sent_at >= cutoff_time
    ).first()

    return existing_alert is not None


def _compute_state_hash(rule_id: int, snapshot: ProductSnapshot) -> str:
    """
    Produce a fingerprint of (rule, price, availability) for deduplication.
    If price and availability haven't changed since the last alert, the hash
    will be identical and the cooldown check will suppress a new alert.
    """
    hash_string = f"{rule_id}:{snapshot.price}:{snapshot.availability}"
    return hashlib.sha256(hash_string.encode()).hexdigest()


@celery.task(bind=True, max_retries=3)
def evaluate_tracked_product_alerts(self, product_id, snapshot_id):
    """
    Tracked-product alert evaluation.

    Called by on_scrape_complete after scraping a specifically tracked product.
    Checks every TrackedProduct row for this product_id and evaluates:

      1. PRICE DIRECTION RULE
         tracked.price_direction = 'above' or 'below'
         tracked.price_reference = the threshold price
         -> fires 'price_increase' or 'price_drop' alert

      2. VARIANT / SIZE TRACKING
         tracked.size_filter = comma-separated sizes (e.g. '08.0,09.0')
                               or empty = check ALL variants
         tracked.availability_filter = 'InStock', 'OutOfStock', 'LowStock'
                                        or empty = no filter
         -> fires 'availability_match' alert with size + availability context
            included in the Discord embed

    Both checks can fire in the same evaluation run for the same TrackedProduct.
    Each alert is independently deduplicated via state hash + cooldown.
    """
    logger.info(f'Evaluating tracked product alerts for {product_id}, snapshot {snapshot_id}')

    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            from app.models.tracked_product import TrackedProduct
            from app.models.product_variant import ProductVariant

            product = Product.query.get(product_id)
            if not product:
                logger.error(f'Product {product_id} not found')
                return {'status': 'error', 'message': 'Product not found'}

            current_snapshot = ProductSnapshot.query.get(snapshot_id)
            if not current_snapshot:
                logger.error(f'Snapshot {snapshot_id} not found')
                return {'status': 'error', 'message': 'Snapshot not found'}

            tracked_products = TrackedProduct.query.filter_by(product_id=product_id).all()
            alerts_created = 0

            for tracked in tracked_products:
                triggered_alerts = []  # list of (alert_type, extra_context)

                # --- Price direction check ---
                if tracked.price_direction and tracked.price_reference and current_snapshot.price:
                    current_price = float(current_snapshot.price)
                    ref_price = float(tracked.price_reference)
                    if tracked.price_direction == 'above' and current_price > ref_price:
                        logger.info(f'[TP {tracked.id}] Price rule TRIGGERED: {current_price} > {ref_price} (above)')
                        triggered_alerts.append(('price_increase', {}))
                    elif tracked.price_direction == 'below' and current_price < ref_price:
                        logger.info(f'[TP {tracked.id}] Price rule TRIGGERED: {current_price} < {ref_price} (below)')
                        triggered_alerts.append(('price_drop', {}))
                    else:
                        logger.info(f'[TP {tracked.id}] Price rule NOT triggered: current={current_price}, ref={ref_price}, direction={tracked.price_direction}')

                # --- Variant / size tracking ---
                variants_to_check = []
                all_variants = ProductVariant.query.filter_by(product_id=product_id).all()

                if tracked.size_filter:
                    variants_to_check = [v for v in all_variants if v.size and v.size in tracked.size_filter]
                    logger.info(f'[TP {tracked.id}] Checking {len(variants_to_check)}/{len(all_variants)} variants matching size_filter={tracked.size_filter}')
                else:
                    variants_to_check = all_variants

                for variant in variants_to_check:
                    avail_str = 'In Stock' if variant.available else 'Out of Stock'
                    logger.info(f'[TP {tracked.id}] Variant size={variant.size} available={variant.available} ({avail_str})')

                    # Availability filter match
                    if tracked.availability_filter:
                        stock_state = (variant.stock_state or '').lower()
                        avail_filter = tracked.availability_filter.lower()
                        # Normalise: 'instock' matches True, 'outofstock' matches False
                        filter_wants_in = 'instock' in avail_filter or avail_filter == 'in stock'
                        filter_wants_out = 'outofstock' in avail_filter or avail_filter == 'out of stock'
                        filter_wants_low = 'low' in avail_filter

                        rule_result = False
                        if filter_wants_in and variant.available is True:
                            rule_result = True
                        elif filter_wants_out and variant.available is False:
                            rule_result = True
                        elif filter_wants_low and 'low' in stock_state:
                            rule_result = True

                        logger.info(f'[TP {tracked.id}] Availability rule for size={variant.size}: filter={tracked.availability_filter} result={rule_result}')
                        if rule_result:
                            triggered_alerts.append(('availability_match', {
                                'size': variant.size,
                                'color': variant.color,
                                'available': variant.available,
                                'stock_state': variant.stock_state,
                                'variant_price': float(variant.price) if variant.price else None,
                            }))

                # --- Emit an alert for each trigger ---
                for alert_type, ctx in triggered_alerts:
                    if _is_tracked_product_in_cooldown(tracked, product, alert_type, current_snapshot, ctx):
                        logger.info(f'[TP {tracked.id}] Alert {alert_type} in cooldown, skipping')
                        continue

                    state_hash = _compute_tracked_state_hash(tracked.id, current_snapshot, ctx)

                    alert = Alert(
                        user_id=tracked.user_id,
                        product_id=product_id,
                        alert_type=alert_type,
                        state_hash=state_hash
                    )
                    db.session.add(alert)
                    db.session.commit()

                    send_discord_alert.apply_async(
                        args=[alert.id],
                        kwargs={'extra_context': ctx},
                        queue='alert_queue'
                    )

                    alerts_created += 1
                    logger.info(f'[TP {tracked.id}] Created alert {alert.id} type={alert_type} ctx={ctx}')

            return {
                'status': 'success',
                'alerts_created': alerts_created
            }

    except Exception as e:
        logger.error(f'Error evaluating tracked product alerts: {e}')
        raise


def _is_tracked_product_in_cooldown(tracked_product, product, alert_type, snapshot, ctx=None):
    """
    Cooldown check for tracked-product alerts.
    Same logic as _is_in_cooldown but uses _compute_tracked_state_hash which
    includes the size from ctx so that alerts for different sizes don't block
    each other's cooldowns.
    """
    from app.models.website import Website
    website = Website.query.get(product.website_id)

    state_hash = _compute_tracked_state_hash(tracked_product.id, snapshot, ctx)
    cooldown_minutes = website.alert_cooldown_minutes if website else 60
    cutoff_time = datetime.utcnow() - timedelta(minutes=cooldown_minutes)

    existing_alert = Alert.query.filter(
        Alert.product_id == product.id,
        Alert.alert_type == alert_type,
        Alert.state_hash == state_hash,
        Alert.sent_at >= cutoff_time
    ).first()

    return existing_alert is not None


def _compute_tracked_state_hash(tracked_product_id, snapshot, ctx=None):
    """
    State hash for tracked-product alerts.
    Includes the size key from ctx so that:
      - size US 10 in stock and size US 11 in stock produce DIFFERENT hashes
      - re-alerting on the same size at the same price is blocked by cooldown
      - re-alerting on a DIFFERENT size is NOT blocked
    Format: 'tp:<tracked_id>:<price>:<availability>:<size>'
    """
    size_key = (ctx or {}).get('size', '')
    hash_string = f"tp:{tracked_product_id}:{snapshot.price}:{snapshot.availability}:{size_key}"
    return hashlib.sha256(hash_string.encode()).hexdigest()


@celery.task(bind=True, max_retries=3)
def send_discord_alert(self, alert_id, extra_context=None):
    """
    Send a Discord alert for a saved Alert row.

    Webhook priority:
      1. tracked_product.discord_webhook_url  (per-product URL stored on the TrackedProduct)
      2. DiscordWebhook rows for the website  (site-level webhooks configured in settings)
    Both are sent to if both are present (deduped by URL).

    Also publishes to Redis pub/sub channel 'alerts:user:<user_id>' so connected
    WebSocket clients get a real-time notification in the UI.

    extra_context: dict passed from evaluate_tracked_product_alerts with size/color/
    availability details for variant-level alerts. Used in embed description and fields.
    """
    logger.info(f'Sending Discord alert {alert_id} ctx={extra_context}')

    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            alert = Alert.query.get(alert_id)
            if not alert:
                logger.error(f'Alert {alert_id} not found')
                return {'status': 'error', 'message': 'Alert not found'}

            product = Product.query.get(alert.product_id)
            website = Website.query.get(product.website_id)

            webhooks = DiscordWebhook.query.filter_by(
                website_id=website.id,
                is_active=True
            ).all()

            # Also check tracked product's directly stored webhook URL
            from app.models.tracked_product import TrackedProduct
            tracked = TrackedProduct.query.filter_by(
                user_id=alert.user_id,
                product_id=alert.product_id
            ).first()
            tracked_webhook_url = tracked.discord_webhook_url if tracked else None

            # Collect all unique URLs to send to
            webhook_urls = {w.webhook_url: f'webhook:{w.id}' for w in webhooks}
            if tracked_webhook_url and tracked_webhook_url not in webhook_urls:
                webhook_urls[tracked_webhook_url] = 'tracked_product'

            if not webhook_urls:
                logger.warning(f'No active webhooks for website {website.id}')
                return {'status': 'success', 'webhooks_sent': 0}

            latest_snapshot = ProductSnapshot.query.filter_by(
                product_id=product.id
            ).order_by(ProductSnapshot.created_at.desc()).first()

            embed = _create_discord_embed(alert, product, latest_snapshot, extra_context or {})

            sent_count = 0
            for url, label in webhook_urls.items():
                try:
                    _send_to_discord(url, embed)
                    sent_count += 1
                    logger.info(f'Sent Discord alert {alert_id} to {label}')
                except Exception as e:
                    logger.error(f'Failed to send to {label}: {e}')

            _publish_realtime_alert(alert, product, latest_snapshot)

            return {
                'status': 'success',
                'webhooks_sent': sent_count
            }

    except Exception as e:
        logger.error(f'Error sending Discord alert: {e}')
        raise


def _create_discord_embed(alert: Alert, product: Product, snapshot: ProductSnapshot, ctx: dict = None) -> dict:
    """
    Build a Discord embed dict for the alert.

    Structure:
      title       = product name (clickable hyperlink via embed.url)
      description = alert type emoji/label + optional size availability line
      fields      = Brand, Price, Size, Color, Status, Inventory, SKU
      thumbnail   = product image
      color       = sidebar color by alert type

    ctx (extra_context from variant alerts):
      size, color, available, stock_state, variant_price
    When ctx.size is present, the embed shows per-size availability instead of
    the generic product-level status field.
    """
    ctx = ctx or {}
    color_map = {
        'new_match': 0x00ff00,
        'price_drop': 0xff9900,
        'price_increase': 0xf97316,
        'back_in_stock': 0x0099ff,
        'availability_match': 0x22c55e,
    }

    title_map = {
        'new_match': '🆕 New Product Match',
        'price_drop': '💰 Price Drop',
        'price_increase': '📈 Price Increase',
        'back_in_stock': '✅ Back in Stock',
        'availability_match': '📦 Availability Alert',
    }

    size_label = ctx.get('size')
    color_label = ctx.get('color')

    # Title = product name (becomes the clickable hyperlink in Discord)
    embed_title = product.title or 'Unknown Product'

    # Description = alert type badge + optional size availability line
    desc_parts = [title_map.get(alert.alert_type, '🔔 Alert')]
    if size_label:
        avail_label = 'In Stock ✅' if ctx.get('available') else 'Out of Stock ❌'
        desc_parts.append(f'Size **{size_label}** — {avail_label}')
    description = '\n'.join(desc_parts)

    embed = {
        'title': embed_title,
        'description': description,
        'url': product.url,
        'color': color_map.get(alert.alert_type, 0x808080),
        'fields': [],
        'timestamp': datetime.utcnow().isoformat()
    }

    if product.brand:
        embed['fields'].append({'name': 'Brand', 'value': product.brand, 'inline': True})

    # Size-level price overrides snapshot price when available
    price_val = ctx.get('variant_price') or (float(snapshot.price) if snapshot and snapshot.price else None)
    if price_val:
        embed['fields'].append({'name': 'Price', 'value': f"{snapshot.currency or '$'} {price_val:.2f}", 'inline': True})

    if size_label:
        embed['fields'].append({'name': 'Size', 'value': size_label, 'inline': True})

    if color_label:
        embed['fields'].append({'name': 'Color', 'value': color_label, 'inline': True})

    if not size_label and snapshot and snapshot.availability:
        embed['fields'].append({'name': 'Status', 'value': snapshot.availability, 'inline': True})

    if product.inventory_level is not None:
        embed['fields'].append({'name': 'Inventory', 'value': f'{product.inventory_level} in stock', 'inline': True})

    if product.sku:
        embed['fields'].append({'name': 'SKU', 'value': product.sku, 'inline': True})

    if product.image:
        embed['thumbnail'] = {'url': product.image}

    return embed


def _send_to_discord(webhook_url: str, embed: dict):
    """
    POST the embed to a Discord webhook URL.
    Discord expects {'embeds': [embed_dict]}.
    Raises httpx.HTTPStatusError on non-2xx response.
    """
    payload = {
        'embeds': [embed]
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(webhook_url, json=payload)
        response.raise_for_status()


def _publish_realtime_alert(alert: Alert, product: Product, snapshot: ProductSnapshot):
    """
    Publish alert to Redis pub/sub so the Flask-SocketIO server can push it
    to connected browser clients in real time.

    Channel: 'alerts:user:<user_id>'
    The frontend subscribes to this channel via WebSocket and appends the
    alert to the notifications panel without a page refresh.
    """
    try:
        r = redis.from_url(Config.REDIS_URL)
        
        message = {
            'alert_id': alert.id,
            'alert_type': alert.alert_type,
            'product_id': product.id,
            'product_title': product.title,
            'product_url': product.url,
            'product_image': product.image,
            'price': str(snapshot.price) if snapshot.price else None,
            'currency': snapshot.currency,
            'availability': snapshot.availability,
            'sent_at': alert.sent_at.isoformat()
        }
        
        import json
        r.publish(f'alerts:user:{alert.user_id}', json.dumps(message))
        
    except Exception as e:
        logger.error(f'Failed to publish realtime alert: {e}')
