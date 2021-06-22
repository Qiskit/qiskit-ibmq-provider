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

from abc import abstractmethod
from typing import Tuple
import sys
import time
import threading

from qiskit.providers.job import JobV1 as Job
from qiskit.providers.ibmq.runtime import RuntimeJob
from qiskit.providers.ibmq.job import IBMQJob


from .utils import get_job_type
from ...utils.converters import duration_difference


# pylint: disable=too-few-public-methods
class JobMonitor:
    """Monitors a job for updates to display to the dashboard"""
    def __init__(self, job: Job, watcher: 'IQXDashboard') -> None:
        """Creates a JobMonitor.

        Args:
            job: the job
            watcher: the dashboard
        """
        self.job = job
        self._job_type = get_job_type(job)
        self._watcher = watcher
        self._prev_status_name = None
        self._interval = 0.5
        self._exception_count = 0

    def _update(self, info: Tuple) -> None:
        """Updates the watcher with the provided info"""
        self._watcher.update_single_job(self._job_type, info)

    @abstractmethod
    def _set_job_queued(self) -> None:
        """Perform updates particular to the QUEUED phase"""
        pass

    def start(self):
        """Start the monitor"""
        status = self.job.status()
        while status.name not in ['DONE', 'CANCELLED', 'ERROR']:
            time.sleep(self._interval)
            try:
                status = self.job.status()
                self._exception_count = 0
                if status.name == 'QUEUED':
                    self._set_job_queued()
                elif status.name != self._prev_status_name:

                    msg = status.name
                    info = (self.job.job_id(), msg, 0, status.value)

                    # Update the job on the dashboard
                    self._update(info)

                    self._interval = 2
                    self._prev_status_name = status.name

            # pylint: disable=broad-except
            except Exception:
                self._exception_count += 1
                if self._exception_count == 5:
                    info = (self.job.job_id(), 'NA', 0, "Could not query job.")
                    # Update the job on the dashboard
                    self._update(info)
                    sys.exit()


class RuntimeJobMonitor(JobMonitor):
    """Monitors a runtime job for updates to display to dashboard"""

    def __init__(self, job: RuntimeJob, watcher: 'IQXDashboard') -> None:
        """Initialize a runtime job

        Args:
            job: the job
            watcher: the dashboard
        """
        super().__init__(job, watcher)

    def _set_job_queued(self) -> None:
        """Perform queued updates"""
        info = (self.job.job_id(), self.job.status().name)
        # Update the job on the dashboard
        self._update(info)


class CircuitJobMonitor(JobMonitor):
    """Monitors a circuit job for updates to display to dashboard"""

    def __init__(self, job: IBMQJob, watcher: 'IQXDashboard') -> None:
        """Initialize a circuit job

        Args:
            job: the job
            watcher: the dashboard
        """
        super().__init__(job, watcher)
        self._prev_queue_pos = None
        self._prev_est_time = ''

    def _set_job_queued(self) -> None:
        """Perform queued updates"""
        status = self.job.status()
        info = (self.job.job_id(), status.name)
        # Update the job on the dashboard
        queue_pos = self.job.queue_position()
        if queue_pos != self._prev_queue_pos:
            queue_info = self.job.queue_info()
            # If we have access to the time info, prepare it
            if queue_info and queue_info.estimated_start_time:
                est_time = duration_difference(queue_info.estimated_start_time)
                self._prev_est_time = est_time
            else:
                est_time = self._prev_est_time

            info = (self.job.job_id(), status.name+' ({})'.format(queue_pos),
                    est_time, status.value)

            self._update(info)
            if queue_pos is not None:
                self._interval = max(queue_pos, 2)
            else:
                self._interval = 2
            self._prev_queue_pos = queue_pos
        self._update(info)


def _create_monitor(job: Job, watcher: 'IQXDashboard') -> JobMonitor:
    """Create a monitor for the job.

    Args:
        job: the job
        watcher: the watcher to recieve updates

    Returns:
        JobMonitor: the monitor
    """
    monitor = RuntimeJobMonitor(job, watcher) if isinstance(job, RuntimeJob) \
        else CircuitJobMonitor(job, watcher)
    monitor.start()
    return monitor


def job_monitor(job: Job, watcher: 'IQXDashboard') -> None:
    """Monitor the status of an ``IBMQJob`` instance.

    Args:
        job: Job to monitor.
        watcher: Job watcher instance.
    """
    thread = threading.Thread(target=_create_monitor, args=(job, watcher))
    thread.start()
