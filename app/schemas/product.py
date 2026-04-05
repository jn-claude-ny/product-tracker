from marshmallow import Schema, fields


class ProductSchema(Schema):
    id = fields.Int(dump_only=True)
    website_id = fields.Int()
    url = fields.Str()
    sku = fields.Str()
    title = fields.Str()
    brand = fields.Str()
    image = fields.Str()
    categories = fields.List(fields.Str())
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
