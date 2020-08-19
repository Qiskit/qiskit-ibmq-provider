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

"""Utilities for working with IBM Quantum Experience jobs."""

from typing import Dict, List, Generator, Any, Union
from contextlib import contextmanager

from qiskit.providers.jobstatus import JobStatus

from ..apiconstants import ApiJobStatus
from ..api.exceptions import ApiError
from .exceptions import IBMQJobApiError


API_TO_JOB_STATUS = {
    ApiJobStatus.CREATING: JobStatus.INITIALIZING,
    ApiJobStatus.CREATED: JobStatus.INITIALIZING,
    ApiJobStatus.TRANSPILING: JobStatus.INITIALIZING,
    ApiJobStatus.TRANSPILED: JobStatus.INITIALIZING,
    ApiJobStatus.VALIDATING: JobStatus.VALIDATING,
    ApiJobStatus.VALIDATED: JobStatus.VALIDATING,
    ApiJobStatus.RUNNING: JobStatus.RUNNING,
    ApiJobStatus.PENDING_IN_QUEUE: JobStatus.QUEUED,
    ApiJobStatus.QUEUED: JobStatus.QUEUED,
    ApiJobStatus.COMPLETED: JobStatus.DONE,
    ApiJobStatus.CANCELLED: JobStatus.CANCELLED,
    ApiJobStatus.ERROR_CREATING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_VALIDATING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_RUNNING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_TRANSPILING_JOB: JobStatus.ERROR
}


def build_error_report(results: List[Dict[str, Any]]) -> str:
    """Build a user-friendly error report for a failed job.

    Args:
        results: Result section of the job response.

    Returns:
        The error report.
    """
    error_list = []
    for index, result in enumerate(results):
        if not result['success']:
            error_list.append('Experiment {}: {}'.format(index, result['status']))

    error_report = 'The following experiments failed:\n{}'.format('\n'.join(error_list))
    return error_report


def api_status_to_job_status(api_status: Union[str, ApiJobStatus]) -> JobStatus:
    """Return the corresponding job status for the input server job status.

    Args:
        api_status: Server job status.

    Returns:
        Job status.
    """
    if isinstance(api_status, str):
        api_status = ApiJobStatus(api_status)
    return API_TO_JOB_STATUS[api_status]


def get_cancel_status(cancel_response: Dict[str, Any]) -> bool:
    """Return whether the cancel response represents a successful job cancel.

    Args:
        cancel_response: The response received from the server after
            cancelling a job.

    Returns:
        Whether the job cancel is successful.
    """
    return 'error' not in cancel_response and cancel_response.get('cancelled', False)


@contextmanager
def api_to_job_error() -> Generator[None, None, None]:
    """Convert an ``ApiError`` to an ``IBMQJobApiError``."""
    try:
        yield
    except ApiError as api_err:
        raise IBMQJobApiError(str(api_err)) from api_err
