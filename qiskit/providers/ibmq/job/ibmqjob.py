# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Quantum Experience job."""

import logging
from typing import Dict, Optional, Tuple, Any, List, Callable, Union
import warnings
from datetime import datetime
from concurrent import futures
from threading import Event
from queue import Empty

from marshmallow import ValidationError

from qiskit.providers import (BaseJob,  # type: ignore[attr-defined]
                              BaseBackend)
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import QasmQobj, PulseQobj
from qiskit.result import Result
from qiskit.validation import BaseModel, ModelValidationError, bind_schema

from ..apiconstants import ApiJobStatus, ApiJobKind
from ..api.clients import AccountClient
from ..api.exceptions import ApiError, UserTimeoutExceededError
from ..utils.utils import RefreshQueue
from ..utils.qobj_utils import dict_to_qobj
from .exceptions import (IBMQJobApiError, IBMQJobFailureError,
                         IBMQJobTimeoutError, IBMQJobInvalidStateError)
from .queueinfo import QueueInfo
from .schema import JobResponseSchema
from .utils import (build_error_report, api_status_to_job_status,
                    api_to_job_error, get_cancel_status)

logger = logging.getLogger(__name__)


@bind_schema(JobResponseSchema)
class IBMQJob(BaseModel, BaseJob):
    """Representation of a job that executes on an IBM Quantum Experience backend.

    The job may be executed on a simulator or a real device. A new ``IBMQJob``
    instance is returned when you call
    :meth:`IBMQBackend.run()<qiskit.providers.ibmq.ibmqbackend.IBMQBackend.run()>`
    to submit a job to a particular backend.

    If the job is successfully submitted, you can inspect the job's status by
    calling :meth:`status()`. Job status can be one of the
    :class:`~qiskit.providers.JobStatus` members.
    For example::

        from qiskit.providers.jobstatus import JobStatus

        job = backend.run(...)

        try:
            job_status = job.status()  # Query the backend server for job status.
            if job_status is JobStatus.RUNNING:
                print("The job is still running")
        except IBMQJobApiError as ex:
            print("Something wrong happened!: {}".format(ex))

    Note:
        An error may occur when querying the remote server to get job information.
        The most common errors are temporary network failures
        and server errors, in which case an
        :class:`~qiskit.providers.ibmq.job.IBMQJobApiError`
        is raised. These errors usually clear quickly, so retrying the operation is
        likely to succeed.

    Some of the methods in this class are blocking, which means control may
    not be returned immediately. :meth:`result()` is an example
    of a blocking method::

        job = backend.run(...)

        try:
            job_result = job.result()  # It will block until the job finishes.
            print("The job finished with result {}".format(job_result))
        except JobError as ex:
            print("Something wrong happened!: {}".format(ex))

    Job information retrieved from the server is attached to the ``IBMQJob``
    instance as attributes. Given that Qiskit and the server can be updated
    independently, some of these attributes might be deprecated or experimental.
    Supported attributes can be retrieved via methods. For example, you
    can use :meth:`creation_date()` to retrieve the job creation date,
    which is a supported attribute.
    """

    _executor = futures.ThreadPoolExecutor()
    """Threads used for asynchronous processing."""

    def __init__(self,
                 _backend: BaseBackend,
                 api: AccountClient,
                 _job_id: str,
                 _creation_date: datetime,
                 _api_status: ApiJobStatus,
                 **kwargs: Any) -> None:
        """IBMQJob constructor.

        Args:
            _backend: The backend instance used to run this job.
            api: Object for connecting to the server.
            _job_id: Job ID.
            _creation_date: Job creation date.
            _api_status: Job status returned by the server.
            kwargs: Additional job attributes.
        """
        # pylint: disable=redefined-builtin

        # Convert qobj from dictionary to Qobj.
        if isinstance(kwargs.get('_qobj', None), dict):
            self._qobj = dict_to_qobj(kwargs.pop('_qobj'))

        BaseModel.__init__(self, _backend=_backend, _job_id=_job_id,
                           _creation_date=_creation_date,
                           _api_status=_api_status, **kwargs)
        BaseJob.__init__(self, self.backend(), self.job_id())

        # Model attributes.
        self._api = api
        self._use_object_storage = (self.kind == ApiJobKind.QOBJECT_STORAGE)
        self._queue_info = None     # type: Optional[QueueInfo]
        self._status, self._queue_info = self._get_status_position(
            _api_status, kwargs.pop('info_queue', None))

        # Properties used for caching.
        self._cancelled = False
        self._job_error_msg = None  # type: Optional[str]

    def qobj(self) -> Optional[Union[QasmQobj, PulseQobj]]:
        """Return the Qobj for this job.

        Returns:
            The Qobj for this job, or ``None`` if the job does not have a Qobj.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when retrieving
                job information from the server.
        """
        if not self.kind:
            return None

        # pylint: disable=access-member-before-definition,attribute-defined-outside-init
        if not self._qobj:  # type: ignore[has-type]
            with api_to_job_error():
                qobj = self._api.job_download_qobj(
                    self.job_id(), self._use_object_storage)
                self._qobj = dict_to_qobj(qobj)

        return self._qobj

    def properties(self) -> Optional[BackendProperties]:
        """Return the backend properties for this job.

        Returns:
            The backend properties used for this job, or ``None`` if
            properties are not available.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        with api_to_job_error():
            properties = self._api.job_properties(job_id=self.job_id())

        if not properties:
            return None

        return BackendProperties.from_dict(properties)

    def result(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            partial: bool = False,
            refresh: bool = False
    ) -> Result:
        """Return the result of the job.

        Note:
            Some IBM Quantum Experience job results can only be read once. A
            second attempt to query the server for the same job will fail,
            since the job has already been "consumed".

            The first call to this method in an ``IBMQJob`` instance will
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

            For example, if one of the experiments in the job failed, trying to
            get the counts of the unsuccessful experiment would raise an exception
            since there are no counts to return::

                try:
                    counts = result.get_counts("failed_experiment")
                except QiskitError:
                    print("Experiment failed!")

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
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init

        if not self._wait_for_completion(timeout=timeout, wait=wait,
                                         required_status=(JobStatus.DONE,)):
            if self._status is JobStatus.CANCELLED:
                raise IBMQJobInvalidStateError('Unable to retrieve result for job {}. '
                                               'Job was cancelled.'.format(self.job_id()))

            if self._status is JobStatus.ERROR and not partial:
                raise IBMQJobFailureError(
                    'Unable to retrieve result for job {}. Job has failed. '
                    'Use job.error_message() to get more details.'.format(self.job_id()))

        return self._retrieve_result(refresh=refresh)

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
        try:
            response = self._api.job_cancel(self.job_id())
            self._cancelled = get_cancel_status(response)
            logger.debug('Job %s cancel status is "%s". Response data: %s.',
                         self.job_id(), self._cancelled, response)
            return self._cancelled
        except ApiError as error:
            self._cancelled = False
            raise IBMQJobApiError('Unexpected error when cancelling job {}: {}'
                                  .format(self.job_id(), str(error))) from error

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

        Returns:
            The status of the job.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        if self._status in JOB_FINAL_STATES:
            return self._status

        with api_to_job_error():
            api_response = self._api.job_status(self.job_id())
            self._status, self._queue_info = self._get_status_position(
                ApiJobStatus(api_response['status']), api_response.get('infoQueue', None))

        # Get all job attributes if the job is done.
        if self._status in JOB_FINAL_STATES:
            self.refresh()

        return self._status

    def done(self) -> bool:
        """Return whether the job has successfully run.

        Returns:
            ``True`` if the job is done, else ``False``.
        """
        return self._is_job_status(JobStatus.DONE)

    def running(self) -> bool:
        """Return whether the job is actively running.

        Returns:
            ``True`` if the job is running, else ``False``.
        """
        return self._is_job_status(JobStatus.RUNNING)

    def cancelled(self) -> bool:
        """Return whether the job has been cancelled.

        Returns:
            ``True`` if the job has been cancelled, else ``False``.
        """
        return self._is_job_status(JobStatus.CANCELLED)

    def _is_job_status(self, job_status: JobStatus) -> bool:
        """Return whether the current job status matches the desired one.

        Args:
            job_status: The job status to check against.

        Returns:
            ``True`` if the current job status matches the desired one, else ``False``.
        """
        return self.status() == job_status

    def error_message(self) -> Optional[str]:
        """Provide details about the reason of failure.

        Returns:
            An error report if the job failed or ``None`` otherwise.
        """
        # pylint: disable=attribute-defined-outside-init
        if not self._wait_for_completion(required_status=(JobStatus.ERROR,)):
            return None

        if not self._job_error_msg:
            # First try getting error messages from the result.
            try:
                self._retrieve_result()
            except IBMQJobFailureError:
                pass

        if not self._job_error_msg:
            # Then try refreshing the job
            if not self._error:
                self.refresh()
            if self._error:
                self._job_error_msg = self._format_message_from_error(
                    self._error.__dict__)
            elif self._api_status:
                self._job_error_msg = self._api_status.value
            else:
                self._job_error_msg = "Unknown error."

        return self._job_error_msg

    def queue_position(self, refresh: bool = False) -> Optional[int]:
        """Return the position of the job in the server queue.

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
            # Get latest position
            self.status()

        if self._queue_info:
            return self._queue_info.position
        return None

    def queue_info(self) -> Optional[QueueInfo]:
        """Return queue information for this job.

        The queue information may include queue position, estimated start and
        end time, and dynamic priorities for the hub, group, and project. See
        :class:`QueueInfo` for more information.

        Note:
            Even if the job is queued, some of its queue information may not
            be immediately available.

        Returns:
            A :class:`QueueInfo` instance that contains queue information for
            this job, or ``None`` if queue information is unknown or not
            applicable.
        """
        # Get latest queue information.
        self.status()

        # Return queue information only if it has any useful information.
        if self._queue_info and any(
                value is not None for attr, value in self._queue_info.__dict__.items()
                if not attr.startswith('_') and attr != 'job_id'):
            return self._queue_info
        return None

    def creation_date(self) -> str:
        """Return job creation date.

        Returns:
            Job creation date.
        """
        return self._creation_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    def job_id(self) -> str:
        """Return the job ID assigned by the server.

        Returns:
            Job ID.
        """
        return self._job_id

    def name(self) -> Optional[str]:
        """Return the name assigned to this job.

        Returns:
            Job name or ``None`` if no name was assigned to this job.
        """
        return self._name

    def tags(self) -> List[str]:
        """Return the tags assigned to this job.

        Returns:
            Tags assigned to this job.
        """
        return self._tags.copy()

    def time_per_step(self) -> Optional[Dict]:
        """Return the date and time information on each step of the job processing.

        The output dictionary contains the date and time information on each
        step of the job processing. The keys of the dictionary are the names
        of the steps, and the values are the date and time data. For example::

            {'CREATING': '2020-02-13T20:19:25.717Z',
             'CREATED': '2020-02-13T20:19:26.467Z',
             'VALIDATING': '2020-02-13T20:19:26.527Z'}

        Returns:
            Date and time information on job processing steps, or ``None``
            if the information is not yet available.
        """
        if not self._time_per_step or self._status not in JOB_FINAL_STATES:
            self.refresh()
        return self._time_per_step

    def scheduling_mode(self) -> Optional[str]:
        """Return the scheduling mode the job is in.

        The scheduling mode indicates how the job is scheduled to run. For example,
        ``fairshare`` indicates the job is scheduled using a fairshare algorithm.

        This information is only available if the job status is ``RUNNING`` or ``DONE``.

        Returns:
            The scheduling mode the job is in or ``None`` if the information
            is not available.
        """
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init
        if self._run_mode is None:
            self.refresh()
            if self._status in [JobStatus.RUNNING, JobStatus.DONE] and self._run_mode is None:
                self._run_mode = "fairshare"  # type: Optional[str]

        return self._run_mode

    def submit(self) -> None:
        """Submit this job to an IBM Quantum Experience backend.

        Note:
            This function is deprecated, please use
            :meth:`IBMQBackend.run()<qiskit.providers.ibmq.ibmqbackend.IBMQBackend.run()>`
            to submit a job.

        Raises:
            IBMQJobInvalidStateError: If the job has already been submitted.
        """
        if self.job_id() is not None:
            raise IBMQJobInvalidStateError(
                'The job {} has already been submitted.'.format(self.job_id()))

        warnings.warn("job.submit() is deprecated. Please use "
                      "IBMQBackend.run() to submit a job.", DeprecationWarning, stacklevel=2)

    def refresh(self) -> None:
        """Obtain the latest job information from the server.

        This method may add additional attributes to this job instance, if new
        information becomes available.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
        """
        with api_to_job_error():
            api_response = self._api.job_get(self.job_id())

        saved_model_cls = JobResponseSchema.model_cls
        try:
            # Load response into a dictionary
            JobResponseSchema.model_cls = dict
            data = self.schema.load(api_response)
            BaseModel.__init__(self, **data)

            # Model attributes.
            self._use_object_storage = (self.kind == ApiJobKind.QOBJECT_STORAGE)
            self._status, self._queue_info = self._get_status_position(
                data.pop('_api_status'), data.pop('info_queue', None))
        except ValidationError as ex:
            raise IBMQJobApiError('Unexpected return value received from the server when '
                                  'refreshing job {}: {}'.format(self.job_id(), str(ex))) from ex
        finally:
            JobResponseSchema.model_cls = saved_model_cls

    def to_dict(self) -> None:
        """Serialize the model into a Python dict of simple types.

        Note:
            This is an inherited but unsupported method and may not work properly.
        """
        warnings.warn("IBMQJob.to_dict() is not supported and may not work properly.",
                      stacklevel=2)
        return BaseModel.to_dict(self)

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
                    * job: This ``IBMQJob`` instance.

                In addition, the following keyword arguments are also provided:

                    * queue_info: A :class:`QueueInfo` instance with job queue information,
                      or ``None`` if queue information is unknown or not applicable.
                      You can use the ``to_dict()`` method to convert the
                      :class:`QueueInfo` instance to a dictionary, if desired.

        Raises:
            IBMQJobTimeoutError: if the job does not reach a final state before the
                specified timeout.
        """
        exit_event = Event()
        status_queue = RefreshQueue(maxsize=1)
        future = None
        if callback:
            future = self._executor.submit(self._status_callback,
                                           status_queue=status_queue,
                                           exit_event=exit_event,
                                           callback=callback,
                                           wait=wait)
        try:
            self._wait_for_completion(timeout=timeout, status_queue=status_queue)
        finally:
            if future:
                # Make sure the callback thread wakes up.
                exit_event.set()
                status_queue.notify_all()
                future.result()

    def _wait_for_completion(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            required_status: Tuple[JobStatus] = JOB_FINAL_STATES,
            status_queue: Optional[RefreshQueue] = None
    ) -> bool:
        """Wait until the job progress to a final state such as ``DONE`` or ``ERROR``.

        Args:
            timeout: Seconds to wait for job. If ``None``, wait indefinitely.
            wait: Seconds between queries.
            required_status: The final job status required.
            status_queue: Queue used to share the latest status.

        Returns:
            ``True`` if the final job status matches one of the required states.

        Raises:
            IBMQJobTimeoutError: if the job does not return results before a
                specified timeout.
            IBMQJobApiError: if there was an error getting the job status
                due to a network issue.
        """
        if self._status in JOB_FINAL_STATES:
            return self._status in required_status

        try:
            status_response = self._api.job_final_status(
                self.job_id(), timeout=timeout, wait=wait, status_queue=status_queue)
        except UserTimeoutExceededError:
            raise IBMQJobTimeoutError(
                'Timeout while waiting for job {}.'.format(self._job_id)) from None
        except ApiError as api_err:
            logger.error('Maximum retries exceeded: '
                         'Error checking job status due to a network error.')
            raise IBMQJobApiError('Error checking job status due to a network '
                                  'error: {}'.format(str(api_err))) from api_err

        self._status, self._queue_info = self._get_status_position(
            ApiJobStatus(status_response['status']), status_response.get('infoQueue', None))

        # Get all job attributes when the job is done.
        self.refresh()

        return self._status in required_status

    def _retrieve_result(self, refresh: bool = False) -> Result:
        """Retrieve the job result response.

        Args:
            refresh: If ``True``, re-query the server for the result.
               Otherwise return the cached value.

        Returns:
            The job result.

        Raises:
            IBMQJobApiError: If an unexpected error occurred when communicating
                with the server.
            IBMQJobFailureError: If the job failed and partial result could not
                be retrieved.
            IBMQJobInvalidStateError: If result is in an unsupported format.
        """
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init
        result_response = None
        if not self._result or refresh:  # type: ignore[has-type]
            try:
                result_response = self._api.job_result(self.job_id(), self._use_object_storage)
                self._result = Result.from_dict(result_response)
            except (ModelValidationError, ApiError) as err:
                if self._status is JobStatus.ERROR:
                    raise IBMQJobFailureError(
                        'Unable to retrieve result for job {}. Job has failed. Use '
                        'job.error_message() to get more details.'.format(self.job_id())) from err
                if not self.kind:
                    raise IBMQJobInvalidStateError(
                        'Unable to retrieve result for job {}. Job result '
                        'is in an unsupported format.'.format(self.job_id())) from err
                raise IBMQJobApiError(
                    'Unable to retrieve result for '
                    'job {}: {}'.format(self.job_id(), str(err))) from err
            finally:
                # In case partial results are returned or job failure, an error message is cached.
                if result_response:
                    self._check_for_error_message(result_response)

        if self._status is JobStatus.ERROR and not self._result.results:
            raise IBMQJobFailureError(
                'Unable to retrieve result for job {}. Job has failed. '
                'Use job.error_message() to get more details.'.format(self.job_id()))

        return self._result

    def _check_for_error_message(self, result_response: Dict[str, Any]) -> None:
        """Retrieves the error message from the result response.

        Args:
            result_response: Dictionary of the result response.
        """
        if result_response.get('results', None):
            # If individual errors given
            self._job_error_msg = build_error_report(result_response['results'])
        elif 'error' in result_response:
            self._job_error_msg = self._format_message_from_error(result_response['error'])

    def _format_message_from_error(self, error: Dict) -> str:
        """Format message from the error field.

        Args:
            The error field.

        Returns:
            A formatted error message.

        Raises:
            IBMQJobApiError: If invalid data received from the server.
        """
        try:
            return "{}. Error code: {}.".format(error['message'], error['code'])
        except KeyError as ex:
            raise IBMQJobApiError('Failed to get error message for job {}. Invalid error '
                                  'data received: {}'.format(self.job_id(), error)) from ex

    def _status_callback(
            self,
            status_queue: RefreshQueue,
            exit_event: Event,
            callback: Callable,
            wait: Optional[float]
    ) -> None:
        """Invoke the callback function with the latest job status.

        Args:
            status_queue: Queue containing the latest status.
            exit_event: Event used to notify this thread to quit.
            callback: Callback function to invoke.
            wait: Time between each callback function call. If ``None``,
                the callback function is invoked only if job status or queue position
                has changed.
        """
        status_response = None
        last_data = (None, None)  # type: Tuple[Optional[JobStatus], Optional[QueueInfo]]

        while not exit_event.is_set():
            try:
                if wait is None:
                    status_response = status_queue.get(block=True)
                else:
                    exit_event.wait(wait)
                    status_response = status_queue.get(block=False)
            except Empty:
                pass

            if not status_response:
                continue

            try:
                status, queue_info = self._get_status_position(
                    ApiJobStatus(status_response['status']),
                    status_response.get('infoQueue', None))
            except IBMQJobApiError as ex:
                logger.warning("Unexpected error when getting job status: %s", ex)
                continue

            if status in JOB_FINAL_STATES:
                return
            if wait is None:
                if (status, queue_info) == last_data:
                    continue
                last_data = (status, queue_info)
            callback(self.job_id(), status, self, queue_info=queue_info)

    def _get_status_position(
            self,
            api_status: ApiJobStatus,
            api_info_queue: Optional[Dict] = None
    ) -> Tuple[JobStatus, Optional[QueueInfo]]:
        """Return the corresponding job status for the input server job status.

        Args:
            api_status: Server job status
            api_info_queue: Job queue information from the server response.

        Returns:
            A tuple of job status and queue information (``None`` if not available).

        Raises:
             IBMQJobApiError: if unexpected return value received from the server.
        """
        queue_info = None
        try:
            status = api_status_to_job_status(api_status)
            if api_status is ApiJobStatus.RUNNING and api_info_queue:
                api_info_queue['job_id'] = self.job_id()  # job_id is used for QueueInfo.format().
                queue_info = QueueInfo.from_dict(api_info_queue)
                if queue_info._status == ApiJobStatus.PENDING_IN_QUEUE.value:
                    status = JobStatus.QUEUED
        except (KeyError, ValidationError) as ex:
            raise IBMQJobApiError('Unexpected return value received from the server when getting '
                                  'status for job {}: {}'.format(self.job_id(), str(ex))) from ex

        if status is not JobStatus.QUEUED:
            queue_info = None

        return status, queue_info
