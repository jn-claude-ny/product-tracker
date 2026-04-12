from marshmallow import Schema, fields, validate





class WebsiteSchema(Schema):

    id = fields.Int(dump_only=True)

    user_id = fields.Int(dump_only=True)

    name = fields.Str(required=True)

    base_url = fields.Str(required=True)

    allowed_domains = fields.List(fields.Str())

    sitemap_url = fields.Str(required=True)

    use_playwright = fields.Bool()

    wait_selector = fields.Str(allow_none=True)

    scrape_delay_seconds = fields.Decimal(as_string=True)

    randomize_delay = fields.Bool()

    proxy_group = fields.Str(allow_none=True)

    alert_cooldown_minutes = fields.Int()

    cron_schedule = fields.Str(allow_none=True)

    discord_webhook_url = fields.Str(allow_none=True)

    # Crawl state tracking
    crawl_state = fields.Str(dump_only=True)
    crawl_progress = fields.Int(dump_only=True)
    total_products_expected = fields.Int(dump_only=True)
    products_discovered = fields.Int(dump_only=True)
    products_processed = fields.Int(dump_only=True)
    last_crawl_completed_at = fields.DateTime(dump_only=True, allow_none=True)

    sitemap_etag = fields.Str(dump_only=True)

    sitemap_last_checked = fields.DateTime(dump_only=True)

    is_crawling = fields.Method('get_is_crawling', dump_only=True)

    active_task_count = fields.Method('get_active_task_count', dump_only=True)

    queued_task_count = fields.Method('get_queued_task_count', dump_only=True)

    product_count = fields.Method('get_product_count', dump_only=True)

    last_error = fields.Str(dump_only=True, allow_none=True)

    last_error_at = fields.DateTime(dump_only=True, allow_none=True)

    created_at = fields.DateTime(dump_only=True)

    updated_at = fields.DateTime(dump_only=True)



    def get_product_count(self, obj):

        return obj.products.count() if hasattr(obj, 'products') else 0



    def get_is_crawling(self, obj):

        activity = getattr(obj, '_crawl_activity', None)

        if isinstance(activity, dict):

            return bool(activity.get('is_crawling', False))

        return bool(getattr(obj, 'is_crawling', False))



    def get_active_task_count(self, obj):

        activity = getattr(obj, '_crawl_activity', None)

        if isinstance(activity, dict):

            return int(activity.get('active_task_count', 0))

        return 0



    def get_queued_task_count(self, obj):

        activity = getattr(obj, '_crawl_activity', None)

        if isinstance(activity, dict):

            return int(activity.get('queued_task_count', 0))

        return 0





class WebsiteCreateSchema(Schema):

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))

    base_url = fields.Str(required=True, validate=validate.Length(min=1, max=512))

    allowed_domains = fields.List(fields.Str(), load_default=[])

    sitemap_url = fields.Str(required=True, validate=validate.Length(min=1, max=512))

    use_playwright = fields.Bool(load_default=False)

    wait_selector = fields.Str(allow_none=True)

    scrape_delay_seconds = fields.Decimal(as_string=True, load_default='3.0')

    randomize_delay = fields.Bool(load_default=True)

    proxy_group = fields.Str(allow_none=True)

    alert_cooldown_minutes = fields.Int(load_default=60)

    cron_schedule = fields.Str(allow_none=True)

    discord_webhook_url = fields.Str(allow_none=True)





class WebsiteUpdateSchema(Schema):

    name = fields.Str(validate=validate.Length(min=1, max=255))

    base_url = fields.Str(validate=validate.Length(min=1, max=512))

    allowed_domains = fields.List(fields.Str())

    sitemap_url = fields.Str(validate=validate.Length(min=1, max=512))

    use_playwright = fields.Bool()

    wait_selector = fields.Str(allow_none=True)

    scrape_delay_seconds = fields.Decimal(as_string=True)

    randomize_delay = fields.Bool()

    proxy_group = fields.Str(allow_none=True)

    alert_cooldown_minutes = fields.Int()

    cron_schedule = fields.Str(allow_none=True)

    discord_webhook_url = fields.Str(validate=validate.Length(max=512), allow_none=True, load_default=None)
