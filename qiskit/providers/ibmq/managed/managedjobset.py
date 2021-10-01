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

"""A set of jobs being managed by the :class:`IBMQJobManager`."""

from datetime import datetime
from typing import List, Optional, Union, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import time
import logging
import uuid
import threading
import warnings

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.qobj import QasmQobj, PulseQobj
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.apiconstants import ApiJobShareLevel
from qiskit.providers.ibmq.accountprovider import AccountProvider

from .managedjob import ManagedJob
from .managedresults import ManagedResults
from .utils import (requires_submit, format_status_counts, format_job_details,
                    JOB_SET_NAME_FORMATTER, JOB_SET_NAME_RE)
from .exceptions import (IBMQJobManagerInvalidStateError, IBMQJobManagerTimeoutError,
                         IBMQJobManagerJobNotFound, IBMQJobManagerUnknownJobSet)
from ..job import IBMQJob
from ..job.exceptions import IBMQJobTimeoutError, IBMQJobApiError
from ..ibmqbackend import IBMQBackend

logger = logging.getLogger(__name__)


class ManagedJobSet:
    """A set of managed jobs.

    An instance of this class is returned when you submit experiments using
    :meth:`IBMQJobManager.run()`.
    It provides methods that allow you to interact
    with the jobs as a single entity. For example, you can retrieve the results
    for all of the jobs using :meth:`results()` and cancel all jobs using
    :meth:`cancel()`.
    """

    _id_prefix = "ibmq_jobset_"
    _id_suffix = "_"

    def __init__(
            self,
            name: Optional[str] = None,
            short_id: Optional[str] = None
    ) -> None:
        """ManagedJobSet constructor.

        Args:
            name: Name for this set of jobs. If not specified, the current
                date and time is used.
            short_id: Short ID for this set of jobs.
        """
        self._managed_jobs = []  # type: List[ManagedJob]
        self._name = name or datetime.utcnow().isoformat()
        self._backend = None  # type: Optional[IBMQBackend]
        self._id = short_id or uuid.uuid4().hex + '-' + str(time.time()).replace('.', '')
        self._id_long = self._id_prefix + self._id + self._id_suffix
        self._tags = []  # type: List[str]
        self._job_submit_lock = threading.Lock()  # Used to synchronize job submit.

        # Used for caching
        self._managed_results = None  # type: Optional[ManagedResults]
        self._error_msg = None  # type: Optional[str]

    def run(
            self,
            experiment_list: Union[List[List[QuantumCircuit]], List[List[Schedule]]],
            backend: IBMQBackend,
            executor: ThreadPoolExecutor,
            job_share_level: Optional[ApiJobShareLevel] = None,
            job_tags: Optional[List[str]] = None,
            **run_config: Any
    ) -> None:
        """Execute a list of circuits or pulse schedules on a backend.

        Args:
            experiment_list : Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            executor: The thread pool used to submit jobs asynchronously.
            job_share_level: Job share level.
            job_tags: Tags to be assigned to the job.
            run_config: Additional arguments used to configure the Qobj
                assembly. Refer to the :func:`qiskit.compiler.assemble` documentation
                for details on these arguments.

        Raises:
            IBMQJobManagerInvalidStateError: If the jobs were already submitted.
        """
        if job_share_level:
            warnings.warn("The `job_share_level` keyword is no longer supported "
                          "and will be removed in a future release.",
                          Warning, stacklevel=2)

        if self._managed_jobs:
            raise IBMQJobManagerInvalidStateError(
                'The jobs for this managed job set have already been submitted.')

        self._backend = backend
        if job_tags:
            self._tags = job_tags.copy()

        exp_index = 0
        total_jobs = len(experiment_list)
        for i, experiments in enumerate(experiment_list):
            job_name = JOB_SET_NAME_FORMATTER.format(self._name, i)
            mjob = ManagedJob(experiments_count=len(experiments), start_index=exp_index)
            logger.debug("Submitting job %s/%s for job set %s", i+1, total_jobs, self._name)
            mjob.submit(experiments, job_name=job_name, backend=backend,
                        executor=executor, job_tags=self._tags+[self._id_long],
                        submit_lock=self._job_submit_lock, **run_config)
            logger.debug("Job %s submitted", i+1)
            self._managed_jobs.append(mjob)
            exp_index += len(experiments)

    def retrieve_jobs(self, provider: AccountProvider, refresh: bool = False) -> None:
        """Retrieve previously submitted jobs in this set.

        Args:
            provider: Provider used for this job set.
            refresh: If ``True``, re-query the server for the job set.
                Otherwise return the cached value.

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
            job_page = provider.backend.jobs(    # type: ignore[attr-defined]
                skip=len(jobs), limit=page_limit, job_tags=[self._id_long])
            jobs += job_page
            if len(job_page) < page_limit:
                break

        if not jobs:
            raise IBMQJobManagerUnknownJobSet(
                '{} is not a known job set within the provider {}.'.format(
                    self.job_set_id(), provider))

        # Extract common information from the first job.
        first_job = jobs[0]
        job_set_name, _ = self._parse_job_name(first_job)
        self._name = job_set_name
        self._backend = first_job.backend()
        self._tags = first_job.tags()
        self._tags.remove(self._id_long)

        jobs_dict = {}
        for job in jobs:
            # Verify the job is proper.
            job_set_name, job_index = self._parse_job_name(job)
            if job_set_name != self._name or job.backend().name() != self._backend.name():
                raise IBMQJobManagerInvalidStateError(
                    'Job {} is tagged for the job set {} but does not appear '
                    'to belong to the set.'.format(job.job_id(), self.job_set_id()))
            jobs_dict[job_index] = job

        sorted_indexes = sorted(jobs_dict)
        # Verify we got all jobs.
        if sorted_indexes != list(range(len(sorted_indexes))):
            raise IBMQJobManagerInvalidStateError(
                'Unable to retrieve all jobs for job set {}.'.format(self.job_set_id()))

        self._managed_jobs = []
        experiment_index = 0
        for job_index in sorted_indexes:
            job = jobs_dict[job_index]
            mjob = ManagedJob(
                start_index=experiment_index,
                experiments_count=len(job.circuits()),
                job=job
            )
            self._managed_jobs.append(mjob)
            experiment_index = mjob.end_index + 1

    def statuses(self) -> List[Union[JobStatus, None]]:
        """Return the status of each job in this set.

        Returns:
            A list of job statuses. An entry in the list is ``None`` if the
            job status could not be retrieved due to a server error.
        """
        return [mjob.status() for mjob in self._managed_jobs]

    def report(self, detailed: bool = True) -> str:
        """Return a report on current job statuses.

        Args:
            detailed: If ``True``, return a detailed report. Otherwise return a
                summary report.

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
            partial: bool = False,
            refresh: bool = False
    ) -> ManagedResults:
        """Return the results of the jobs.

        This call will block until all job results become available or
        the timeout is reached.

        Note:
            Some IBM Quantum Experience job results can only be read once. A
            second attempt to query the server for the same job will fail,
            since the job has already been "consumed".

            The first call to this method in a ``ManagedJobSet`` instance will
            query the server and consume any available job results. Subsequent
            calls to that instance's method will also return the results, since
            they are cached. However, attempting to retrieve the results again in
            another instance or session might fail due to the job results
            having been consumed.

        Note:
            When `partial=True`, this method will attempt to retrieve partial
            results of failed jobs. In this case, precaution should
            be taken when accessing individual experiments, as doing so might
            cause an exception. The ``success`` attribute of the returned
            :class:`ManagedResults`
            instance can be used to verify whether it contains
            partial results.

            For example, if one of the experiments failed, trying to get the counts
            of the unsuccessful experiment would raise an exception since there
            are no counts to return::

                try:
                    counts = managed_results.get_counts("failed_experiment")
                except QiskitError:
                    print("Experiment failed!")

        Args:
           timeout: Number of seconds to wait for job results.
           partial: If ``True``, attempt to retrieve partial job results.
           refresh: If ``True``, re-query the server for the result. Otherwise
                return the cached value.

        Returns:
            A :class:`ManagedResults`
            instance that can be used to retrieve results
            for individual experiments.

        Raises:
            IBMQJobManagerTimeoutError: if unable to retrieve all job results before the
                specified timeout.
        """
        if self._managed_results is not None and not refresh:
            return self._managed_results

        start_time = time.time()
        original_timeout = timeout
        success = True

        # TODO We can potentially make this multithreaded
        for mjob in self._managed_jobs:
            try:
                result = mjob.result(timeout=timeout, partial=partial, refresh=refresh)
                if result is None or not result.success:
                    success = False
            except IBMQJobTimeoutError as ex:
                raise IBMQJobManagerTimeoutError(
                    'Timeout while waiting for the results for experiments {}-{}.'.format(
                        mjob.start_index, self._managed_jobs[-1].end_index)) from ex

            if timeout:
                timeout = original_timeout - (time.time() - start_time)
                if timeout <= 0:
                    raise IBMQJobManagerTimeoutError(
                        'Timeout while waiting for the results for experiments {}-{}.'.format(
                            mjob.start_index, self._managed_jobs[-1].end_index))

        self._managed_results = ManagedResults(self, self._backend.name(), success)

        return self._managed_results

    @requires_submit
    def error_messages(self) -> Optional[str]:
        """Provide details about job failures.

        This call will block until all jobs finish.

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
        """Cancel all jobs in this job set."""
        for mjob in self._managed_jobs:
            mjob.cancel()

    @requires_submit
    def jobs(self) -> List[Union[IBMQJob, None]]:
        """Return jobs in this job set.

        Returns:
            A list of :class:`~qiskit.providers.ibmq.job.IBMQJob`
            instances that represents the submitted jobs.
            An entry in the list is ``None`` if the job failed to be submitted.
        """
        return [mjob.job for mjob in self._managed_jobs]

    @requires_submit
    def job(
            self,
            experiment: Union[str, QuantumCircuit, Schedule, int]
    ) -> Tuple[Optional[IBMQJob], int]:
        """Retrieve the job used to submit the specified experiment and its index.

        For example, if :class:`IBMQJobManager` is used to submit 1000 experiments,
        and :class:`IBMQJobManager` divides them into 2 jobs: job 1
        has experiments 0-499, and job 2 has experiments 500-999. In this
        case ``job_set.job(501)`` will return ``(job2, 1)``.

        Args:
            experiment: Retrieve the job used to submit this experiment. Several
                types are accepted for convenience:

                    * str: The name of the experiment.
                    * QuantumCircuit: The name of the circuit instance will be used.
                    * Schedule: The name of the schedule instance will be used.
                    * int: The position of the experiment.

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
                for i, exp in enumerate(job.circuits()):
                    if hasattr(exp, 'name') and exp.name == experiment:
                        return job, i

        raise IBMQJobManagerJobNotFound(
            'Unable to find the job for experiment {}.'.format(experiment))

    @requires_submit
    def qobjs(self) -> List[Union[QasmQobj, PulseQobj]]:
        """Return the Qobjs for the jobs in this set.

        Returns:
            A list of Qobjs for the jobs. An entry in the list is ``None``
            if the Qobj could not be retrieved.
        """
        return [mjob.qobj() for mjob in self._managed_jobs]

    def name(self) -> str:
        """Return the name of this job set.

        Returns:
            Name of this job set.
        """
        return self._name

    @requires_submit
    def update_name(self, name: str) -> str:
        """Update the name of this job set.

        Args:
            name: The new `name` for this job set.

        Returns:
            The new name associated with this job set.
        """
        for job in self.jobs():
            if job:
                _, job_index = self._parse_job_name(job)
                try:
                    # Use the index found in the job name to update the name in order
                    # to preserve the job set order.
                    _ = job.update_name(JOB_SET_NAME_FORMATTER.format(name, job_index))
                except IBMQJobApiError as ex:
                    # Log a warning with the job that failed to update.
                    logger.warning('There was an error updating the name for job %s, '
                                   'belonging to job set %s: %s',
                                   job.job_id(), self.job_set_id(), str(ex))

        # Cache the updated job set name.
        self._name = name

        return self._name

    def job_set_id(self) -> str:
        """Return the ID of this job set.

        Returns:
            ID of this job set.
        """
        # Return only the short version of the ID to reduce the possibility the
        # full ID is used for another job.
        return self._id

    def managed_jobs(self) -> List[ManagedJob]:
        """Return the managed jobs in this set.

        Returns:
            A list of managed jobs.
        """
        return self._managed_jobs

    def tags(self) -> List[str]:
        """Return the tags assigned to this job set.

        Returns:
            Tags assigned to this job set.
        """
        return self._tags

    def update_tags(
            self,
            replacement_tags: List[str] = None,
            additional_tags: List[str] = None,
            removal_tags: List[str] = None
    ) -> List[str]:
        """Update the tags assigned to this job set.

        When multiple parameters are specified, the parameters are processed in the
        following order:

            1. replacement_tags
            2. additional_tags
            3. removal_tags

        For example, if 'new_tag' is specified for both `additional_tags` and `removal_tags`,
        then it is added and subsequently removed from the tags list, making it a "do nothing"
        operation.

        Note:
            * Some tags, such as those starting with ``ibmq_jobset``, are used
              internally by `ibmq-provider` and therefore cannot be modified.
            * When removing tags, if the job does not have a specified tag, it
              will be ignored.

        Args:
            replacement_tags: The tags that should replace the current tags
                associated with this job set.
            additional_tags: The new tags that should be added to the current tags
                associated with this job set.
            removal_tags: The tags that should be removed from the current tags
                associated with this job set.

        Returns:
            The new tags associated with this job set.

        Raises:
            IBMQJobManagerInvalidStateError: If none of the input parameters are specified.
        """
        if (replacement_tags is None) and (additional_tags is None) and (removal_tags is None):
            raise IBMQJobManagerInvalidStateError(
                'The tags cannot be updated since none of the parameters are specified.')

        updated_tags = []  # type: List[str]
        for job in self.jobs():
            if job:
                try:
                    updated_tags = job.update_tags(replacement_tags=replacement_tags,
                                                   additional_tags=additional_tags,
                                                   removal_tags=removal_tags)
                except IBMQJobApiError as ex:
                    # Log a warning with the job that failed to update.
                    logger.warning('There was an error updating the tags for job %s, '
                                   'belonging to job set %s: %s',
                                   job.job_id(), self.job_set_id(), str(ex))

        # Cache the updated job set tags and remove the long id.
        self._tags = updated_tags
        self._tags.remove(self._id_long)

        return self._tags

    def _parse_job_name(self, job: IBMQJob) -> Tuple[str, int]:
        """Parse the name of a job from the job set.

        Args:
            job: A job in the job set.

        Returns:
            A tuple containing the job set name and the index of the job's
            placement in the job set: (<job_set_name>, <job_index_in_set>).

        Raises:
            IBMQJobManagerInvalidStateError: If the job does not have a proper
                job name.
        """
        matched = JOB_SET_NAME_RE.match(job.name())
        if not matched:
            raise IBMQJobManagerInvalidStateError(
                'Job {} is tagged for the job set {} but does not '
                'have a proper job name.'.format(job.job_id(), self.job_set_id()))

        return matched.group(1), int(matched.group(2))
