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

from qiskit.exceptions import QiskitError


class IBMQError(QiskitError):
    """Base class for errors raised by the IBMQ provider module."""
    pass


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
    """IBM Q Backend Errors."""
    pass


class IBMQBackendApiError(IBMQBackendError):
    """Error that occurs unexpectedly when querying the API."""
    pass


class IBMQBackendApiProtocolError(IBMQBackendApiError):
    """Error raised when unexpected API return values received."""
    pass


class IBMQBackendValueError(IBMQBackendError, ValueError):
    """Value errors thrown within IBMQBackend."""
    pass
