# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exceptions related to the IBM Q Experience API."""

from ..api import ApiError as ApiErrorV1


class ApiError(ApiErrorV1):
    """Generic IBM Q API error."""
    pass


class RequestsApiError(ApiError):
    """Exception re-raising a RequestException."""
    def __init__(self, original_exception, *args, **kwargs):
        self.original_exception = original_exception
        super().__init__(*args, **kwargs)


class WebsocketError(ApiError):
    """Exceptions related to websockets."""
    pass


class WebsocketIBMQProtocolError(WebsocketError):
    """Exceptions related to IBM Q protocol error."""
    pass


class WebsocketAuthenticationError(WebsocketError):
    """Exception caused during websocket authentication."""
    pass


class WebsocketTimeoutError(WebsocketError):
    """Timeout during websocket communication."""
    pass


class AuthenticationLicenseError(ApiError):
    """Exception due to user not accepting latest license agreement via web."""
    pass
