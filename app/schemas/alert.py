from marshmallow import Schema, fields


class AlertSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int()
    product_id = fields.Int()
    alert_type = fields.Str()
    state_hash = fields.Str()
    sent_at = fields.DateTime(dump_only=True)
