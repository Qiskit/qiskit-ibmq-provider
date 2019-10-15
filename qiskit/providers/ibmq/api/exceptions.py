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

"""Exceptions related to the IBM Q Experience API."""

from ..exceptions import IBMQError


class ApiError(IBMQError):
    """Generic IBM Q API error."""
    pass


class RequestsApiError(ApiError):
    """Exception re-raising a RequestException."""
    pass


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


class ApiIBMQProtocolError(ApiError):
    """Exception related to IBM Q API protocol error."""
    pass


class UserTimeoutExceededError(ApiError):
    """Exceptions related to exceeding user defined timeout."""
    pass
