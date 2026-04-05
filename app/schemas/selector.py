from marshmallow import Schema, fields, validate


class SelectorSchema(Schema):
    id = fields.Int(dump_only=True)
    website_id = fields.Int(required=True)
    field_name = fields.Str(required=True)
    selector_type = fields.Str(validate=validate.OneOf(['css', 'xpath']))
    selector_value = fields.Str(required=True)
    post_process = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class SelectorCreateSchema(Schema):
    field_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    selector_type = fields.Str(missing='css', validate=validate.OneOf(['css', 'xpath']))
    selector_value = fields.Str(required=True, validate=validate.Length(min=1))
    post_process = fields.Str(allow_none=True)
