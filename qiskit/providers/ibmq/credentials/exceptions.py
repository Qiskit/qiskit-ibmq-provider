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

"""Exception for the Credentials module."""

from ..exceptions import IBMQError, IBMQErrorCodes


class CredentialsError(IBMQError):
    """Base class for errors raised during credential management."""
    error_code = IBMQErrorCodes.GENERIC_CREDENTIALS_ERROR


class InvalidCredentialsFormatError(CredentialsError):
    """Error raised when the credentials are in an invalid format."""
    error_code = IBMQErrorCodes.INVALID_CREDENTIALS_FORMAT


class CredentialsNotFoundError(CredentialsError):
    """Error raised when the credentials are not found."""
    error_code = IBMQErrorCodes.CREDENTIALS_NOT_FOUND
