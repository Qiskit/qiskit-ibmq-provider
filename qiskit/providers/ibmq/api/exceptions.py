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

    def __init__(self, *message: Any) -> None:
        """Set the error message and code."""
        super().__init__(*message, error_code=IBMQ_API_ERROR_CODES[type(self)])


class RequestsApiError(ApiError):
    """Exception re-raising a RequestException."""
    pass


class WebsocketError(ApiError):
    """Exceptions related to websockets."""
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


class WebsocketIBMQProtocolError(WebsocketError):
    """Exceptions related to IBM Q protocol error."""
    pass


class WebsocketAuthenticationError(WebsocketError):
    """Exception caused during websocket authentication."""
    pass


class WebsocketTimeoutError(WebsocketError):
    """Timeout during websocket communication."""
    pass


IBMQ_API_ERROR_CODES = {
    ApiError: IBMQErrorCodes.GENERIC_API_ERROR,
    RequestsApiError: IBMQErrorCodes.GENERIC_API_ERROR,
    WebsocketError: IBMQErrorCodes.GENERIC_NETWORK_ERROR,
    WebsocketIBMQProtocolError: IBMQErrorCodes.API_PROTOCOL_ERROR,
    WebsocketAuthenticationError: IBMQErrorCodes.API_AUTHENTICATION_ERROR,
    WebsocketTimeoutError: IBMQErrorCodes.REQUEST_TIMEOUT,
    AuthenticationLicenseError: IBMQErrorCodes.LICENSE_ERROR,
    ApiIBMQProtocolError: IBMQErrorCodes.API_PROTOCOL_ERROR,
    UserTimeoutExceededError: IBMQErrorCodes.REQUEST_TIMEOUT
}
