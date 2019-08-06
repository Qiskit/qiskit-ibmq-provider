# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Model and schema for authentication."""
from marshmallow import fields
from qiskit.validation import BaseSchema, bind_schema


class LoginTokenRequestSchema(BaseSchema):
    """Schema for LoginTokenRequest"""

    # Required properties
    api_token = fields.String(attribute='apiToken', required=True,
                              metadata='api token associated to the user')


class LoginTokenResponseSchema(BaseSchema):
    """Schema for LoginTokenResponse."""

    # Required properties.
    id = fields.String(required=True, metadata='long term access token')


class UserApiUrlResponseSchema(BaseSchema):
    """Nested schema for UserInfoResponse"""

    # Required properties.
    protocol = fields.String(required=True, metadata='api protocol')
    url = fields.Url(required=True, metadata='URL address to the api')


class UserInfoResponseSchema(BaseSchema):
    """Schema for UserInfoResponse."""

    # Required properties.
    urls = fields.Dict(fields.Nested(UserApiUrlResponseSchema), many=True, required=True,
                       metadata='urls and corresponding protocols associated with APIs')


@bind_schema(LoginTokenRequestSchema)
class LoginTokenRequest:
    """Model for LoginTokenRequestSchema.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``LoginTokenRequestSchema``.
    """

    def __init__(self, api_token, **kwargs):
        self.api_token = api_token

        super().__init__(**kwargs)


@bind_schema(LoginTokenResponseSchema)
class LoginTokenResponse:
    """Model for LoginTokenResponseSchema.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``LoginTokenResponseSchema``.
    """

    def __init__(self, id, **kwargs):
        self.id = id

        super().__init__(**kwargs)


@bind_schema(UserInfoResponseSchema)
class UserInfoResponse:
    """Model for UserInfoResponseSchema.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``UserInfoResponseSchema``.
    """

    def __init__(self, urls, **kwargs):
        self.urls = urls

        super().__init__(**kwargs)
