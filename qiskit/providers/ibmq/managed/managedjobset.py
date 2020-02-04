# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
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
import uuid
import re

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.compiler import assemble
from qiskit.qobj import Qobj
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.apiconstants import ApiJobShareLevel
from qiskit.providers.ibmq.accountprovider import AccountProvider

from .managedjob import ManagedJob
from .managedresults import ManagedResults
from .utils import requires_submit, format_status_counts, format_job_details
from .exceptions import (IBMQJobManagerInvalidStateError, IBMQJobManagerTimeoutError,
                         IBMQJobManagerJobNotFound, IBMQJobManagerUnknownJobSet)
from ..job import IBMQJob
from ..job.exceptions import IBMQJobTimeoutError
from ..ibmqbackend import IBMQBackend

logger = logging.getLogger(__name__)


class ManagedJobSet:
    """A set of managed jobs."""

    _id_prefix = "ibmq_jobset_"
    _id_suffix = "_"

    def __init__(
            self,
            name: Optional[str] = None,
            short_id: Optional[str] = None
    ) -> None:
        """Creates a new ManagedJobSet instance.

        Args:
            name: Name for this set of jobs. Default: current datetime.
            short_id: Short ID for this set of jobs. Default: None.
        """
        self._managed_jobs = []  # type: List[ManagedJob]
        self._name = name or datetime.utcnow().isoformat()
        self._backend = None  # type: Optional[IBMQBackend]
        self._id = short_id or uuid.uuid4().hex + '-' + str(time.time()).replace('.', '')
        self._id_long = self._id_prefix + self._id + self._id_suffix
        self._tags = []  # type: List[str]

        # Used for caching
        self._managed_results = None  # type: Optional[ManagedResults]
        self._error_msg = None  # type: Optional[str]

    def run(
            self,
            experiment_list: Union[List[List[QuantumCircuit]], List[List[Schedule]]],
            backend: IBMQBackend,
            executor: ThreadPoolExecutor,
            job_share_level: ApiJobShareLevel,
            job_tags: Optional[List[str]] = None,
            **assemble_config: Any
    ) -> None:
        """Execute a list of circuits or pulse schedules on a backend.

        Args:
            experiment_list : Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            executor: The thread pool to use.
            job_share_level: Job share level.
            job_tags: tags to be assigned to the job.
            assemble_config: Additional arguments used to configure the Qobj
                assembly. Refer to the ``qiskit.compiler.assemble`` documentation
                for details on these arguments.

        Raises:
            IBMQJobManagerInvalidStateError: If the jobs were already submitted.
        """
        if self._managed_jobs:
            raise IBMQJobManagerInvalidStateError("Jobs were already submitted.")

        self._backend = backend
        if job_tags:
            self._tags = job_tags.copy()
        exp_index = 0
        for i, experiments in enumerate(experiment_list):
            qobj = assemble(experiments, backend=backend, **assemble_config)
            job_name = "{}_{}_".format(self._name, i)
            mjob = ManagedJob(experiments_count=len(experiments), start_index=exp_index)
            mjob.submit(qobj=qobj, job_name=job_name, backend=backend,
                        executor=executor, job_share_level=job_share_level,
                        job_tags=self._tags+[self._id_long])
            self._managed_jobs.append(mjob)
            exp_index += len(experiments)

    def retrieve_jobs(self, provider: AccountProvider, refresh: bool = False) -> None:
        """Retrieve previously submitted jobs for this set.

        Args:
            provider: Provider used for this job set.
            refresh: If True, re-query the API for the job set.
                Otherwise return the cached value. Default: False.

        Raises:
            IBMQJobManagerUnknownJobSet: If the job set cannot be found.
            IBMQJobManagerInvalidStateError: If jobs for this job set are
                found but have unexpected attributes.
        """
        if not refresh and self._managed_jobs:
            return

        # IBMQBackend jobs() method does not have a way to pass in unlimited
        # number of jobs to retrieve. 1000 should be a sufficiently large
        # enough number.
        jobs = []  # type: List[IBMQJob]
        page_limit = 1000
        while True:
            job_page = provider.backends.jobs(    # type: ignore[attr-defined]
                skip=len(jobs), limit=page_limit, job_tags=[self._id_long])
            jobs += job_page
            if len(job_page) < page_limit:
                break

        if not jobs:
            raise IBMQJobManagerUnknownJobSet(
                "{} is not a known job set within the provider {}.".format(
                    self.job_set_id(), provider))

        # Extract common information from the first job.
        first_job = jobs[0]
        pattern = re.compile(r'(.*)_([0-9])+_$')
        matched = pattern.match(first_job.name())
        if not matched:
            raise IBMQJobManagerInvalidStateError(
                "Job {} is tagged for the job set {} but does not have a proper job name.".format(
                    first_job.job_id(), self.job_set_id()))
        self._name = matched.group(1)
        self._backend = first_job.backend()
        self._tags = first_job.tags()
        self._tags.remove(self._id_long)

        jobs_dict = {}
        for job in jobs:
            # Verify the job is proper.
            matched = pattern.match(job.name()) if job.name() else None
            if not matched or matched.group(1) != self._name or \
                    job.backend().name() != self._backend.name():
                raise IBMQJobManagerInvalidStateError(
                    "Job {} is tagged for the job set {} but does not appear "
                    "to belong to the set".format(job.job_id(), self.job_set_id()))
            jobs_dict[int(matched.group(2))] = job

        sorted_indexes = sorted(jobs_dict)
        # Verify we got all jobs.
        if sorted_indexes != list(range(len(sorted_indexes))):
            raise IBMQJobManagerInvalidStateError(
                "Unable to retrieve all jobs for job set {}".format(self.job_set_id()))

        self._managed_jobs = []
        experiment_index = 0
        for job_index in sorted_indexes:
            job = jobs_dict[job_index]
            mjob = ManagedJob(
                start_index=experiment_index,
                experiments_count=len(job.qobj().experiments),
                job=job
            )
            self._managed_jobs.append(mjob)
            experiment_index = mjob.end_index + 1

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
        report = ["Job set name: {}".format(self.name()),
                  "          ID: {}".format(self.job_set_id()),
                  "        tags: {}".format(self.tags()),
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
            except IBMQJobTimeoutError:
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
            for job in self.jobs():
                for i, exp in enumerate(job.qobj().experiments):
                    if hasattr(exp.header, 'name') and exp.header.name == experiment:
                        return job, i

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

    def job_set_id(self) -> str:
        """Return the ID of this set of jobs.

        Returns:
            ID of this set of jobs.
        """
        # Return only the short version of the ID to reduce the possibility the
        # full ID is used for another job.
        return self._id

    def managed_jobs(self) -> List[ManagedJob]:
        """Return a list of managed jobs.

        Returns:
            A list of managed jobs.
        """
        return self._managed_jobs

    def tags(self) -> List[str]:
        """Return the tags assigned to this set of jobs.

        Returns:
            Tags assigned to this set of jobs.
        """
        return self._tags
