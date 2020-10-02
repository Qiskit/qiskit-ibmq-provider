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

"""Exceptions related to the IBM Quantum Experience provider."""

from qiskit.exceptions import QiskitError


class IBMQError(QiskitError):
    """Base class for errors raised by the provider modules."""
    pass


class IBMQAccountError(IBMQError):
    """Base class for errors raised by account management."""
    pass


class IBMQAccountValueError(IBMQError):
    """Value errors raised by account management."""


class IBMQAccountCredentialsNotFound(IBMQAccountError):
    """Errors raised when credentials are not found."""
    pass


class IBMQAccountCredentialsInvalidFormat(IBMQAccountError):
    """Errors raised when the credentials format is invalid."""
    pass


class IBMQAccountCredentialsInvalidToken(IBMQAccountError):
    """Errors raised when an IBM Quantum Experience token is invalid."""
    pass


class IBMQAccountCredentialsInvalidUrl(IBMQAccountError):
    """Errors raised when an IBM Quantum Experience URL is invalid."""
    pass


class IBMQAccountMultipleCredentialsFound(IBMQAccountError):
    """Errors raised when multiple credentials are found."""
    pass


class IBMQProviderError(IBMQAccountError):
    """Errors related to provider handling."""
    pass


class IBMQBackendError(IBMQError):
    """Base class for errors raised by the backend modules."""
    pass


class IBMQBackendApiError(IBMQBackendError):
    """Errors that occur unexpectedly when querying the server."""
    pass


class IBMQBackendApiProtocolError(IBMQBackendApiError):
    """Errors raised when an unexpected value is received from the server."""
    pass


class IBMQBackendValueError(IBMQBackendError, ValueError):
    """Value errors raised by the backend modules."""
    pass


class IBMQBackendJobLimitError(IBMQBackendError):
    """Errors raised when job limit is reached."""
    pass


class IBMQInputValueError(IBMQError):
    """Error raised due to invalid input value."""
    pass


class IBMQNotAuthorizedError(IBMQError):
    """Error raised when a service is invoked from an unauthorized account."""
