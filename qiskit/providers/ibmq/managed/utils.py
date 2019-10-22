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

"""Utility functions for IBMQJobManager."""

from typing import Callable, Any, List, Union
from functools import wraps
from collections import Counter

from qiskit.providers.jobstatus import JobStatus

from .managedjob import ManagedJob
from .exceptions import IBMQJobManagerInvalidStateError


def requires_submit(func: Callable) -> Callable:
    """Decorator used by ManagedJobSet to wait for all jobs to be submitted.

    Args:
        func (callable): function to be decorated.

    Returns:
        callable: the decorated function.

    Raises:
        IBMQJobManagerInvalidStateError: If jobs have not been submitted.
    """
    @wraps(func)
    def _wrapper(
            job_set: 'ManagedJobSet',   # type: ignore[name-defined]
            *args: Any,
            **kwargs: Any
    ) -> Any:
        """Wrapper function.

        Args:
            job_set: ManagedJobSet instance used to manage a set of jobs.
            args: arguments to be passed to the decorated function.
            kwargs: keyword arguments to be passed to the decorated function.

        Returns:
            return value of the decorated function.

        Raises:
            IBMQJobManagerInvalidStateError: If jobs have not been submitted.
        """
        if job_set._submit_collector is None:
            raise IBMQJobManagerInvalidStateError("Jobs need to be submitted first!")
        job_set._submit_collector.result()
        return func(job_set, *args, **kwargs)

    return _wrapper


def format_status_counts(statuses: List[Union[JobStatus, None]]) -> List[str]:
    """Format summary report on job statuses.

    Args:
        statuses: Statuses of the jobs.

    Returns:
        Formatted job status report.
    """
    counts = Counter(statuses)  # type: Counter
    report = [
        "       Total jobs: {}".format(len(statuses)),
        "  Successful jobs: {}".format(counts[JobStatus.DONE]),
        "      Failed jobs: {}".format(counts[JobStatus.ERROR]),
        "   Cancelled jobs: {}".format(counts[JobStatus.CANCELLED]),
        "     Running jobs: {}".format(counts[JobStatus.RUNNING]),
        "     Pending jobs: {}".format(counts[JobStatus.INITIALIZING] +
                                       counts[JobStatus.VALIDATING] +
                                       counts[JobStatus.QUEUED])
    ]

    return report


def format_job_details(
        statuses: List[Union[JobStatus, None]],
        managed_jobs: List[ManagedJob]
) -> List[str]:
    """Format detailed report for jobs.

    Args:
        statuses: Statuses of the jobs.
        managed_jobs: Jobs being managed.

    Returns:
        Formatted job details.
    """
    report = []
    for i, mjob in enumerate(managed_jobs):
        report.append("  experiments: {}-{}".format(mjob.start_index, mjob.end_index))
        report.append("    job index: {}".format(i))
        if not mjob.future.done():
            report.append("    status: {}".format(JobStatus.INITIALIZING.value))
            continue
        if mjob.submit_error is not None:
            report.append("    status: job submit failed: {}".format(
                str(mjob.submit_error)))
            continue

        job = mjob.job
        report.append("    job ID: {}".format(job.job_id()))
        report.append("    name: {}".format(job.name()))
        status_txt = statuses[i].value if statuses[i] else "Unknown"
        report.append("    status: {}".format(status_txt))

        if statuses[i] is JobStatus.QUEUED:
            report.append("    queue position: {}".format(job.queue_position()))
        elif statuses[i] is JobStatus.ERROR:
            report.append("    error_message:")
            msg_list = job.error_message().split('\n')
            for msg in msg_list:
                report.append(msg.rjust(len(msg)+6))

    return report
