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
from qiskit.validation import BaseSchema
from qiskit.validation.fields import String, Url, Nested


class LoginTokenRequestSchema(BaseSchema):
    """Schema for LoginTokenRequest"""

    # Required properties
    api_token = String(attribute='apiToken', required=True,
                       description='API token.')


class LoginTokenResponseSchema(BaseSchema):
    """Schema for LoginTokenResponse."""

    # Required properties.
    # pylint: disable=invalid-name
    id = String(required=True, description='access token.')


class UserApiUrlResponseSchema(BaseSchema):
    """Nested schema for UserInfoResponse"""

    # Required properties.
    http = Url(required=True, description='the API URL for http communication.')
    # pylint: disable=invalid-name
    ws = String(required=True, description='the API URL for websocket communication.')


class UserInfoResponseSchema(BaseSchema):
    """Schema for UserInfoResponse."""

    # Required properties.
    urls = Nested(UserApiUrlResponseSchema, required=True,
                  description='base URLs for the services. Currently supported keys: '
                              'http and ws')
