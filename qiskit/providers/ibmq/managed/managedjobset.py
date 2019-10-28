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
from typing import List, Optional, Union, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import time
import logging

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.compiler import assemble
from qiskit.qobj import Qobj
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.exceptions import JobTimeoutError

from .managedjob import ManagedJob
from .managedresults import ManagedResults
from .utils import requires_submit, format_status_counts, format_job_details
from .exceptions import (IBMQJobManagerInvalidStateError, IBMQJobManagerTimeoutError,
                         IBMQJobManagerJobNotFound)
from ..job import IBMQJob
from ..ibmqbackend import IBMQBackend

logger = logging.getLogger(__name__)


class ManagedJobSet:
    """A set of managed jobs."""

    def __init__(self, name: Optional[str] = None) -> None:
        """Creates a new ManagedJobSet instance."""
        self._managed_jobs = []  # type: List[ManagedJob]
        self._name = name or datetime.utcnow().isoformat()
        self._backend = None  # type: Optional[IBMQBackend]

        # Used for caching
        self._managed_results = None  # type: Optional[ManagedResults]
        self._error_msg = None  # type: Optional[str]

    def run(
            self,
            experiment_list: Union[List[List[QuantumCircuit]], List[List[Schedule]]],
            backend: IBMQBackend,
            executor: ThreadPoolExecutor,
            **assemble_config: Any
    ) -> None:
        """Execute a list of circuits or pulse schedules on a backend.

        Args:
            experiment_list : Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            executor: The thread pool to use.
            assemble_config: Additional arguments used to configure the Qobj
                assembly. Refer to the ``qiskit.compiler.assemble`` documentation
                for details on these arguments.

        Raises:
            IBMQJobManagerInvalidStateError: If the jobs were already submitted.
        """
        if self._managed_jobs:
            raise IBMQJobManagerInvalidStateError("Jobs were already submitted.")

        self._backend = backend
        exp_index = 0
        for i, experiments in enumerate(experiment_list):
            qobj = assemble(experiments, backend=backend, **assemble_config)
            job_name = "{}_{}_".format(self._name, i)
            self._managed_jobs.append(
                ManagedJob(experiments, start_index=exp_index,
                           qobj=qobj, job_name=job_name, backend=backend,
                           executor=executor)
            )
            exp_index += len(experiments)

    def statuses(self) -> List[Union[JobStatus, None]]:
        """Return the status of each job.

        Returns:
            A list of job statuses. The entry is ``None`` if the job status
                cannot be retrieved due to server error.
        """
        return [mjob.status() for mjob in self._managed_jobs]

    def report(self, detailed: bool = True) -> str:
        """Return a report on current job statuses.

        Args:
            detailed: True if a detailed report is be returned. False
                if a summary report is to be returned.

        Returns:
            A report on job statuses.
        """
        statuses = self.statuses()
        report = ["Job set {}:".format(self.name()),
                  "Summary report:"]
        report.extend(format_status_counts(statuses))

        if detailed:
            report.append("\nDetail report:")
            report.extend(format_job_details(statuses, self._managed_jobs))

        return '\n'.join(report)

    @requires_submit
    def results(
            self,
            timeout: Optional[float] = None,
            partial: bool = False
    ) -> ManagedResults:
        """Return the results of the jobs.

        This call will block until all job results become available or
            the timeout is reached.

        Note:
            Some IBMQ job results can be read only once. A second attempt to
            query the API for the job will fail, as the job is "consumed".

            The first call to this method in a ``ManagedJobSet`` instance will query
            the API and consume any available job results. Subsequent calls to
            that instance's method will also return the results, since they are
            cached. However, attempting to retrieve the results again in
            another instance or session might fail due to the job results
            having been consumed.

            When `partial=True`, this method will attempt to retrieve partial
            results of failed jobs if possible. In this case, precaution should
            be taken when accessing individual experiments, as doing so might
            cause an exception. The ``success`` attribute of a
            ``ManagedResults`` instance can be used to verify whether it contains
            partial results.

            For example:
                If one of the experiments failed, trying to get the counts of
                the unsuccessful experiment would raise an exception since
                there are no counts to return for it:
                i.e.
                    try:
                        counts = managed_results.get_counts("failed_experiment")
                    except QiskitError:
                        print("Experiment failed!")

        Args:
           timeout: Number of seconds to wait for job results.
           partial: If true, attempt to retrieve partial job results.

        Returns:
            A ``ManagedResults`` instance that can be used to retrieve results
                for individual experiments.

        Raises:
            IBMQJobManagerTimeoutError: if unable to retrieve all job results before the
                specified timeout.
        """
        if self._managed_results is not None:
            return self._managed_results

        start_time = time.time()
        original_timeout = timeout
        success = True

        # TODO We can potentially make this multithreaded
        for mjob in self._managed_jobs:
            try:
                result = mjob.result(timeout=timeout, partial=partial)
                if result is None or not result.success:
                    success = False
            except JobTimeoutError:
                raise IBMQJobManagerTimeoutError(
                    "Timeout waiting for results for experiments {}-{}.".format(
                        mjob.start_index, self._managed_jobs[-1].end_index))

            if timeout:
                timeout = original_timeout - (time.time() - start_time)
                if timeout <= 0:
                    raise IBMQJobManagerTimeoutError(
                        "Timeout waiting for results for experiments {}-{}.".format(
                            mjob.start_index, self._managed_jobs[-1].end_index))

        self._managed_results = ManagedResults(self, self._backend.name(), success)

        return self._managed_results

    @requires_submit
    def error_messages(self) -> Optional[str]:
        """Provide details about job failures.

        This call will block until all job results become available.

        Returns:
            An error report if one or more jobs failed or ``None`` otherwise.
        """
        if self._error_msg:
            return self._error_msg

        report = []  # type: List[str]
        for i, mjob in enumerate(self._managed_jobs):
            msg_list = mjob.error_message()
            if not msg_list:
                continue
            report.append("Experiments {}-{}, job index={}, job ID={}:".format(
                mjob.start_index, mjob.end_index, i, mjob.job.job_id()))
            for msg in msg_list.split('\n'):
                report.append(msg.rjust(len(msg)+2))

        if not report:
            return None
        return '\n'.join(report)

    @requires_submit
    def cancel(self) -> None:
        """Cancel all managed jobs."""
        for mjob in self._managed_jobs:
            mjob.cancel()

    @requires_submit
    def jobs(self) -> List[Union[IBMQJob, None]]:
        """Return a list of submitted jobs.

        Returns:
            A list of IBMQJob instances that represents the submitted jobs. The
                entry is ``None`` if the job submit failed.
        """
        return [mjob.job for mjob in self._managed_jobs]

    @requires_submit
    def job(
            self,
            experiment: Union[str, QuantumCircuit, Schedule, int]
    ) -> Tuple[Optional[IBMQJob], int]:
        """Returns the job used to submit the experiment and the experiment index.

        For example, if ``IBMQJobManager`` is used to submit 1000 experiments,
            and ``IBMQJobManager`` divides them into 2 jobs: job 1
            has experiments 0-499, and job 2 has experiments 500-999. In this
            case ``job_set.job(501)`` will return (job2, 1).

        Args:
            experiment: the index of the experiment. Several types are
                accepted for convenience::
                * str: the name of the experiment.
                * QuantumCircuit: the name of the circuit instance will be used.
                * Schedule: the name of the schedule instance will be used.
                * int: the position of the experiment.

        Returns:
            A tuple of the job used to submit the experiment, or ``None`` if
                the job submit failed, and the experiment index.

        Raises:
            IBMQJobManagerJobNotFound: If the job for the experiment could not
                be found.
        """
        if isinstance(experiment, int):
            for mjob in self._managed_jobs:
                if mjob.end_index >= experiment >= mjob.start_index:
                    return mjob.job, experiment - mjob.start_index
        else:
            if isinstance(experiment, (QuantumCircuit, Schedule)):
                experiment = experiment.name
            for mjob in self._managed_jobs:
                for i, exp in enumerate(mjob.experiments):
                    if exp.name == experiment:
                        return mjob.job, i

        raise IBMQJobManagerJobNotFound("Unable to find the job for experiment {}".format(
            experiment))

    @requires_submit
    def qobjs(self) -> List[Qobj]:
        """Return the Qobj for the jobs.

        Returns:
            A list of Qobj for the jobs. The entry is ``None`` if the Qobj
                could not be retrieved.
        """
        return [mjob.qobj() for mjob in self._managed_jobs]

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
