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

"""Exception for the ``Credentials`` module."""

from ..exceptions import IBMQError


class CredentialsError(IBMQError):
    """Base class for errors raised during credential management."""
    pass


class InvalidCredentialsFormatError(CredentialsError):
    """Errors raised when the credentials are in an invalid format."""
    pass


class CredentialsNotFoundError(CredentialsError):
    """Errors raised when the credentials are not found."""
    pass


class HubGroupProjectError(IBMQError):
    """Base class for errors raised by the hubgroupproject module."""
    pass


class HubGroupProjectInvalidStateError(HubGroupProjectError):
    """Errors raised when a HubGroupProject is in an invalid state for an operation."""
    pass
