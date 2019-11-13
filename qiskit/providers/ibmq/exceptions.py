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

"""Exception for the IBMQ module."""

import re

from qiskit.exceptions import QiskitError

from .errorcodes import IBMQErrorCodes


class IBMQError(QiskitError):
    """Base class for errors raised by the IBMQ provider module."""

    error_code = IBMQErrorCodes.GENERIC_ERROR

    def __init__(self, message: str) -> None:
        """Create a new IBMQError instance."""
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Format the error string with the error code."""
        # Strip previous error code.
        plain_message = re.sub(r' \[[0-9]{4}\]\.$', '', self.message)
        return '{} [{}].'.format(plain_message, self.error_code.value)


class IBMQAccountError(IBMQError):
    """Base class for errors raised by account management."""
    error_code = IBMQErrorCodes.GENERIC_CREDENTIALS_ERROR


class IBMQAccountCredentialsNotFound(IBMQAccountError):
    """Error raised when credentials not found."""
    error_code = IBMQErrorCodes.CREDENTIALS_NOT_FOUND


class IBMQAccountCredentialsInvalidFormat(IBMQAccountError):
    """Error raised when credentials format is invalid."""
    error_code = IBMQErrorCodes.INVALID_CREDENTIALS_FORMAT


class IBMQAccountCredentialsInvalidToken(IBMQAccountError):
    """Error raised for an invalid IBM Q Experience API token.."""
    error_code = IBMQErrorCodes.INVALID_TOKEN


class IBMQAccountCredentialsInvalidUrl(IBMQAccountError):
    """Error raised for an invalid IBM Q Experience API url.."""
    error_code = IBMQErrorCodes.INVALID_URL


class IBMQAccountMultipleCredentialsFound(IBMQAccountError):
    """Error raised when multiple credentials found."""
    error_code = IBMQErrorCodes.INVALID_CREDENTIALS_FORMAT


class IBMQProviderError(IBMQAccountError):
    """Errors related to provider handling."""
    error_code = IBMQErrorCodes.PROVIDER_MATCH_ERROR


class IBMQBackendError(IBMQError):
    """Base class for IBM Q Backend Errors."""
    error_code = IBMQErrorCodes.GENERIC_BACKEND_ERROR


class IBMQBackendApiError(IBMQBackendError):
    """Error that occurs unexpectedly when querying the API."""
    error_code = IBMQErrorCodes.GENERIC_API_ERROR


class IBMQBackendApiProtocolError(IBMQBackendError):
    """Error raised when unexpected API return values received."""
    error_code = IBMQErrorCodes.API_PROTOCOL_ERROR


class IBMQBackendValueError(IBMQBackendError, ValueError):
    """Value errors thrown within IBMQBackend."""
    error_code = IBMQErrorCodes.INVALID_STATE
