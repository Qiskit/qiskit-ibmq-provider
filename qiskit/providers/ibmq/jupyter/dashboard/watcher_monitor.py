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

"""A module of widgets for job monitoring."""

import sys
import time
import threading

from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.job.ibmqjob import IBMQJob

from ...utils.converters import duration_difference


def _job_monitor(job: IBMQJob, status: JobStatus, watcher: 'IQXDashboard') -> None:
    """Monitor the status of an ``IBMQJob`` instance.

    Args:
        job: Job to monitor.
        status: Job status.
        watcher: Job watcher instance.
    """
    thread = threading.Thread(target=_job_checker, args=(job, status, watcher))
    thread.start()


def _job_checker(job: IBMQJob, status: JobStatus, watcher: 'IQXDashboard') -> None:
    """A simple job status checker.

    Args:
        job: The job to check.
        status: Job status.
        watcher: Job watcher instance.
    """
    prev_status_name = None
    prev_queue_pos = None
    interval = 2
    exception_count = 0
    prev_est_time = ''
    while status.name not in ['DONE', 'CANCELLED', 'ERROR']:
        time.sleep(interval)
        try:
            status = job.status()
            exception_count = 0

            if status.name == 'QUEUED':
                queue_pos = job.queue_position()
                if queue_pos != prev_queue_pos:
                    queue_info = job.queue_info()
                    if queue_info and queue_info.estimated_start_time:
                        est_time = duration_difference(queue_info.estimated_start_time)
                        prev_est_time = est_time
                    else:
                        est_time = prev_est_time

                    update_info = (job.job_id(), status.name+' ({})'.format(queue_pos),
                                   est_time, status.value)

                    watcher.update_single_job(update_info)
                    if queue_pos is not None:
                        interval = max(queue_pos, 2)
                    else:
                        interval = 2
                    prev_queue_pos = queue_pos

            elif status.name != prev_status_name:
                msg = status.name
                if msg == 'RUNNING':
                    job_mode = job.scheduling_mode()
                    if job_mode:
                        msg += ' [{}]'.format(job_mode[0].upper())

                update_info = (job.job_id(), msg, 0, status.value)

                watcher.update_single_job(update_info)
                interval = 2
                prev_status_name = status.name

        # pylint: disable=broad-except
        except Exception:
            exception_count += 1
            if exception_count == 5:
                update_info = (job.job_id(), 'NA', 0, "Could not query job.")
                watcher.update_single_job(update_info)
                sys.exit()
