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
    hash_string = f"{rule_id}:{snapshot.price}:{snapshot.availability}"
    return hashlib.sha256(hash_string.encode()).hexdigest()


@celery.task(bind=True, max_retries=3)
def evaluate_tracked_product_alerts(self, product_id, snapshot_id):
    """Evaluate alerts for tracked products with price direction tracking."""
    logger.info(f'Evaluating tracked product alerts for {product_id}, snapshot {snapshot_id}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from app.models.tracked_product import TrackedProduct
            
            product = Product.query.get(product_id)
            if not product:
                logger.error(f'Product {product_id} not found')
                return {'status': 'error', 'message': 'Product not found'}
            
            current_snapshot = ProductSnapshot.query.get(snapshot_id)
            if not current_snapshot:
                logger.error(f'Snapshot {snapshot_id} not found')
                return {'status': 'error', 'message': 'Snapshot not found'}
            
            # Get all tracked products for this product
            tracked_products = TrackedProduct.query.filter_by(product_id=product_id).all()
            
            alerts_created = 0
            
            for tracked in tracked_products:
                alert_type = None
                
                # Check price direction tracking
                if tracked.price_direction and tracked.price_reference and current_snapshot.price:
                    current_price = float(current_snapshot.price)
                    ref_price = float(tracked.price_reference)
                    
                    if tracked.price_direction == 'above' and current_price > ref_price:
                        alert_type = 'price_increase'
                    elif tracked.price_direction == 'below' and current_price < ref_price:
                        alert_type = 'price_drop'
                
                # Check availability
                if not alert_type and tracked.availability_filter:
                    current_avail = (current_snapshot.availability or '').lower()
                    if tracked.availability_filter.lower() in current_avail:
                        alert_type = 'availability_match'
                
                # Check size filter
                if not alert_type and tracked.size_filter and current_snapshot.size_data:
                    # Size-based alerting would require size-specific data in snapshot
                    pass
                
                if alert_type:
                    # Check cooldown
                    if _is_tracked_product_in_cooldown(tracked, product, alert_type, current_snapshot):
                        continue
                    
                    state_hash = _compute_tracked_state_hash(tracked.id, current_snapshot)
                    
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
                        queue='alert_queue'
                    )
                    
                    alerts_created += 1
            
            return {
                'status': 'success',
                'alerts_created': alerts_created
            }
            
    except Exception as e:
        logger.error(f'Error evaluating tracked product alerts: {e}')
        raise


def _is_tracked_product_in_cooldown(tracked_product, product, alert_type, snapshot):
    """Check if alert is in cooldown for tracked product."""
    from app.models.website import Website
    website = Website.query.get(product.website_id)
    
    state_hash = _compute_tracked_state_hash(tracked_product.id, snapshot)
    cooldown_minutes = website.alert_cooldown_minutes if website else 60
    cutoff_time = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
    
    existing_alert = Alert.query.filter(
        Alert.product_id == product.id,
        Alert.alert_type == alert_type,
        Alert.state_hash == state_hash,
        Alert.sent_at >= cutoff_time
    ).first()
    
    return existing_alert is not None


def _compute_tracked_state_hash(tracked_product_id, snapshot):
    """Compute state hash for tracked product alert."""
    hash_string = f"tp:{tracked_product_id}:{snapshot.price}:{snapshot.availability}"
    return hashlib.sha256(hash_string.encode()).hexdigest()


@celery.task(bind=True, max_retries=3)
def send_discord_alert(self, alert_id):
    logger.info(f'Sending Discord alert {alert_id}')
    
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
            
            if not webhooks:
                logger.warning(f'No active webhooks for website {website.id}')
                return {'status': 'success', 'webhooks_sent': 0}
            
            latest_snapshot = ProductSnapshot.query.filter_by(
                product_id=product.id
            ).order_by(ProductSnapshot.created_at.desc()).first()
            
            embed = _create_discord_embed(alert, product, latest_snapshot)
            
            sent_count = 0
            for webhook in webhooks:
                try:
                    _send_to_discord(webhook.webhook_url, embed)
                    sent_count += 1
                except Exception as e:
                    logger.error(f'Failed to send to webhook {webhook.id}: {e}')
            
            _publish_realtime_alert(alert, product, latest_snapshot)
            
            return {
                'status': 'success',
                'webhooks_sent': sent_count
            }
            
    except Exception as e:
        logger.error(f'Error sending Discord alert: {e}')
        raise


def _create_discord_embed(alert: Alert, product: Product, snapshot: ProductSnapshot) -> dict:
    color_map = {
        'new_match': 0x00ff00,
        'price_drop': 0xff9900,
        'back_in_stock': 0x0099ff
    }
    
    title_map = {
        'new_match': '🆕 New Product Match',
        'price_drop': '💰 Price Drop',
        'back_in_stock': '✅ Back in Stock'
    }
    
    embed = {
        'title': title_map.get(alert.alert_type, 'Alert'),
        'description': product.title or 'No title',
        'url': product.url,
        'color': color_map.get(alert.alert_type, 0x808080),
        'fields': [],
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if product.brand:
        embed['fields'].append({
            'name': 'Brand',
            'value': product.brand,
            'inline': True
        })
    
    if snapshot.price:
        embed['fields'].append({
            'name': 'Price',
            'value': f"{snapshot.currency or 'USD'} {snapshot.price}",
            'inline': True
        })
    
    if snapshot.availability:
        embed['fields'].append({
            'name': 'Availability',
            'value': snapshot.availability,
            'inline': True
        })
    
    if product.image:
        embed['thumbnail'] = {'url': product.image}
    
    return embed


def _send_to_discord(webhook_url: str, embed: dict):
    payload = {
        'embeds': [embed]
    }
    
    with httpx.Client(timeout=10.0) as client:
        response = client.post(webhook_url, json=payload)
        response.raise_for_status()


def _publish_realtime_alert(alert: Alert, product: Product, snapshot: ProductSnapshot):
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
