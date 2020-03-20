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


class IQXError(QiskitError):
    """Base class for errors raised by the provider modules."""
    pass


class IQXAccountError(IQXError):
    """Base class for errors raised by account management."""
    pass


class IQXAccountCredentialsNotFound(IQXAccountError):
    """Errors raised when credentials are not found."""
    pass


class IQXAccountCredentialsInvalidFormat(IQXAccountError):
    """Errors raised when the credentials format is invalid."""
    pass


class IQXAccountCredentialsInvalidToken(IQXAccountError):
    """Errors raised when an IBM Quantum Experience token is invalid."""
    pass


class IQXAccountCredentialsInvalidUrl(IQXAccountError):
    """Errors raised when an IBM Quantum Experience URL is invalid."""
    pass


class IQXAccountMultipleCredentialsFound(IQXAccountError):
    """Errors raised when multiple credentials are found."""
    pass


class IQXProviderError(IQXAccountError):
    """Errors related to provider handling."""
    pass


class IQXBackendError(IQXError):
    """Base class for errors raised by the backend modules."""
    pass


class IQXBackendApiError(IQXBackendError):
    """Errors that occur unexpectedly when querying the server."""
    pass


class IQXBackendApiProtocolError(IQXBackendApiError):
    """Errors raised when an unexpected value is received from the server."""
    pass


class IQXBackendValueError(IQXBackendError, ValueError):
    """Value errors raised by the backend modules."""
    pass
