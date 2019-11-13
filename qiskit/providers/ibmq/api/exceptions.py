# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exceptions related to the IBM Q Experience API."""

from typing import Any

from ..exceptions import IBMQError, IBMQErrorCodes


class ApiError(IBMQError):
    """Generic IBM Q API error."""
    error_code = IBMQErrorCodes.GENERIC_API_ERROR


class RequestsApiError(ApiError):
    """Exception re-raising a RequestException."""
    error_code = IBMQErrorCodes.GENERIC_API_ERROR


class WebsocketError(ApiError):
    """Exceptions related to websockets."""
    error_code = IBMQErrorCodes.GENERIC_NETWORK_ERROR


class AuthenticationLicenseError(ApiError):
    """Exception due to user not accepting latest license agreement via web."""
    error_code = IBMQErrorCodes.LICENSE_ERROR


class ApiIBMQProtocolError(ApiError):
    """Exception related to IBM Q API protocol error."""
    error_code = IBMQErrorCodes.API_PROTOCOL_ERROR


class UserTimeoutExceededError(ApiError):
    """Exceptions related to exceeding user defined timeout."""
    error_code = IBMQErrorCodes.REQUEST_TIMEOUT


class WebsocketIBMQProtocolError(WebsocketError):
    """Exceptions related to IBM Q protocol error."""
    error_code = IBMQErrorCodes.API_PROTOCOL_ERROR


class WebsocketAuthenticationError(WebsocketError):
    """Exception caused during websocket authentication."""
    error_code = IBMQErrorCodes.API_AUTHENTICATION_ERROR


class WebsocketTimeoutError(WebsocketError):
    """Timeout during websocket communication."""
    error_code = IBMQErrorCodes.REQUEST_TIMEOUT
