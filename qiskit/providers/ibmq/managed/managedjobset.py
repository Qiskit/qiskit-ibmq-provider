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

"""A set of jobs being managed by the IBMQJobManager."""

from datetime import datetime
from typing import List, Optional, Union
from concurrent.futures import ThreadPoolExecutor
import warnings
import time
import logging

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.compiler import assemble
from qiskit.qobj import Qobj
from qiskit.result import Result
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.exceptions import JobError

from .managedjob import ManagedJob
from .utils import requires_submit, format_status_counts, format_job_details
from .exceptions import IBMQJobManagerInvalidStateError, IBMQJobManagerTimeoutError
from ..job import IBMQJob
from ..ibmqbackend import IBMQBackend

logger = logging.getLogger(__name__)


class ManagedJobSet:
    """A set of managed jobs."""

    def __init__(self, name: Optional[str] = None) -> None:
        """Creates a new ManagedJobSet instance."""
        self._managed_jobs = []  # type: List[ManagedJob]
        self._name = name or datetime.utcnow().isoformat()

        # Used for caching
        self._results = []  # type: Optional[List[Union[Result, None]]]
        self._error_msg = None  # type: Optional[str]

    def run(
            self,
            experiment_list: Union[List[List[QuantumCircuit]], List[List[Schedule]]],
            backend: IBMQBackend,
            executor: ThreadPoolExecutor,
            shots: int = 1024
    ) -> None:
        """Execute a list of circuits or pulse schedules on a backend.

        Args:
            experiment_list : Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            executor: The thread pool to use.
            shots: Number of repetitions of each experiment, for sampling. Default: 1024.

        Raises:
            IBMQJobManagerInvalidStateError: If the jobs were already submitted.
        """
        if self._managed_jobs:
            raise IBMQJobManagerInvalidStateError("Jobs were already submitted.")

        exp_index = 0
        for i, experiment in enumerate(experiment_list):
            qobj = assemble(experiment, backend=backend, shots=shots)
            job_name = "{}_{}".format(self._name, i)
            future = executor.submit(
                self._async_submit, qobj=qobj, job_name=job_name, backend=backend)
            self._managed_jobs.append(
                ManagedJob(experiment, start_index=exp_index, future=future))
            exp_index += len(experiment)

    def _async_submit(
            self,
            qobj: Qobj,
            job_name: str,
            backend: IBMQBackend,
    ) -> IBMQJob:
        """Run a Qobj asynchronously.

        Args:
            qobj: Qobj to run.
            job_name: Name of the job.
            backend: Backend to execute the experiments on.

        Returns:
            IBMQJob instance for the job.
        """
        return backend.run(qobj=qobj, job_name=job_name)

    def submit_results(self):
        """Collect job submit responses.

        Raises:
            IBMQJobManagerInvalidStateError: If jobs have not been submitted.
        """
        if not self._managed_jobs:
            raise IBMQJobManagerInvalidStateError("Jobs need to be submitted first!")

        if all(exps.future is None for exps in self._managed_jobs):
            # Submit results already collected
            return

        for managed in self._managed_jobs:
            managed.submit_result()

    @requires_submit
    def statuses(self) -> List[Union[JobStatus, None]]:
        """Return the status of each job.

        Returns:
            A list of job statuses. The entry is ``None`` if the job status
                cannot be retrieved due to server error.
        """
        statuses = []
        for i, mjob in enumerate(self._managed_jobs):
            if mjob.job is not None:
                try:
                    statuses.append(mjob.job.statuses())
                    continue
                except JobError as err:
                    warnings.warn(
                        "Unable to retrieve status for job {}, job ID={}, "
                        "for experiments {}-{}}: {}".format(
                            i, mjob.job.job_id(), mjob.start_index, mjob.end_index, err))
            statuses.append(None)

        return statuses

    @requires_submit
    def report(self, detailed: bool = True) -> str:
        """Return a report on current job statuses.

        Args:
            detailed: True if a detailed report is be returned. False
                if a summary report is to be returned.

        Returns:
            A report on job statuses.
        """
        statuses = self.statuses()
        report = ["Summary report:"]
        report.extend(format_status_counts(statuses))

        if detailed:
            report.append("\nDetail report:")
            report.extend(format_job_details(statuses, self._managed_jobs))

        return '\n'.join(report)

    @requires_submit
    def results(self, timeout: Optional[float] = None) -> List[Union[Result, None]]:
        """Return the results of the jobs.

        This call will block until all job results become available or
            the timeout is reached.

        Args:
           timeout: Number of seconds to wait for job results.

        Returns:
            A list of job results. The entry is ``None`` if the job result
                cannot be retrieved.

        Raises:
            IBMQJobManagerTimeoutError: if unable to retrieve all job results before the
                specified timeout.
        """
        if self._results:
            return self._results

        results = []
        start_time = time.time()
        original_timeout = timeout

        for i, mjob in enumerate(self._managed_jobs):
            result = None
            if mjob.job is not None:
                try:
                    # TODO Revise this when partial result is supported
                    result = mjob.job.result(timeout=timeout)
                except JobError as err:
                    warnings.warn(
                        "Unable to retrieve results for job {}, job ID={}, "
                        "for experiments {}-{}}: {}".format(
                            i, mjob.job.job_id(), mjob.start_index, mjob.end_index, err))

            results.append(result)
            if timeout:
                timeout = original_timeout - (time.time() - start_time)
                if timeout <= 0:
                    raise IBMQJobManagerTimeoutError(
                        "Timeout waiting for results for experiments {}-{}.".format(
                            mjob.start_index, self._managed_jobs[-1].end_index))

        self._results = results
        return self._results

    @requires_submit
    def error_messages(self) -> Optional[str]:
        """Provide details about job failures.

        Returns:
            An error report if one or more jobs failed or ``None`` otherwise.
        """
        if self._error_msg:
            return self._error_msg

        report = []
        for i, mjob in enumerate(self._managed_jobs):
            if mjob.job is None:
                continue
            if mjob.job.statuses() is not JobStatus.ERROR:
                continue
            report.append("Job {}, job ID={}, for experiments {}-{}:".format(
                i, mjob.job.job_id(), mjob.start_index, mjob.end_index))
            try:
                msg_list = mjob.job.error_message().split('\n')
            except JobError:
                msg_list = ["Unknown error."]

            for msg in msg_list:
                report.append(msg.rjust(len(msg)+2))

        if not report:
            return None
        return '\n'.join(report)

    @requires_submit
    def cancel(self) -> None:
        """Cancel all managed jobs."""
        for job in self.jobs():
            if job is not None:
                try:
                    job.cancel()
                except JobError as err:
                    logger.warning("Unable to cancel job {}: {}".format(job.job_id(), err))

    @requires_submit
    def jobs(self) -> List[Union[IBMQJob, None]]:
        """Return a list of submitted jobs.

        Returns:
            A list of IBMQJob instances that represents the submitted jobs. The
                entry is ``None`` if the job submit failed.
        """
        return [exps.job for exps in self._managed_jobs]

    @requires_submit
    def qobjs(self) -> List[Qobj]:
        """Return the Qobj for the jobs.

        Returns:
            A list of Qobj for the jobs.
        """
        return [mjob.job.qobj() for mjob in self._managed_jobs]

    def name(self) -> str:
        """Return the name of this set of jobs.

        Returns:
            Name of this set of jobs.
        """
        return self._name

    def managed_jobs(self) -> List[ManagedJob]:
        """Return a list of managed jobs.

        Returns:
            A list of managed jobs.
        """
        return self._managed_jobs


class RetrievedManagedJobSet(ManagedJobSet):
    """Managed job set from a previous manager instance."""

    def __init__(self, jobs, name: Optional[str] = None):
        """Creates a new RetrievedManagedJobSet instance."""
        super().__init__(name)

        for job in jobs:
            self._managed_jobs.append(ManagedJob([], None, None, job))

    def run(
            self,
            experiment_list: Union[List[List[QuantumCircuit]], List[List[Schedule]]],
            backend: IBMQBackend,
            executor: ThreadPoolExecutor,
            name_prefix: Optional[str] = None,
            shots: int = 1024
    ) -> None:
        raise IBMQJobManagerInvalidStateError("Jobs were already submitted.")

    def submit_results(self):
        """Collect job submit responses."""
        return
