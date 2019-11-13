# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Exceptions related to IBMQJob."""

from qiskit.providers.exceptions import JobError, JobTimeoutError

from ..errorcodes import IBMQErrorCodes
from ..exceptions import IBMQError


class IBMQJobError(JobError, IBMQError):
    """Base class for job errors raised by the IBMQ provider module."""
    error_code = IBMQErrorCodes.GENERIC_JOB_ERROR


class IBMQJobApiError(IBMQJobError):
    """Error that occurs unexpectedly when querying the API."""
    error_code = IBMQErrorCodes.GENERIC_API_ERROR


class IBMQApiProtocolError(IBMQJobError):
    """Error raised when unexpected API return values received."""
    error_code = IBMQErrorCodes.API_PROTOCOL_ERROR


class IBMQJobFailureError(IBMQJobError):
    """Error that occurs because the job failed."""
    error_code = IBMQErrorCodes.JOB_FINISHED_IN_ERROR


class IBMQJobInvalidStateError(IBMQJobError):
    """Error that occurs because a job is not in a state for the operation."""
    error_code = IBMQErrorCodes.INVALID_STATE


class IBMQJobTimeoutError(JobTimeoutError, IBMQJobError):
    """Error raised when a job operation times out."""
    error_code = IBMQErrorCodes.REQUEST_TIMEOUT
