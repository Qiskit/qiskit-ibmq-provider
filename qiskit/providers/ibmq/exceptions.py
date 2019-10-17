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


class IBMQApiUrlError(IBMQAccountError):
    """Errors raised due to mixing API versions."""


class IBMQProviderError(IBMQAccountError):
    """Errors related to provider handling."""


class IBMQBackendError(IBMQError):
    """IBM Q Backend Errors."""
    pass


class IBMQBackendValueError(IBMQError, ValueError):
    """Value errors thrown within IBMQBackend."""
    pass


class IBMQJobManagerError(IBMQError):
    """Base class for errors raise by job manager."""
    pass


class IBMQJobManagerSubmitError(IBMQJobManagerError):
    """Errors raised when the job manager is unable to submit one or more jobs."""
    pass


class IBMQJobManagerInvalidStateError(IBMQJobManagerError):
    """Errors raised when an operation is invoked in an invalid state."""
    pass


class IBMQJobManagerTimeoutError(IBMQJobManagerError):
    """Errors raised when a job manager operation times out."""
    pass
