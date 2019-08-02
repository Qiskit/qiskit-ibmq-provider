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
from marshmallow.fields import String, Url, Dict
from qiskit.validation import BaseSchema, bind_schema, BaseModel


class TokenSchema(BaseSchema):
    """Schema for Token."""

    # Required properties.
    token_id = String('id', required=True)


@bind_schema(TokenSchema)
class Token(BaseModel):
    """Model for Token.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``TokenSchema``.

    Attributes:
        token_id (str): long term access token.
    """

    def __init__(self, token_id, **kwargs):
        self.token_id = token_id

        super().__init__(**kwargs)


class UserSchema(BaseSchema):
    """Schema for User."""

    # Required properties.
    urls = Dict(Url(), required=True)


@bind_schema(UserSchema)
class User(BaseModel):
    """Model for User.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``UserSchema``.

    Attributes:
        urls (str): urls associated with APIs.
    """

    def __init__(self, urls, **kwargs):
        self.urls = urls

        super().__init__(**kwargs)
