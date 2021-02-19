# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Quantum Experience composite job."""

import re
import logging
from typing import Dict, Optional, Tuple, Any, List, Callable, Union, Set
import warnings
import uuid
from datetime import datetime
from concurrent import futures
import queue
from collections import defaultdict, OrderedDict
import threading
import copy
from functools import wraps
import time
import traceback

from qiskit.compiler import assemble
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import QasmQobj, PulseQobj
from qiskit.result import Result
from qiskit.providers.ibmq import ibmqbackend  # pylint: disable=unused-import
from qiskit.assembler.disassemble import disassemble
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.result.models import ExperimentResult

from ..apiconstants import API_JOB_FINAL_STATES
from ..api.clients import AccountClient
from ..utils.utils import validate_job_tags, api_status_to_job_status
from .exceptions import (IBMQJobApiError, IBMQJobFailureError, IBMQJobTimeoutError,
                         IBMQJobInvalidStateError)
from .queueinfo import QueueInfo
from .utils import auto_retry, JOB_STATUS_TO_INT, JobStatusQueueInfo, last_job_stat_pos
from .ibmqjob import IBMQJob
from .ibmq_circuit_job import IBMQCircuitJob
from ..exceptions import IBMQBackendJobLimitError

logger = logging.getLogger(__name__)


def _requires_submit(func):  # type: ignore
    """Decorator used by ``IBMQCompositeJob`` to wait for all jobs to be submitted."""

    @wraps(func)
    def _wrapper(self, *args, **kwargs):  # type: ignore
        futures.wait(self._job_submit_futures)
        self._move_jobs_from_queue()
        return func(self, *args, **kwargs)

    return _wrapper


class IBMQCompositeJob(IBMQJob):
    """Representation of a set of jobs that execute on an IBM Quantum Experience backend.

    An ``IBMQCompositeJob`` instance is returned when you call
    :meth:`IBMQBackend.run()<qiskit.providers.ibmq.ibmqbackend.IBMQBackend.run()>`
    to submit a list of circuits whose length exceeds the maximum allowed by
    the backend or by the ``max_circuits_per_job`` parameter.

    This ``IBMQCompositeJob`` instance manages all the sub-jobs for you and can
    be used like a traditional job instance. For example, you can continue to
    use methods like :meth:`status()` and :meth:`result()` to get the job
    status and result, respectively.

    You can also retrieve a previously executed ``IBMQCompositeJob`` using the
    :meth:`~qiskit.providers.ibmq.IBMQBackend.retrieve_job` and
    :meth:`~qiskit.providers.ibmq.IBMQBackend.jobs` methods, like you would with
    traditional jobs.

    ``IBMQCompositeJob`` also allows you to re-run failed jobs, using the
    :meth:`rerun-failed()` method. This method will re-submit all failed or
    cancelled sub-jobs. Any circuits that failed to be submitted (e.g. due to
    server error) will only be re-submitted if the circuits are known. That is,
    if this ``IBMQCompositeJob`` was returned by
    :meth:`qiskit.providers.ibmq.IBMQBackend.run` and not retrieved from the server.

    Some of the methods in this class are blocking, which means control may
    not be returned immediately. :meth:`result()` is an example
    of a blocking method, and control will return only after all sub-jobs finish.

    ``IBMQCompositeJob`` uses job tags to identify sub-jobs. It is therefore
    important to preserve these tags. All tags used internally by ``IBMQCompositeJob``
    start with ``ibmq_composite_job_``.
    """

    _tag_prefix = "ibmq_composite_job_"
    _id_prefix = _tag_prefix + "id_"
    _id_suffix = "_"
    _index_prefix = _tag_prefix + "indexes:"
    _index_tag = _index_prefix + "{job_index}:{total}:{start_index}:{end_index}"
    _index_pattern = re.compile(rf"{_index_prefix}(?P<job_index>\d+):(?P<total>\d+):"
                                r"(?P<start_index>\d+):(?P<end_index>\d+)")

    _executor = futures.ThreadPoolExecutor()
    """Threads used for asynchronous processing."""

    def __init__(
            self,
            backend: 'ibmqbackend.IBMQBackend',
            api_client: AccountClient,
            job_id: Optional[str] = None,
            creation_date: Optional[datetime] = None,
            jobs: Optional[List[IBMQCircuitJob]] = None,
            circuits_list: Optional[List[Union[List[QuantumCircuit], List[Schedule]]]] = None,
            run_config: Optional[Dict] = None,
            name: Optional[str] = None,
            share_level: Optional[str] = None,
            tags: Optional[List[str]] = None,
            experiment_id: Optional[str] = None,
            client_version: Optional[Dict] = None
    ) -> None:
        """IBMQCompositeJob constructor.

        Args:
            backend: The backend instance used to run this job.
            api_client: Object for connecting to the server.
            job_id: Job ID.
            creation_date: Job creation date.
            jobs: A list of sub-jobs.
            circuits_list: Circuits for this job.
            run_config: Runtime configuration for this job.
            name: Job name.
            share_level: Level the job can be shared with.
            tags: Job tags.
            experiment_id: ID of the experiment this job is part of.
            client_version: Client used for the job.
        """
        if jobs is None and circuits_list is None:
            raise IBMQJobInvalidStateError('"jobs" and "circuits_list" cannot both be None.')

        self._job_id = job_id or self._id_prefix + uuid.uuid4().hex + self._id_suffix
        tags = tags or []
        filtered_tags = [tag for tag in tags if not tag.startswith(self._tag_prefix)]
        super().__init__(backend=backend, api_client=api_client, job_id=self._job_id,
                         name=name, share_level=share_level, tags=filtered_tags,
                         experiment_id=experiment_id)
        self._client_version = client_version
        self._status = JobStatus.INITIALIZING
        self._creation_date = creation_date

        # Properties used for job submit.
        # self._jobs = jobs or []
        self._jobs = {}
        self._jobs_queue = queue.Queue()
        self._job_submit_futures = []
        self._job_submit_error_queue = queue.Queue()
        self._job_submit_errors = []
        self._job_submit_events = []

        # Properties used for caching.
        self._user_cancelled = False
        self._job_error_msg = None  # type: Optional[str]
        self._properties = None
        self._queue_info = None
        self._qobj = None
        self._circuit_indexes = []  # type: List[Tuple[int, int]]
        self._result = None
        self._circuits = None

        # Properties used for wait_for_final_state callback.
        self._callback_lock = threading.Lock()
        self._user_callback = None
        self._user_wait_value = None
        self._last_reported_stat = (None, None)  # type: Tuple[Optional[JobStatus], Optional[int]]
        self._last_reported_time = 0
        self._job_statuses = {}

        if circuits_list is not None:
            self._circuits = [circ for sublist in circuits_list for circ in sublist]
            self._submit_circuits(circuits_list, run_config)
        else:
            # Validate the jobs.
            for job in jobs:
                print(f">>>>>>> IBMQCompositeJob.__init__: sub job tags: {job.tags()}, id={job.job_id()}")
                job_idx, start, end = \
                    self._find_circuit_indexes(job, ['job_index', 'start_index', 'end_index'])
                self._circuit_indexes.append((start, end))
                self._jobs[job_idx] = job
            self._circuit_indexes.sort()
            missing = set(range(self._find_circuit_indexes(jobs[0], ['total'])[0])) - \
                      set(self._jobs.keys())
            if len(missing) > 0:
                raise IBMQJobInvalidStateError(
                    f"Composite job {self.job_id()} is missing jobs at indexes {missing}.")

    @classmethod
    def from_jobs(
            cls,
            job_id: str,
            jobs: List[IBMQCircuitJob],
            api_client: AccountClient
    ) -> 'IBMQCompositeJob':
        """Return an instance of this class.

        The input job ID is used to query for sub-job information from the server.

        Args:
            job_id: Job ID.
            jobs: A list of subjobs that belong to this composite job.
            api_client: Client to use to communicate with the server.

        Returns:
            An instance of this class.
        """
        ref_job = jobs[0]
        return cls(backend=ref_job.backend(),
                   api_client=api_client,
                   job_id=job_id,
                   creation_date=ref_job.creation_date(),
                   jobs=jobs,
                   circuits_list=None,
                   run_config=None,
                   name=ref_job.name(),
                   share_level=ref_job.share_level(),
                   tags=ref_job.tags(),
                   experiment_id=ref_job.experiment_id,
                   client_version=ref_job.client_version)

    def _submit_circuits(
            self,
            circuit_lists: List[Union[List[QuantumCircuit], List[Schedule]]],
            run_config: Dict
    ) -> None:
        """Assemble and submit circuits.

        Args:
            circuit_lists: List of circuits to submit.
            run_config: Configuration used for assembling.
        """
        # Assemble all circuits first before submitting them with threads to
        # avoid conflicts with terra assembler.
        exp_index = 0
        qobjs = []
        logger.debug("Assembling all circuits.")
        for idx, circs in enumerate(circuit_lists):
            print(f">>>>>>> IBMQCompositeJob._submit_circuits: assembling circuits len {len(circs)}")
            qobjs.append((assemble(circs, backend=self.backend(), **run_config),
                          exp_index,  # start index
                          exp_index+len(circs)-1))  # end index
            exp_index += len(circs)
            self._job_submit_events.append(threading.Event())
        self._job_submit_events[0].set()

        for idx, item in enumerate(qobjs):
            qobj, start_index, end_index = item
            if self._qobj is None:
                self._qobj = copy.deepcopy(qobj)
            else:
                self._qobj.experiments.extend(qobj.experiments)
            self._circuit_indexes.append((start_index, end_index))
            self._job_submit_futures.append(
                self._executor.submit(self._async_submit, qobj=qobj, start_index=start_index,
                                      end_index=end_index, job_index=idx,
                                      total=len(circuit_lists)))

    def _async_submit(
            self,
            qobj: Union[QasmQobj, PulseQobj],
            start_index: int,
            end_index: int,
            job_index: int,
            total: int
    ) -> None:
        """Submit a Qobj asynchronously.

        Args:
            qobj: Qobj to run.
            start_index: Starting index of the circuits in the Qobj.
            end_index: Ending index of the circuits in the Qobj.
            job_index: Job index.
            total: Total number of jobs.
        """
        print(f">>>>>> IBMQCompositeJob. _async_submit: submitting qobj expr len {len(qobj.experiments)}")
        tags = self._tags.copy()
        tags.append(self._index_tag.format(
            job_index=job_index, total=total, start_index=start_index, end_index=end_index))
        tags.append(self.job_id())
        job = None
        logger.debug(f"Submitting job for circuits {start_index}-{end_index}.")
        print(f">>>>>>>> async submit waiting for event {self._job_submit_events[job_index]}")
        self._job_submit_events[job_index].wait()
        try:
            while job is None:
                if self._user_cancelled:
                    return  # Abandon submit if user cancelled.
                try:
                    print(f">>>>>> IBMQCompositeJob. _async_submit: submitting job {job_index}, tags={tags}")
                    job = auto_retry(self.backend()._submit_job,
                                     qobj=qobj, job_name=self._name,
                                     job_share_level=self._share_level,
                                     job_tags=tags, experiment_id=self._experiment_id)
                except IBMQBackendJobLimitError:
                    print(f">>>>>>> IBMQCompositeJob caught job limit error")
                    final_states = [state.value for state in API_JOB_FINAL_STATES]
                    oldest_running = self.backend().jobs(
                        limit=1, descending=False, ignore_composite_jobs=True,
                        db_filter={"status": {"nin": final_states}})
                    print(f">>>>>> oldest_running is {oldest_running}")
                    if oldest_running:
                        oldest_running = oldest_running[0]
                        print(f">>>>>> issue warning about job limit")
                        logger.warning("Job limit reached, waiting for job %s to finish "
                                       "before submitting the next one.",
                                       oldest_running.job_id())
                        try:
                            # Set a timeout in case the job is stuck.
                            print(f">>>>>> subjob {job_index } waiting for oldest running")
                            oldest_running.wait_for_final_state(timeout=300)
                        except Exception as err:  # pylint: disable=broad-except
                            # Don't kill the submit if unable to wait for old job.
                            logger.debug("An error occurred while waiting for "
                                         "job %s to finish: %s", oldest_running.job_id(), err)
                except Exception as err:  # pylint: disable=broad-except
                    self._job_submit_error_queue.put(
                        {'start_index': start_index,
                         'end_index': end_index,
                         'job_index': job_index,
                         'error': err})
                    logger.debug(f"An error occurred submitting sub-job {job_index}: " +
                                 traceback.format_exc())
                    raise

            if self._user_cancelled:
                job.cancel()
            self._jobs_queue.put_nowait((job_index, job))
            print(f">>>>> subjob {job_index } put in the queue")
            logger.debug(f"Job {job.job_id()} for circuits {start_index}-{end_index} submitted.")
        finally:
            try:
                # Wake up the next submit.
                next(event for event in self._job_submit_events if not event.is_set()).set()
            except StopIteration:
                pass

    @_requires_submit
    def properties(self) -> Optional[Union[List[BackendProperties], BackendProperties]]:
        """Return the backend properties for this job.

        Note:
            This method blocks until all sub-jobs are submitted.

        Returns:
            The backend properties used for this job, or ``None`` if
            properties are not available. A list of backend properties is
            returned if the sub-jobs used different properties.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        if self._properties is None:
            self._properties = []
            properties_ts = []
            for job in self._jobs.values():
                props = job.properties()
                if props.last_update_date not in properties_ts:
                    self._properties.append(props)
                    properties_ts.append(props.last_update_date)

        if not self._properties:
            return None
        if len(self._properties) == 1:
            return self._properties[0]
        return self._properties

    def result(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            partial: bool = False,
            refresh: bool = False
    ) -> Result:
        """Return the result of the job.

        Note:
            This method blocks until all sub-jobs finish.

        Note:
            Some IBM Quantum Experience job results can only be read once. A
            second attempt to query the server for the same job will fail,
            since the job has already been "consumed".

            The first call to this method in an ``IBMQCompositeJob`` instance will
            query the server and consume any available job results. Subsequent
            calls to that instance's ``result()`` will also return the results, since
            they are cached. However, attempting to retrieve the results again in
            another instance or session might fail due to the job results
            having been consumed.

        Note:
            When `partial=True`, this method will attempt to retrieve partial
            results of failed jobs. In this case, precaution should
            be taken when accessing individual experiments, as doing so might
            cause an exception. The ``success`` attribute of the returned
            :class:`~qiskit.result.Result` instance can be used to verify
            whether it contains partial results.

            For example, if one of the circuits in the job failed, trying to
            get the counts of the unsuccessful circuit would raise an exception
            since there are no counts to return::

                try:
                    counts = result.get_counts("failed_circuit")
                except QiskitError:
                    print("Circuit execution failed!")

        If the job failed, you can use :meth:`error_message()` to get more information.

        Args:
            timeout: Number of seconds to wait for job.
            wait: Time in seconds between queries.
            partial: If ``True``, return partial results if possible.
            refresh: If ``True``, re-query the server for the result. Otherwise
                return the cached value.

        Returns:
            Job result.

        Raises:
            IBMQJobInvalidStateError: If the job was cancelled.
            IBMQJobFailureError: If the job failed.
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        # pylint: disable=arguments-differ
        self.wait_for_final_state(wait=wait, timeout=timeout)
        if self._status == JobStatus.DONE or partial:
            self._result = self._gather_results(refresh=refresh)
            if self._result is not None:
                return self._result

        if self._status is JobStatus.CANCELLED:
            raise IBMQJobInvalidStateError('Unable to retrieve result for job {}. '
                                           'Job was cancelled.'.format(self.job_id()))
        print(f">>>>>> self._status={self._status}")
        error_message = self.error_message()
        if '\n' in error_message:
            error_message = ". Use the error_message() method to get more details."
        else:
            error_message = ": " + error_message
        raise IBMQJobFailureError(
            'Unable to retrieve result for job {}. Job has failed{}'.format(
                self.job_id(), error_message))

    def cancel(self) -> bool:
        """Attempt to cancel the job.

        Note:
            Depending on the state the job is in, it might be impossible to
            cancel the job.

        Returns:
            ``True`` if the job is cancelled, else ``False``.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        self._user_cancelled = True
        # Wake up all pending job submits.
        for event in self._job_submit_events:
            event.set()

        all_cancelled = []
        self._move_jobs_from_queue()
        for job in self._jobs.values():
            try:
                all_cancelled.append(job.cancel())
            except IBMQJobApiError as err:
                if 'Error code: 3209' not in str(err):
                    raise

        return all(all_cancelled)

    @_requires_submit
    def update_name(self, name: str) -> str:
        """Update the name associated with this job.

        Note:
            This method blocks until all sub-jobs are submitted.

        Args:
            name: The new `name` for this job.

        Returns:
            The new name associated with this job.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server or updating the job name.
            IBMQJobInvalidStateError: If the input job name is not a string.
        """
        if not isinstance(name, str):
            raise IBMQJobInvalidStateError(
                '"{}" of type "{}" is not a valid job name. '
                'The job name needs to be a string.'.format(name, type(name)))

        self._name = name
        for job in self._jobs.values():
            auto_retry(job.update_name, name)

        return self._name

    @_requires_submit
    def update_tags(
            self,
            replacement_tags: Optional[List[str]] = None,
            additional_tags: Optional[List[str]] = None,
            removal_tags: Optional[List[str]] = None
    ) -> List[str]:
        """Update the tags associated with this job.

        When multiple parameters are specified, the parameters are processed in the
        following order:

            1. replacement_tags
            2. additional_tags
            3. removal_tags

        For example, if 'new_tag' is specified for both `additional_tags` and `removal_tags`,
        then it is added and subsequently removed from the tags list, making it a "do nothing"
        operation.

        Note:
            * Some tags, such as those starting with ``ibmq_composite_job_``, are used
              internally by `ibmq-provider` and therefore cannot be modified.
            * When removing tags, if the job does not have a specified tag, it
              will be ignored.

        Note:
            This method blocks until all sub-jobs are submitted.

        Args:
            replacement_tags: The tags that should replace the current tags
                associated with this job.
            additional_tags: The new tags that should be added to the current tags
                associated with this job.
            removal_tags: The tags that should be removed from the current tags
                associated with this job.

        Returns:
            The new tags associated with this job.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server or updating the job tags.
            IBMQJobInvalidStateError: If none of the input parameters are specified or
                if any of the input parameters are invalid.
        """
        if (replacement_tags is None) and (additional_tags is None) and (removal_tags is None):
            raise IBMQJobInvalidStateError(
                'The tags cannot be updated since none of the parameters are specified.')

        # Get the list of tags to update.
        new_tags = self._get_tags_to_update(replacement_tags=replacement_tags,
                                            additional_tags=additional_tags,
                                            removal_tags=removal_tags)
        for job in self._jobs.values():
            tags_to_update = new_tags.union(
                {tag for tag in job.tags() if tag.startswith(self._tag_prefix)})
            auto_retry(job.update_tags, list(tags_to_update))
        self._tags = list(new_tags)
        return self._tags

    def _get_tags_to_update(self,
                            replacement_tags: Optional[List[str]],
                            additional_tags: Optional[List[str]],
                            removal_tags: Optional[List[str]]) -> Set[str]:
        """Create the list of tags to update for this job.

        Args:
            replacement_tags: The tags that should replace the current tags
                associated with this job.
            additional_tags: The new tags that should be added to the current tags
                associated with this job.
            removal_tags: The tags that should be removed from the current tags
                associated with this job.

        Returns:
            The new tags to associate with this job.

        Raises:
            IBMQJobInvalidStateError: If any of the input parameters are invalid.
        """
        tags_to_update = set(self._tags or [])  # Get the current job tags.
        if isinstance(replacement_tags, list):  # `replacement_tags` could be an empty list.
            # Replace the current tags and re-add those associated with a job set.
            validate_job_tags(replacement_tags, IBMQJobInvalidStateError)
            tags_to_update = set(replacement_tags)
            print(f">>>>>>> IBMQCompisitejob._get_tags_to_update cur tag {self._tags}")
            # tags_to_update.update(
            #     filter(lambda old_tag: old_tag.startswith(self._tag_prefix), self._tags))
        if additional_tags:
            # Add the specified tags to the tags to update.
            validate_job_tags(additional_tags, IBMQJobInvalidStateError)
            tags_to_update.update(additional_tags)
        if removal_tags:
            # Remove the specified tags, except those related to a job set,
            # from the tags to update.
            validate_job_tags(removal_tags, IBMQJobInvalidStateError)
            for tag_to_remove in removal_tags:
                # if tag_to_remove.startswith(self._tag_prefix):
                #     logger.warning('The tag "%s" for job %s will not be removed, because '
                #                    'it is used internally by the ibmq-provider.',
                #                    tag_to_remove, self.job_id())
                #     continue
                if tag_to_remove in tags_to_update:
                    tags_to_update.remove(tag_to_remove)
                else:
                    logger.warning('The tag "%s" for job %s will not be removed, because it was '
                                   'not found in the job tags to update %s',
                                   tag_to_remove, self.job_id(), tags_to_update)

        print(f">>>>>>> IBMQCompisitejob._get_tags_to_update return val {tags_to_update}")
        return tags_to_update

    def status(self) -> JobStatus:
        """Query the server for the latest job status.

        Note:
            This method is not designed to be invoked repeatedly in a loop for
            an extended period of time. Doing so may cause the server to reject
            your request.
            Use :meth:`wait_for_final_state()` if you want to wait for the job to finish.

        Note:
            If the job failed, you can use :meth:`error_message()` to get
            more information.

        Note:
            Since this job contains multiple sub-jobs, the returned status is mapped
            in the following order:

                * INITIALIZING - if any sub-job is being initialized.
                * VALIDATING - if any sub-job is being validated.
                * QUEUED - if any sub-job is queued.
                * RUNNING - if any sub-job is still running.
                * ERROR - if any sub-job incurred an error.
                * CANCELLED - if any sub-job is cancelled.
                * DONE - if all sub-jobs finished.

        Returns:
            The status of the job.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        self._update_status_queue_info_error()
        print(f">>>>>> IBMQCompositeJob status: status={self._status}")
        return self._status

    def report(self, detailed: bool = True) -> str:
        """Return a report on current sub-job statuses.

        Args:
            detailed: If ``True``, return a detailed report. Otherwise return a
                summary report.

        Returns:
            A report on sub-job statuses.
        """
        report = [f"Composite Job {self.job_id()}:",
                  "  Summary report:"]

        self._move_jobs_from_queue()
        print(f">>>>>> report: self._jobs={self._jobs.values()}")
        by_status = defaultdict(int)
        by_id = {}
        for job in self._jobs.values():
            status = job.status()
            by_status[status] += 1
            by_id[job.job_id()] = status
        by_status[JobStatus.ERROR] += len(self._job_submit_errors)

        # Summary report.
        count_report = []
        # Format header.
        for stat in ['Total', 'Successful', 'Failed', 'Cancelled', 'Running', 'Pending']:
            count_report.append(' '*4 + stat + " jobs: {}")
        max_text = max(len(text) for text in count_report)
        count_report = [text.rjust(max_text) for text in count_report]
        # Format counts.
        count_report[0] = count_report[0].format(len(self._circuit_indexes))
        non_pending_count = 0
        for idx, stat in enumerate([JobStatus.DONE, JobStatus.ERROR,
                                    JobStatus.CANCELLED, JobStatus.RUNNING], 1):
            non_pending_count += by_status[stat]
            count_report[idx] = count_report[idx].format(by_status[stat])
        count_report[-1] = count_report[-1].format(len(self._circuit_indexes) - non_pending_count)
        report += count_report

        # Detailed report.
        if detailed:
            report.append("\n  Detail report:")
            indexed_error = {sub_err['job_index']: sub_err['error']
                             for sub_err in self._job_submit_errors}

            for idx, circuit_indexes in enumerate(self._circuit_indexes):
                report.append(' '*4 + f'Circuits {circuit_indexes[0]}-{circuit_indexes[1]}:')
                report.append(' '*6 + f'Job index: {idx}')
                if idx in self._jobs:
                    job = self._jobs[idx]
                    report.append(' '*6 + f'Job ID: {job.job_id()}')
                    report.append(' '*6 + f'Status: {by_id[job.job_id()]}')
                elif idx in indexed_error:
                    report.append(' '*6 + f"Status: {indexed_error[idx]}")
                else:
                    report.append(' '*6 + "Status: Job not yet submitted.")

        return '\n'.join(report)

    def error_message(self) -> Optional[str]:
        """Provide details about the reason of failure.

        Note:
            This method blocks until the job finishes.

        Returns:
            An error report if the job failed or ``None`` otherwise.
        """
        self.wait_for_final_state()
        if self._status != JobStatus.ERROR:
            return None

        if not self._job_error_msg:
            self._update_status_queue_info_error()

        return self._job_error_msg

    def queue_position(self, refresh: bool = False) -> Optional[int]:
        """Return the position of the job in the server queue.

        This method returns the queue position of the sub-job that is
        last in queue.

        Note:
            The position returned is within the scope of the provider
            and may differ from the global queue position.

        Args:
            refresh: If ``True``, re-query the server to get the latest value.
                Otherwise return the cached value.

        Returns:
            Position in the queue or ``None`` if position is unknown or not applicable.
        """
        if refresh:
            self._update_status_queue_info_error()
        if self._status != JobStatus.QUEUED:
            self._queue_info = None
            return None
        return self._queue_info.queue_position if self._queue_info else None

    def queue_info(self) -> Optional[QueueInfo]:
        """Return queue information for this job.

        This method returns the queue information of the sub-job that is
        last in queue.

        The queue information may include queue position, estimated start and
        end time, and dynamic priorities for the hub, group, and project. See
        :class:`QueueInfo` for more information.

        Note:
            The queue information is calculated after the job enters the queue.
            Therefore, some or all of the information may not be immediately
            available, and this method may return ``None``.

        Returns:
            A :class:`QueueInfo` instance that contains queue information for
            this job, or ``None`` if queue information is unknown or not
            applicable.
        """
        self._update_status_queue_info_error()
        if self._status != JobStatus.QUEUED:
            self._queue_info = None
        return self._queue_info

    def creation_date(self) -> Optional[datetime]:
        """Return job creation date, in local time.

        Returns:
            The job creation date as a datetime object, in local time, or
            ``None`` if job submission hasn't finished or failed.
        """
        if not self._creation_date:
            self._move_jobs_from_queue()
            if not self._jobs:
                return None
            self._creation_date = min([job.creation_date() for job in self._jobs.values()])
        return self._creation_date

    def share_level(self) -> str:
        """Return the share level of the job.

        The share level is one of ``global``, ``hub``, ``group``, ``project``, and ``none``.

        Returns:
            The share level of the job.
        """
        return self._share_level

    def time_per_step(self) -> Optional[Dict]:
        """Return the date and time information on each step of the job processing.

        The output dictionary contains the date and time information on each
        step of the job processing, in local time. The keys of the dictionary
        are the names of the steps, and the values are the date and time data,
        as a datetime object with local timezone info.
        For example::

            {'CREATING': datetime(2020, 2, 13, 15, 19, 25, 717000, tzinfo=tzlocal(),
             'CREATED': datetime(2020, 2, 13, 15, 19, 26, 467000, tzinfo=tzlocal(),
             'VALIDATING': datetime(2020, 2, 13, 15, 19, 26, 527000, tzinfo=tzlocal()}

        Returns:
            Date and time information on job processing steps, in local time,
            or ``None`` if the information is not yet available.
        """
        output = None
        creation_date = self.creation_date()
        if creation_date is not None:
            output = {'CREATING': creation_date}
        if self._has_pending_submit():
            return output

        timestamps = defaultdict(list)
        for job in self._jobs.values():
            job_timestamps = job.time_per_step()
            if job_timestamps is None:
                continue
            for key, val in job_timestamps.items():
                timestamps[key].append(val)

        self._update_status_queue_info_error()
        for key, val in timestamps.items():
            if JOB_STATUS_TO_INT[api_status_to_job_status(key)] > JOB_STATUS_TO_INT[self._status]:
                continue
            if key == 'CREATING':
                continue
            if key in ['TRANSPILING', 'VALIDATING', 'QUEUED', 'RUNNING']:
                output[key] = sorted(val)[0]
            else:
                output[key] = sorted(val, reverse=True)[0]

        return output

    def scheduling_mode(self) -> Optional[str]:
        """Return the scheduling mode the job is in.

        The scheduling mode indicates how the job is scheduled to run. For example,
        ``fairshare`` indicates the job is scheduled using a fairshare algorithm.

        ``fairshare`` is returned if any of the sub-jobs has scheduling mode of
        ``fairshare``.

        This information is only available if the job status is ``RUNNING`` or ``DONE``.

        Returns:
            The scheduling mode the job is in or ``None`` if the information
            is not available.
        """
        if self._has_pending_submit():
            return None

        mode = None
        for job in self._jobs.values():
            job_mode = job.scheduling_mode()
            print(f">>>>>> IBMQCompositeJob scheduling_mode: job_mode={job_mode}")
            if job_mode == 'fairshare':
                return 'fairshare'
            if job_mode:
                mode = job_mode
        return mode

    @property
    def client_version(self) -> Dict[str, str]:
        """Return version of the client used for this job.

        Returns:
            Client version in dictionary format, where the key is the name
                of the client and the value is the version. An empty dictionary
                is returned if the information is not yet known.
        """
        self._move_jobs_from_queue()
        if not self._jobs:
            return {}
        return next(iter(self._jobs.values())).client_version

    @client_version.setter
    def client_version(self, data: Dict[str, str]) -> None:
        """Set client version.

        Args:
            data: Client version.
        """
        warnings.warn('The ``client_version`` setter method is deprecated and '
                      'will be removed in a future release. You can use the '
                      '"QE_CUSTOM_CLIENT_APP_HEADER" environment variable to '
                      'specify custom header for requests sent to the server.',
                      DeprecationWarning, stacklevel=2)
        if data:
            if data.get('name', '').startswith('qiskit'):
                self._client_version = dict(
                    zip(data['name'].split(','), data['version'].split(',')))
            else:
                self._client_version = \
                    {data.get('name', 'unknown'): data.get('version', 'unknown')}
        else:
            self._client_version = {}

    @property
    def experiment_id(self) -> str:
        """Return the experiment ID.

        Returns:
            ID of the experiment this job is part of.
        """
        if not self._experiment_id and self._jobs:
            self._experiment_id = next(iter(self._jobs.values())).experiment_id
        return self._experiment_id

    def refresh(self) -> None:
        """Obtain the latest job information from the server.

        This method may add additional attributes to this job instance, if new
        information becomes available.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        self._move_jobs_from_queue()
        for job in self._jobs.values():
            if job.status() not in JOB_FINAL_STATES:
                job.refresh()

    def circuits(self) -> List[Union[QuantumCircuit, Schedule]]:
        """Return the circuits or pulse schedules for this job.

        Returns:
            The circuits or pulse schedules for this job.
        """
        if not self._circuits:
            qobj = self._get_qobj()
            self._circuits, _, _ = disassemble(qobj)

        return self._circuits

    def backend_options(self) -> Dict[str, Any]:
        """Return the backend configuration options used for this job.

        Options that are not applicable to the job execution are not returned.
        Some but not all of the options with default values are returned.
        You can use :attr:`qiskit.providers.ibmq.IBMQBackend.options` to see
        all backend options.

        Returns:
            Backend options used for this job.
        """
        qobj = self._get_qobj()
        _, options, _ = disassemble(qobj)
        return options

    def header(self) -> Dict:
        """Return the user header specified for this job.

        Returns:
            User header specified for this job. An empty dictionary
            is returned if the header cannot be retrieved.
        """
        qobj = self._get_qobj()
        _, _, header = disassemble(qobj)
        return header

    @_requires_submit
    def wait_for_final_state(
            self,
            timeout: Optional[float] = None,
            wait: Optional[float] = None,
            callback: Optional[Callable] = None
    ) -> None:
        """Wait until the job progresses to a final state such as ``DONE`` or ``ERROR``.

        Args:
            timeout: Seconds to wait for the job. If ``None``, wait indefinitely.
            wait: Seconds to wait between invoking the callback function. If ``None``,
                the callback function is invoked only if job status or queue position
                has changed.
            callback: Callback function invoked after each querying iteration.
                The following positional arguments are provided to the callback function:

                    * job_id: Job ID
                    * job_status: Status of the job from the last query.
                    * job: This ``IBMQCompositeJob`` instance.

                In addition, the following keyword arguments are also provided:

                    * queue_info: A :class:`QueueInfo` instance with job queue information,
                      or ``None`` if queue information is unknown or not applicable.
                      You can use the ``to_dict()`` method to convert the
                      :class:`QueueInfo` instance to a dictionary, if desired.

        Raises:
            IBMQJobTimeoutError: if the job does not reach a final state before the
                specified timeout.
        """
        if self._status in JOB_FINAL_STATES:
            return

        self._user_callback = callback
        self._user_wait_value = wait
        status_callback = self._status_callback if callback else None

        # We need to monitor all jobs to give the most up-to-date information
        # to the user callback function. Websockets are preferred to avoid
        # excessive requests.
        job_futures = []
        for job in self._jobs.values():
            job_futures.append(self._executor.submit(job.wait_for_final_state, timeout=timeout,
                                                     wait=wait, callback=status_callback))
        future_stats = futures.wait(job_futures, timeout=timeout)
        for j in self._jobs.values():
            print(f">>>>> sub job {j.job_id()} stat: {j.status()}")
        self._update_status_queue_info_error()
        print(f">>>>>> wait_for_final_state self._status={self._status}")
        if future_stats[1]:
            raise IBMQJobTimeoutError(f"Timeout waiting for job {self.job_id()}") from None
        for fut in future_stats[0]:
            exception = fut.exception()
            if exception is not None:
                raise exception from None

    def sub_jobs(self, block_for_submit: bool = True) -> List[IBMQCircuitJob]:
        """Return all submitted sub-jobs.

        Args:
            block_for_submit: ``True`` if this method should block until
                all sub-jobs are submitted. ``False`` if the method should
                return immediately with submitted sub-jobs, if any.

        Returns:
            All submitted sub-jobs.
        """
        if block_for_submit:
            futures.wait(self._job_submit_futures)
        self._move_jobs_from_queue()
        sorted_sub_jobs = [None]*len(self._jobs)
        for key, val in self._jobs.items():
            sorted_sub_jobs[key] = val

        return sorted_sub_jobs

    def sub_job(self, circuit_index: int) -> Optional[IBMQCircuitJob]:
        """Retrieve the job used to submit the specified circuit.

        Args:
            circuit_index: Index of the circuit whose job is to be returned.

        Returns:
            The Job submitted for the circuit, or ``None`` if the job has
            not been submitted.

        Raises:
            IBMQJobInvalidStateError: If the circuit index is out of range.
        """
        self._move_jobs_from_queue()
        last_index = self._circuit_indexes[-1][1]
        if circuit_index > last_index:
            raise IBMQJobInvalidStateError(
                f"Circuit index {circuit_index} greater than circuit count {last_index}.")

        for idx, circ_indexes in enumerate(self._circuit_indexes):
            if circ_indexes[0] >= circuit_index >= circ_indexes[1]:
                if idx in self._jobs:
                    return self._jobs[idx]
                break

        return None

    def rerun_failed(self):
        """Re-submit all failed sub-jobs.

        Note:
            All sub-jobs that are in "ERROR" or "CANCELLED" states will
            be re-submitted.
            Sub-jobs that failed to be submitted will only be re-submitted if the
            circuits are known. That is, if this ``IBMQCompositeJob`` was
            returned by :meth:`qiskit.providers.ibmq.IBMQBackend.run` and not
            retrieved from the server.
        """
        total_jobs = len(self._circuit_indexes)
        self._move_jobs_from_queue()

        # Rerun failed submits.
        if self._job_submit_errors:
            new_qobj_dict = {key: val for key, val in self._qobj.to_dict().items()
                             if key != 'experiments'}  # Copy all but circuits.
            new_qobj_dict['experiments'] = []
            submit_errors = self._job_submit_errors.copy()
            self._job_submit_errors = []
            for bad_submit in submit_errors:
                start_idx, end_idx = bad_submit['start_index'], bad_submit['end_index']
                new_qobj_dict['experiments'].extend(
                    self._qobj.to_dict()['experiments'][start_idx:end_idx+1])
                if new_qobj_dict['type'] == 'PULSE':
                    new_qobj = PulseQobj.from_dict(new_qobj_dict)
                else:
                    new_qobj = QasmQobj.from_dict(new_qobj_dict)
                job_index = bad_submit['job_index']
                self._job_submit_events[job_index].clear()
                self._job_submit_futures.append(
                    self._executor.submit(self._async_submit, qobj=new_qobj, start_index=start_idx,
                                          end_index=end_idx, job_index=job_index,
                                          total=total_jobs))
        # Rerun failed jobs.
        job_indexes = self._jobs.keys()
        for idx in job_indexes:
            job = self._jobs[idx]
            if job.status() in [JobStatus.ERROR, JobStatus.CANCELLED]:
                qobj = job._get_qobj()
                start_idx, end_idx = self._circuit_indexes[idx]
                del self._jobs[idx]
                self._job_submit_futures.append(
                    self._executor.submit(self._async_submit, qobj=qobj, start_index=start_idx,
                                          end_index=end_idx, job_index=idx,
                                          total=total_jobs))
        # Wake up the next submit.
        try:
            next(event for event in self._job_submit_events if not event.is_set()).set()
        except StopIteration:
            print(f">>>>>> rerun_failed no event found")
            pass
        self._status = JobStatus.INITIALIZING

    def block_for_submit(self) -> None:
        """Block until all sub-jobs are submitted."""
        futures.wait(self._job_submit_futures)

    def _status_callback(
            self,
            job_id: str,
            job_status: JobStatus,
            job: IBMQCircuitJob,
            queue_info: QueueInfo
    ) -> None:
        """Callback function used when a sub-job status changes.

        Args:
            job_id: Sub-job ID.
            job_status: Sub-job status.
            job: Sub-job.
            queue_info: Sub-job queue info.
        """
        with self._callback_lock:
            self._job_statuses[job_id] = JobStatusQueueInfo(job_status, queue_info)
            status, queue_info = last_job_stat_pos(list(self._job_statuses.values()))
            pos = queue_info.position if queue_info else None

            report = False
            cur_time = time.time()
            if self._user_wait_value is None:
                if self._last_reported_stat != (status, pos):
                    report = True
            elif cur_time - self._last_reported_time >= self._user_wait_value:
                report = True

            self._last_reported_stat = (status, pos)
            self._last_reported_time = cur_time
            if report:
                logger.debug("Invoking callback function, job status=%s, queue_info=%s",
                             status, queue_info)
                self._user_callback(self.job_id(), status, self, queue_info=queue_info)

    def _update_status_queue_info_error(self) -> None:
        """Update the status, queue information, and error message of this composite job."""

        if self._has_pending_submit():
            self._status = JobStatus.INITIALIZING
            return

        if self._status in [JobStatus.CANCELLED, JobStatus.DONE]:
            return
        if self._status is JobStatus.ERROR and self._job_error_msg:
            return

        self._move_jobs_from_queue()
        statuses = defaultdict(list)
        for job in self._jobs.values():
            status = job.status()
            statuses[status].append(job)

        print(f">>>>>> _update_status_queue_info_error: statuses={statuses.keys()}, {statuses.values()}")

        for stat in [JobStatus.INITIALIZING, JobStatus.VALIDATING]:
            if stat in statuses:
                self._status = stat
                return

        if JobStatus.QUEUED in statuses:
            self._status = JobStatus.QUEUED
            # Sort by queue position. Put `None` to the end.
            last_queued = sorted(
                statuses[JobStatus.QUEUED],
                key=lambda j: (j.queue_position() is None, j.queue_position()))[-1]
            self._queue_info = last_queued.queue_info()
            return

        if JobStatus.RUNNING in statuses:
            self._status = JobStatus.RUNNING
            return

        if JobStatus.ERROR in statuses or self._job_submit_errors:
            self._status = JobStatus.ERROR
            self._build_error_report(statuses.get(JobStatus.ERROR, []))
            return

        for stat in [JobStatus.CANCELLED, JobStatus.DONE]:
            if stat in statuses:
                self._status = stat
                return

        print(f">>>>>> all statuses: {statuses.keys()}")
        bad_stats = {k: [j.job_id() for j in v] for k, v in statuses.items()
                     if k not in JobStatus}
        raise IBMQJobInvalidStateError("Invalid job status found: " + str(bad_stats))

    def _build_error_report(self, failed_jobs: List[IBMQCircuitJob]) -> None:
        """Build the error report.

        Args:
            failed_jobs: A list of failed jobs.
        """
        def sort_by_indexes(item):
            match = re.match(r"Circuits (\d+)-(\d+):", item)
            if not match:
                return 0
            return match.group(1)

        error_list = []
        for job in failed_jobs:
            start_index, end_index = self._find_circuit_indexes(job, ['start_index', 'end_index'])
            error_list.append(f"Circuits {start_index}-{end_index}: Job {job.job_id()} failed: "
                              f"{job.error_message()}")
        for bad_submit in self._job_submit_errors:
            error_list.append(f"Circuits {bad_submit['start_index']}-{bad_submit['end_index']}: "
                              f"Job submit failed: {bad_submit['error']}")

        error_list.sort(key=sort_by_indexes)
        if len(error_list) > 1:
            self._job_error_msg = \
                'The following circuits failed:\n{}'.format('\n'.join(error_list))
        else:
            self._job_error_msg = error_list[0]

    def _find_circuit_indexes(self, job: IBMQCircuitJob, indexes: List[str]) -> List[int]:
        """Find the circuit indexes of the input job.

        Args:
            job: The circuit job.
            indexes: Names of the indexes to retrieve. The names can be
                ``job_index``, ``total``, ``start_index``, and ``end_index``.

        Returns:
            Job indexes.
        """
        index_tag = [tag for tag in job.tags() if tag.startswith(self._index_prefix)]
        match = None
        if index_tag:
            match = re.match(self._index_pattern, index_tag[0])
        if match is None:
            print(f">>>>> IBMQCompositeJob: {job.tags()}")
            raise IBMQJobInvalidStateError(f"Job {job.job_id()} in composite job {self.job_id()}"
                                           f" is missing proper tags.")
        output = []
        for name in indexes:
            output.append(int(match.group(name)))
        return output

    def _has_pending_submit(self) -> bool:
        """Return whether there are pending job submit futures.

        Returns:
            Whether there are pending job submit futures.
        """
        print(f">>>>>> self._job_submit_futures={self._job_submit_futures}")
        for fut in self._job_submit_futures:
            if fut.done():
                ex = fut.exception()
                if ex:
                    import traceback
                    print(f">>>>>> self.future exception")
                    # traceback.print_exception(type(ex), ex, ex.__traceback__)

        return not all(fut.done() for fut in self._job_submit_futures)

    def _gather_results(self, refresh: bool = False) -> Optional[Result]:
        """Retrieve the job result response.

        Args:
            refresh: If ``True``, re-query the server for the result.
               Otherwise return the cached value.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        if self._result and not refresh:
            return self._result

        job_results = []
        for job_idx in range(len(self._circuit_indexes)):
            if job_idx not in self._jobs:
                job_results.append(None)
                continue
            try:
                res = auto_retry(self._jobs[job_idx].result, refresh=refresh, partial=True)
                job_results.append(res)
            except (IBMQJobFailureError, IBMQJobInvalidStateError):
                job_results.append(None)

        try:
            good_result = next(res for res in job_results if res is not None).to_dict()
        except StopIteration:
            return None

        ref_expr_result = good_result['results'][0]
        template_expr_result = {
            'success': False,
            'data': {},
            'status': 'ERROR'
        }
        for key in ['shots', 'meas_level', 'seed', 'meas_return']:
            template_expr_result[key] = ref_expr_result.get(key, None)

        good_result['job_id'] = self.job_id()
        good_result['success'] = self._status == JobStatus.DONE
        good_result['results'] = []
        good_result['status'] = 'PARTIAL COMPLETED' if self._status != JobStatus.DONE \
            else 'COMPLETED'
        combined_result = Result.from_dict(good_result)

        for idx, result in enumerate(job_results):
            if result is not None:
                combined_result.results.extend(result.results)
            else:
                # Get experiment header from Qobj if possible.
                start_idx, end_idx = self._circuit_indexes[idx]
                experiments = None
                if idx in self._jobs:
                    experiments = self._jobs[idx]._get_qobj().experiments
                elif self._qobj:
                    experiments = self._qobj.experiments[start_idx:end_idx+1]

                expr_results = []
                for circ_idx in range(end_idx-start_idx+1):
                    if experiments:
                        template_expr_result['header'] = experiments[circ_idx].header.to_dict()
                    expr_results.append(ExperimentResult.from_dict(template_expr_result))
                combined_result.results.extend(expr_results)

        return combined_result

    def _get_qobj(self) -> Optional[Union[QasmQobj, PulseQobj]]:
        """Return the Qobj for this job.

        Returns:
            The Qobj for this job, or ``None`` if the job does not have a Qobj.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when retrieving
                job information from the server.
        """
        if not self._qobj:
            self._qobj = copy.deepcopy(self._jobs[0]._get_qobj())
            print(f">>>>>> IBMQCompositeJob._get_qobj: subjob 0 has {len(self._qobj.experiments)} exprs")
            for idx in range(1, len(self._jobs)):
                print(f">>>>>> IBMQCompositeJob._get_qobj: subjob {idx} has {len(self._jobs[idx]._get_qobj().experiments)} exprs")
                self._qobj.experiments.extend(self._jobs[idx]._get_qobj().experiments)
        return self._qobj

    def _move_jobs_from_queue(self) -> None:
        """Move jobs from the thread-safe queue to list."""
        while not self._jobs_queue.empty():
            try:
                job_idx, job = self._jobs_queue.get_nowait()
                self._jobs[job_idx] = job
            except queue.Empty:
                pass
        while not self._job_submit_error_queue.empty():
            try:
                self._job_submit_errors.append(self._job_submit_error_queue.get_nowait())
            except queue.Empty:
                pass
