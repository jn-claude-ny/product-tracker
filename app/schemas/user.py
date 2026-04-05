from marshmallow import Schema, fields, validate


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    email = fields.Email(required=True)
    created_at = fields.DateTime(dump_only=True)
    is_active = fields.Bool(dump_only=True)
    role = fields.Str(dump_only=True)


class UserCreateSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(min=5, max=255))
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128), load_only=True)


class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
