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

"""IBMQJob module

This module is used for creating a job objects for the IBM Q Experience.
"""

import logging
from typing import Dict, Optional, Tuple, Any, List, Callable
import warnings
from datetime import datetime
from collections import deque
from concurrent import futures
from threading import Event

from marshmallow import ValidationError

from qiskit.providers import (BaseJob,  # type: ignore[attr-defined]
                              BaseBackend)
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import Qobj
from qiskit.result import Result
from qiskit.validation import BaseModel, ModelValidationError, bind_schema

from ..apiconstants import ApiJobStatus, ApiJobKind
from ..api.clients import AccountClient
from ..api.exceptions import ApiError, UserTimeoutExceededError
from .exceptions import (IBMQJobApiError, IBMQJobFailureError,
                         IBMQJobTimeoutError, IBMQJobInvalidStateError)
from .queueinfo import QueueInfo
from .schema import JobResponseSchema
from .utils import build_error_report, api_status_to_job_status, api_to_job_error

logger = logging.getLogger(__name__)


@bind_schema(JobResponseSchema)
class IBMQJob(BaseModel, BaseJob):
    """Representation of a job that will be execute on a IBMQ backend.

    Represent a job that is or has been executed on an IBMQ simulator or real
    device. New jobs are intended to be created by calling ``run()`` on a
    particular backend.

    If the job was successfully submitted, you can inspect the job's status by
    using ``status()``. Status can be one of ``JobStatus`` members::

        from qiskit.providers.jobstatus import JobStatus

        job = IBMQBackend.run(...)

        try:
            job_status = job.status() # It will query the backend API.
            if job_status is JobStatus.RUNNING:
                print('The job is still running')

        except IBMQJobApiError as ex:
            print("Something wrong happened!: {}".format(ex))

    A call to ``status()`` can raise if something happens at the server level
    that prevents Qiskit from determining the status of the job. An example of
    this is a temporary connection lose or a network failure.

    The ``status()`` method is an example of non-blocking API.
    The ``result()`` method is an example of blocking API:

        job = IBMQBackend.run(...)

        try:
            job_result = job.result() # It will block until finishing.
            print('The job finished with result {}'.format(job_result))

        except JobError as ex:
            print("Something wrong happened!: {}".format(ex))

    Many of the ``IBMQJob`` methods can raise ``IBMQJobApiError`` if unexpected
    failures happened at the server level.

    Job information retrieved from the API server is attached to the ``IBMQJob``
    instance as attributes. Given that Qiskit and the API server can be updated
    independently, some of these attributes might be deprecated or experimental.
    Supported attributes can be retrieved via methods. For example, you
    can use ``IBMQJob.creation_date()`` to retrieve the job creation date,
    which is a supported attribute.

    Note:
        When querying the server for getting the job information, two kinds
        of errors are possible. The most severe is the one preventing Qiskit
        from getting a response from the server. This can be caused by a
        network failure or a temporary system break. In these cases, the job
         method will raise.

        If Qiskit successfully retrieves the status of a job, it could be it
        finished with errors. In that case, ``status()`` will simply return
        ``JobStatus.ERROR`` and you can call ``error_message()`` to get more
        info.
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
        """IBMQJob init function.

        Args:
            _backend: the backend instance used to run this job.
            api: object for connecting to the API.
            _job_id: job ID of this job.
            _creation_date: job creation date.
            _api_status: API job status.
            kwargs: additional job attributes, that will be added as
                instance members.
        """
        # pylint: disable=redefined-builtin
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

    def qobj(self) -> Optional[Qobj]:
        """Return the Qobj for this job.

        Note that this method might involve querying the API for results if the
        Job has been created in a previous Qiskit session.

        Returns:
            the Qobj for this job, or None if the job does not have a Qobj.

        Raises:
            IBMQJobApiError: if there was some unexpected failure in the server.
        """
        if not self.kind:
            return None

        # pylint: disable=access-member-before-definition,attribute-defined-outside-init
        if not self._qobj:  # type: ignore[has-type]
            self._wait_for_completion()
            with api_to_job_error():
                qobj = self._api.job_download_qobj(
                    self.job_id(), self._use_object_storage)
                self._qobj = Qobj.from_dict(qobj)

        return self._qobj

    def properties(self) -> Optional[BackendProperties]:
        """Return the backend properties for this job.

        Returns:
            the backend properties used for this job, or None if
                properties are not available.

        Raises:
            IBMQJobApiError: if there was some unexpected failure in the server.
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
            Some IBMQ job results can be read only once. A second attempt to
            query the API for the job will fail, as the job is "consumed".

            The first call to this method in an ``IBMQJob`` instance will query
            the API and consume the job if it finished successfully (otherwise
            it will raise a ``JobError`` exception without consuming the job).
            Subsequent calls to that instance's method will also return the
            results, since they are cached. However, attempting to retrieve the
            results again in another instance or session might fail due to the
            job having been consumed.

            When `partial=True`, the result method returns a `Result` object
            containing partial results. If partial results are returned, precaution
            should be taken when accessing individual experiments, as doing so might
            cause an exception. Verifying whether some experiments of a job failed can
            be done by checking the boolean attribute `Result.success`.

            For example:
                If there is a job with two experiments (where one fails), getting
                the counts of the unsuccessful experiment would raise an exception
                since there are no counts to return for it:
                i.e.
                    try:
                        counts = result.get_counts("failed_experiment")
                    except QiskitError:
                        print("Experiment failed!")

        Args:
           timeout: number of seconds to wait for job.
           wait: time in seconds between queries to IBM Q server. Default: 5.
           partial: if true attempts to return partial results for the job. Default: False.
           refresh: if true, query the API for the result again.
               Otherwise return the cached value. Default: False.

        Returns:
            Result object.

        Raises:
            IBMQJobInvalidStateError: if the job was cancelled.
            IBMQJobFailureError: If the job failed.
            IBMQJobApiError: If there was some unexpected failure in the server.
        """
        # pylint: disable=arguments-differ
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init

        if not self._wait_for_completion(timeout=timeout, wait=wait,
                                         required_status=(JobStatus.DONE,)):
            if self._status is JobStatus.CANCELLED:
                raise IBMQJobInvalidStateError('Unable to retrieve job result. Job was cancelled.')

            if self._status is JobStatus.ERROR and not partial:
                raise IBMQJobFailureError('Unable to retrieve job result. Job has failed. '
                                          'Use job.error_message() to get more details.')

        return self._retrieve_result(refresh=refresh)

    def cancel(self) -> bool:
        """Attempt to cancel a job.

        Returns:
            True if job can be cancelled, else False. Note this operation
            might not be possible depending on the environment.

        Raises:
            IBMQJobApiError: if there was some unexpected failure in the server.
        """
        try:
            response = self._api.job_cancel(self.job_id())
            self._cancelled = 'error' not in response and response.get('cancelled', False)
            return self._cancelled
        except ApiError as error:
            self._cancelled = False
            raise IBMQJobApiError('Error cancelling job: %s' % error)

    def status(self) -> JobStatus:
        """Query the API to update the status.

        Note:
            This method is not designed to be invoked repeatedly in a loop for
            an extended period of time. Doing so may cause an exception.
            Use `wait_for_final_state()` if you want to wait for the job to finish.

        Returns:
            The status of the job, once updated.

        Raises:
            IBMQJobApiError: if there was some unexpected failure in the server.
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
            True if job status is done, else false.
        """
        return self._is_job_status(JobStatus.DONE)

    def running(self) -> bool:
        """Return whether the job is actively running.

        Returns:
            True if job status is running, else false.
        """
        return self._is_job_status(JobStatus.RUNNING)

    def cancelled(self) -> bool:
        """Return whether the job has been cancelled.

        Returns:
            True if job status is cancelled, else false.
        """
        return self._is_job_status(JobStatus.CANCELLED)

    def _is_job_status(self, job_status: JobStatus) -> bool:
        """Return whether the current job status matches the desired one.

        Args:
            job_status: the job status to check against.

        Returns:
            True if the current job status matches the desired one, else false.
        """
        return self.status() == job_status

    def error_message(self) -> Optional[str]:
        """Provide details about the reason of failure.

        Note:
            Some IBMQ job results can be read only once. A second attempt to
            query the API for the job will fail, as the job is "consumed".

            The first call to this method in an ``IBMQJob`` instance will query
            the API and consume the job if it failed at some point (otherwise
            it will return ``None``). Subsequent calls to that instance's method
            will also return the failure details, since they are cached.
            However, attempting to retrieve the error details again in another
            instance or session might fail due to the job having been consumed.

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
        """Return the position in the server queue for the provider.

        Note: The position returned is within the scope of the account provider
            and may differ from the global queue position for the device.

        Args:
            refresh: if True, query the API and return the latest value.
                Otherwise return the cached value. Default: False.

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
            end time, and dynamic priorities for the hub/group/project.

        Note:
            Even if the job is queued, some of its queue information may not
                be immediately available.

        Returns:
            An QueueInfo instance that contains queue information for
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
        """Return creation date.

        Returns:
            Job creation date.
        """
        return self._creation_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    def job_id(self) -> str:
        """Return the job ID assigned by the API.

        Returns:
            the job ID.
        """
        return self._job_id

    def name(self) -> Optional[str]:
        """Return the name assigned to this job.

        Returns:
            the job name or ``None`` if no name was assigned to the job.
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

        Returns:
            a dictionary containing the date and time information on each
                step of the job processing. The keys of the dictionary are the
                names of the steps, and the values are the date and time
                information. ``None`` is returned if the information is not
                yet available.
        """
        if not self._time_per_step or self._status not in JOB_FINAL_STATES:
            self.refresh()
        return self._time_per_step

    def submit(self) -> None:
        """Submit job to IBM-Q.

        Note:
            This function is deprecated, please use ``IBMQBackend.run()`` to
                submit a job.

        Events:
            The job has started.

        Raises:
            IBMQJobApiError: if there was some unexpected failure in the server.
            IBMQJobInvalidStateError: If the job has already been submitted.
        """
        if self.job_id() is not None:
            raise IBMQJobInvalidStateError("We have already submitted the job!")

        warnings.warn("job.submit() is deprecated. Please use "
                      "IBMQBackend.run() to submit a job.", DeprecationWarning, stacklevel=2)

    def refresh(self) -> None:
        """Obtain the latest job information from the API."""
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
            raise IBMQJobApiError("Unexpected return value received from the server.") from ex
        finally:
            JobResponseSchema.model_cls = saved_model_cls

    def to_dict(self) -> None:
        """Serialize the model into a Python dict of simple types."""
        warnings.warn("IBMQJob.to_dict() is not supported and may not work properly.",
                      stacklevel=2)
        return BaseModel.to_dict(self)

    def wait_for_final_state(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            callback: Callable = None
    ) -> None:
        """Wait until the job progresses to a final state such as DONE or ERROR.

        Args:
            timeout: seconds to wait for the job. If ``None``, wait indefinitely. Default: None.
            wait: seconds to wait between queries. Default: 5.
            callback: callback function invoked after each querying iteration. Default: None.
                The following positional arguments are provided to the callback function:
                    * job_id: job ID
                    * job_status: status of the job from the last query
                    * job: this IBMQJob instance
                In addition, the following keyword arguments are also provided:
                    * queue_info: A ``QueueInfo`` instance with job queue information,
                        or ``None`` if queue information is unknown or not applicable.
                        You can use the ``to_dict()`` method to convert the ``QueueInfo``
                        instance to a dictionary, if desired.

        Raises:
            IBMQJobTimeoutError: if the job does not reach a final state before the
                specified timeout.
        """
        exit_event = Event()
        status_deque = deque(maxlen=1)  # type: deque
        future = None
        if callback:
            future = self._executor.submit(self._status_callback,
                                           status_deque=status_deque,
                                           exit_event=exit_event,
                                           callback=callback,
                                           wait=wait)
        try:
            self._wait_for_completion(timeout=timeout, wait=wait, status_deque=status_deque)
        finally:
            if future:
                exit_event.set()
                future.result()

    def _wait_for_completion(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            required_status: Tuple[JobStatus] = JOB_FINAL_STATES,
            status_deque: Optional[deque] = None
    ) -> bool:
        """Wait until the job progress to a final state such as DONE or ERROR.

        Args:
            timeout: seconds to wait for job. If None, wait indefinitely. Default: None.
            wait: seconds between queries. Default: 5.
            required_status: the final job status required. Default: ``JOB_FINAL_STATES``.
            status_deque: deque used to share the latest status. Default: None.

        Returns:
            True if the final job status matches one of the required states.

        Raises:
            IBMQJobTimeoutError: if the job does not return results before a
                specified timeout.
        """
        if self._status in JOB_FINAL_STATES:
            return self._status in required_status

        with api_to_job_error():
            try:
                status_response = self._api.job_final_status(
                    self.job_id(), timeout=timeout, wait=wait, status_deque=status_deque)
            except UserTimeoutExceededError:
                raise IBMQJobTimeoutError(
                    'Timeout while waiting for job {}'.format(self._job_id))
        self._status, self._queue_info = self._get_status_position(
            ApiJobStatus(status_response['status']), status_response.get('infoQueue', None))

        # Get all job attributes if the job is done.
        if self._status in JOB_FINAL_STATES:
            self.refresh()

        return self._status in required_status

    def _retrieve_result(self, refresh: bool = False) -> Result:
        """Retrieve the job result response.

        Args:
            refresh: if true, query the API for the result again.
               Otherwise return the cached value. Default: False.

        Returns:
            The job result.

        Raises:
            IBMQJobApiError: If there was some unexpected failure in the server.
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
                    raise IBMQJobFailureError('Unable to retrieve job result. Job has failed. '
                                              'Use job.error_message() to get more details.')
                if not self.kind:
                    raise IBMQJobInvalidStateError('Job result is in an unsupported format.')
                raise IBMQJobApiError(str(err))
            finally:
                # In case partial results are returned or job failure, an error message is cached.
                if result_response:
                    self._check_for_error_message(result_response)

        if self._status is JobStatus.ERROR and not self._result.results:
            raise IBMQJobFailureError('Unable to retrieve job result. Job has failed. '
                                      'Use job.error_message() to get more details.')

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
            IBMQJobApiError: If there was some unexpected failure in the server.
        """
        try:
            return "{}. Error code: {}.".format(error['message'], error['code'])
        except KeyError:
            raise IBMQJobApiError('Failed to get job error message. Invalid error data received: {}'
                                  .format(error))

    def _status_callback(
            self,
            status_deque: deque,
            exit_event: Event,
            callback: Callable,
            wait: float
    ) -> None:
        """Invoke the callback function with the latest job status.

        Args:
            status_deque: Deque containing the latest status.
            exit_event: Event used to notify this thread to quit.
            callback: Callback function to invoke.
            wait: Time between each callback function call.
        """
        while not exit_event.is_set():
            exit_event.wait(wait)

            try:
                status_response = status_deque.pop()
            except IndexError:
                continue

            try:
                status, queue_info = self._get_status_position(
                    ApiJobStatus(status_response['status']), status_response.get('infoQueue', None))
            except IBMQJobApiError as ex:
                logger.warning("Unexpected error when getting job status: %s", ex)
                continue

            callback(self.job_id(), status, self, queue_info=queue_info)

    def _get_status_position(
            self,
            api_status: ApiJobStatus,
            api_info_queue: Optional[Dict] = None
    ) -> Tuple[JobStatus, Optional[QueueInfo]]:
        """Return the corresponding job status for the input API job status.

        Args:
            api_status: API job status
            api_info_queue: job queue information from the API response.

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
            raise IBMQJobApiError("Unexpected return value received from the server.") from ex

        if status is not JobStatus.QUEUED:
            queue_info = None

        return status, queue_info
