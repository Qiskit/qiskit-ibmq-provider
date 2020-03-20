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

"""Exceptions related to IBM Quantum Experience jobs."""

from qiskit.providers.exceptions import JobError, JobTimeoutError

from ..exceptions import IQXError


class IQXJobError(JobError, IQXError):
    """Base class for errors raised by the job modules."""
    pass


class IQXJobApiError(IQXJobError):
    """Errors that occur unexpectedly when querying the server."""
    pass


class IQXJobFailureError(IQXJobError):
    """Errors raised when a job failed."""
    pass


class IQXJobInvalidStateError(IQXJobError):
    """Errors raised when a job is not in a valid state for the operation."""
    pass


class IQXJobTimeoutError(JobTimeoutError, IQXJobError):
    """Errors raised when a job operation times out."""
    pass
