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

from typing import Any, Optional

from qiskit.exceptions import QiskitError

from .errorcodes import IBMQErrorCodes


class IBMQError(QiskitError):
    """Base class for errors raised by the IBMQ provider module."""

    def __init__(self, *message: Any, error_code: Optional[IBMQErrorCodes] = None) -> None:
        """Set the error message and code."""
        super().__init__(*message)
        exception_type = type(self)
        if error_code:
            self.error_code = error_code
        elif exception_type in IBMQ_ERROR_CODES:
            self.error_code = IBMQ_ERROR_CODES[exception_type]
        else:
            self.error_code = IBMQErrorCodes.GENERIC_ERROR

    def __str__(self) -> str:
        """Format the error string with the error code."""
        return '{}. Error code: {}'.format(self.message, self.error_code.value)


class IBMQAccountError(IBMQError):
    """Base class for errors raised by account management."""
    pass


class IBMQAccountCredentialsNotFound(IBMQAccountError):
    """Error raised when credentials not found."""
    pass


class IBMQAccountCredentialsInvalidFormat(IBMQAccountError):
    """Error raised when credentials format is invalid."""
    pass


class IBMQAccountCredentialsInvalidToken(IBMQAccountError):
    """Error raised for an invalid IBM Q Experience API token.."""
    pass


class IBMQAccountCredentialsInvalidUrl(IBMQAccountError):
    """Error raised for an invalid IBM Q Experience API url.."""
    pass


class IBMQAccountMultipleCredentialsFound(IBMQAccountError):
    """Error raised when multiple credentials found."""
    pass


class IBMQProviderError(IBMQAccountError):
    """Errors related to provider handling."""
    pass


class IBMQBackendError(IBMQError):
    """Base class for IBM Q Backend Errors."""
    pass


class IBMQBackendPreQobjError(IBMQBackendError):
    """Error raised when the job is in a format that is no longer supported."""
    pass


class IBMQBackendApiError(IBMQBackendError):
    """Error that occurs unexpectedly when querying the API."""
    pass


class IBMQBackendApiProtocolError(IBMQBackendError):
    """Error raised when unexpected API return values received."""
    pass


class IBMQBackendValueError(IBMQError, ValueError):
    """Value errors thrown within IBMQBackend."""
    pass


IBMQ_ERROR_CODES = {
    IBMQAccountError: IBMQErrorCodes.GENERIC_CREDENTIALS_ERROR,
    IBMQAccountCredentialsNotFound: IBMQErrorCodes.CREDENTIALS_NOT_FOUND,
    IBMQAccountCredentialsInvalidFormat: IBMQErrorCodes.INVALID_CREDENTIALS_FORMAT,
    IBMQAccountCredentialsInvalidToken: IBMQErrorCodes.INVALID_TOKEN,
    IBMQAccountCredentialsInvalidUrl: IBMQErrorCodes.INVALID_URL,
    IBMQAccountMultipleCredentialsFound: IBMQErrorCodes.MULTIPLE_CREDENTIALS_FOUND,
    IBMQBackendError: IBMQErrorCodes.GENERIC_BACKEND_ERROR,
    IBMQBackendPreQobjError: IBMQErrorCodes.JOB_IN_PRE_QOBJ_FORMAT,
    IBMQBackendApiError: IBMQErrorCodes.GENERIC_API_ERROR,
    IBMQBackendApiProtocolError: IBMQErrorCodes.API_PROTOCOL_ERROR,
    IBMQBackendValueError: IBMQErrorCodes.INVALID_STATE
}
