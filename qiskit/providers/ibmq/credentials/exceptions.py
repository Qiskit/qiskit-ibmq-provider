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

from typing import Any

from ..exceptions import IBMQError, IBMQErrorCodes


class CredentialsError(IBMQError):
    """Base class for errors raised during credential management."""

    def __init__(self, *message: Any) -> None:
        """Set the error message and code."""
        super().__init__(*message, error_code=IBMQ_CREDENTIALS_ERROR_CODES[type(self)])


class InvalidCredentialsFormatError(CredentialsError):
    """Error raised when the credentials are in an invalid format."""
    pass


class CredentialsNotFoundError(CredentialsError):
    """Error raised when the credentials are not found."""
    pass


IBMQ_CREDENTIALS_ERROR_CODES = {
    CredentialsError: IBMQErrorCodes.GENERIC_CREDENTIALS_ERROR,
    InvalidCredentialsFormatError: IBMQErrorCodes.INVALID_CREDENTIALS_FORMAT,
    CredentialsNotFoundError: IBMQErrorCodes.CREDENTIALS_NOT_FOUND
}
