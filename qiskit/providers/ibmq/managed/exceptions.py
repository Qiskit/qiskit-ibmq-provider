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

"""Exception for the job manager modules."""

from typing import Any, Optional

from ..exceptions import IBMQError
from ..errorcodes import IBMQErrorCodes


class IBMQJobManagerError(IBMQError):
    """Base class for errors raise by job manager."""

    def __init__(self, *message: Any) -> None:
        """Set the error message and code."""
        super().__init__(*message, error_code=IBMQ_MANAGED_ERROR_CODES[type(self)])


class IBMQJobManagerInvalidStateError(IBMQJobManagerError):
    """Errors raised when an operation is invoked in an invalid state."""
    pass


class IBMQJobManagerTimeoutError(IBMQJobManagerError):
    """Errors raised when a job manager operation times out."""
    pass


class IBMQJobManagerJobNotFound(IBMQJobManagerError):
    """Errors raised when a job cannot be found."""
    pass


class IBMQManagedResultDataNotAvailable(IBMQJobManagerError):
    """Errors raised when result data is not available."""
    pass


IBMQ_MANAGED_ERROR_CODES = {
    IBMQJobManagerError: IBMQErrorCodes.GENERIC_JOB_ERROR,
    IBMQJobManagerInvalidStateError: IBMQErrorCodes.INVALID_STATE,
    IBMQJobManagerTimeoutError: IBMQErrorCodes.REQUEST_TIMEOUT,
    IBMQJobManagerJobNotFound: IBMQErrorCodes.INVALID_STATE,
    IBMQManagedResultDataNotAvailable: IBMQErrorCodes.INVALID_STATE
}
