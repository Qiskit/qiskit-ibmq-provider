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

from typing import Dict, List, Generator, Any, Callable, Optional, NamedTuple
from contextlib import contextmanager

from qiskit.providers.jobstatus import JobStatus

from ..api.exceptions import ApiError
from .exceptions import IBMQJobApiError
from .queueinfo import QueueInfo

JOB_STATUS_TO_INT = {
    JobStatus.INITIALIZING: 0,
    JobStatus.VALIDATING: 1,
    JobStatus.QUEUED: 2,
    JobStatus.RUNNING: 3,
    JobStatus.DONE: 4,
    JobStatus.CANCELLED: 4,
    JobStatus.ERROR: 4
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


def auto_retry(func: Callable, *args, **kwargs) -> Any:
    """Retry the function if encountered server error.

    Args:
        func: Function to be retried.
        *args: Function arguments.
        **kwargs: Function arguments. `max_retry` can be
            specified. The default is 3.

    Returns:
        function return value.
    """
    max_retry = kwargs.pop('max_retry', 3)
    while True:
        try:
            return func(*args, **kwargs)
        except IBMQJobApiError:
            max_retry -= 1
            if max_retry == 0:
                raise


class JobStatusQueueInfo(NamedTuple):
    """A named tuple of job status and queue info."""
    status: JobStatus
    queue_info: Optional[QueueInfo]


def last_job_stat_pos(jobs: List[JobStatusQueueInfo]) -> JobStatusQueueInfo:
    """Find the status and queue information of the job last to finish.

    Jobs are sorted by status, queue position, and estimated completion time.
    A status of "QUEUED", for example, is "later" than one of status "RUNNING".
    A higher queue position or estimated completion time is also considered
    "later". A queue position of ``None`` is assumed to be higher than any
    other positions, since the job is likely to be so new in the queue that
    its position is yet to be determined. The same thing applies to estimated
    completion time.

    Args:
        jobs: A list of jobs to assess.

    Returns:
        Status and queue information of the job last to finish.
    """

    def sort_3_keys(elem: JobStatusQueueInfo):
        """Sort by job status, queue position, and est completion time."""
        queue_info = elem.queue_info
        queue_pos = queue_info.position if queue_info else None
        est_comp = queue_info.estimated_complete_time if queue_info else None
        return JOB_STATUS_TO_INT[elem.status]*-1, queue_pos is None, queue_pos, est_comp is None, est_comp

    return sorted(jobs, key=sort_3_keys)[-1]
