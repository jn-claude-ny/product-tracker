from marshmallow import Schema, fields, validate


class DiscordWebhookSchema(Schema):
    id = fields.Int(dump_only=True)
    website_id = fields.Int(required=True)
    webhook_url = fields.Str(required=True)
    is_active = fields.Bool()


class DiscordWebhookCreateSchema(Schema):
    webhook_url = fields.Str(required=True, validate=validate.Length(min=1, max=512))
    is_active = fields.Bool(load_default=True)
