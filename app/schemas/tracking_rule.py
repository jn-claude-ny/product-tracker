from marshmallow import Schema, fields, validate


class TrackingRuleSchema(Schema):
    id = fields.Int(dump_only=True)
    website_id = fields.Int(required=True)
    name = fields.Str()
    rule_type = fields.Str(required=True, validate=validate.OneOf(['keyword', 'brand', 'category']))
    rule_value = fields.Str(required=True)
    alert_on_new = fields.Bool()
    alert_on_price_drop = fields.Bool()
    alert_on_back_in_stock = fields.Bool()
    price_threshold_type = fields.Str(allow_none=True, validate=validate.OneOf(['absolute', 'percentage']))
    price_threshold_value = fields.Decimal(as_string=True, allow_none=True)
    min_price = fields.Decimal(as_string=True, allow_none=True)
    max_price = fields.Decimal(as_string=True, allow_none=True)
    is_active = fields.Bool()


class TrackingRuleCreateSchema(Schema):
    name = fields.Str(allow_none=True)
    rule_type = fields.Str(required=True, validate=validate.OneOf(['keyword', 'brand', 'category']))
    rule_value = fields.Str(required=True, validate=validate.Length(min=1, max=512))
    alert_on_new = fields.Bool(missing=True)
    alert_on_price_drop = fields.Bool(missing=True)
    alert_on_back_in_stock = fields.Bool(missing=True)
    price_threshold_type = fields.Str(allow_none=True, validate=validate.OneOf(['absolute', 'percentage']))
    price_threshold_value = fields.Decimal(as_string=True, allow_none=True)
    min_price = fields.Decimal(as_string=True, allow_none=True)
    max_price = fields.Decimal(as_string=True, allow_none=True)
    is_active = fields.Bool(missing=True)
