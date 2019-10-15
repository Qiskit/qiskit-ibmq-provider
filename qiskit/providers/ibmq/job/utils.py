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

"""Utilities for working with IBM Q Jobs."""

from datetime import datetime, timezone
from typing import Dict, List, Tuple, Generator, Optional, Any
from contextlib import contextmanager

from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.job.exceptions import IBMQJobApiError

from ..apiconstants import ApiJobStatus
from ..api.exceptions import ApiError


API_TO_JOB_STATUS = {
    ApiJobStatus.CREATING: JobStatus.INITIALIZING,
    ApiJobStatus.CREATED: JobStatus.INITIALIZING,
    ApiJobStatus.VALIDATING: JobStatus.VALIDATING,
    ApiJobStatus.VALIDATED: JobStatus.QUEUED,
    ApiJobStatus.RUNNING: JobStatus.RUNNING,
    ApiJobStatus.COMPLETED: JobStatus.DONE,
    ApiJobStatus.CANCELLED: JobStatus.CANCELLED,
    ApiJobStatus.ERROR_CREATING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_VALIDATING_JOB: JobStatus.ERROR,
    ApiJobStatus.ERROR_RUNNING_JOB: JobStatus.ERROR
}


def current_utc_time() -> str:
    """Gets the current time in UTC format.

    Returns:
        current time in UTC format.
    """
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def is_job_queued(info_queue: Optional[Dict] = None) -> Tuple[bool, int]:
    """Checks whether a job has been queued or not.

    Args:
        info_queue: queue information from the API response.

    Returns:
        a pair indicating if the job is queued and in which
            position.
    """
    is_queued, position = False, 0
    if info_queue:
        if 'status' in info_queue:
            queue_status = info_queue['status']
            is_queued = queue_status == 'PENDING_IN_QUEUE'
        if 'position' in info_queue:
            position = info_queue['position']
    return is_queued, position


def build_error_report(results: List[Dict[str, Any]]) -> str:
    """Build an user-friendly error report for a failed job.

    Args:
        results: result section of the job response.

    Returns:
        the error report.
    """
    error_list = []
    for index, result in enumerate(results):
        if not result['success']:
            error_list.append('Experiment {}: {}'.format(index, result['status']))

    error_report = 'The following experiments failed:\n{}'.format('\n'.join(error_list))
    return error_report


def api_status_to_job_status(api_status: ApiJobStatus) -> JobStatus:
    """Return the corresponding job status for the input API job status.

    Args:
        api_status: API job status

    Returns:
        job status
    """
    return API_TO_JOB_STATUS[api_status]


@contextmanager
def api_to_job_error() -> Generator[None, None, None]:
    """Convert an ApiError to an IBMQJobApiError."""
    try:
        yield
    except ApiError as api_err:
        raise IBMQJobApiError(str(api_err))
