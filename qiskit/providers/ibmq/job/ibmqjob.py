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

"""IBMQJob module

This module is used for creating a job objects for the IBM Q Experience.
"""

import logging
from typing import Dict, Optional, Tuple, Any
import warnings

from marshmallow import ValidationError

from qiskit.providers import (BaseJob,  # type: ignore[attr-defined]
                              JobTimeoutError, BaseBackend)
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import Qobj
from qiskit.result import Result
from qiskit.validation import BaseModel, ModelValidationError, bind_schema

from ..apiconstants import ApiJobStatus, ApiJobKind
from ..api.clients import AccountClient
from ..api.exceptions import ApiError, UserTimeoutExceededError
from ..job.exceptions import (IBMQJobApiError, IBMQJobFailureError,
                              IBMQJobInvalidStateError)
from .schema import JobResponseSchema
from .utils import (build_error_report, is_job_queued,
                    api_status_to_job_status, api_to_job_error)

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

    def __init__(self,
                 _backend: BaseBackend,
                 api: AccountClient,
                 _job_id: str,
                 _creation_date: str,
                 kind: ApiJobKind,
                 _status: ApiJobStatus,
                 **kwargs: Any) -> None:
        """IBMQJob init function.

        Args:
            _backend: the backend instance used to run this job.
            api: object for connecting to the API.
            _job_id: job ID of this job.
            _creation_date: job creation date.
            kind: job kind.
            _status: job status.
            kwargs: additional job attributes, that will be added as
                instance members.
        """
        # pylint: disable=redefined-builtin
        BaseModel.__init__(self, _backend=_backend, _job_id=_job_id,
                           _creation_date=_creation_date, kind=kind,
                           _status=_status, **kwargs)
        BaseJob.__init__(self, self.backend(), self.job_id())

        # Model attributes.
        self._api = api
        self._use_object_storage = (self.kind == ApiJobKind.QOBJECT_STORAGE)
        self._queue_position = None
        self._update_status_position(_status, kwargs.pop('infoQueue', None))

        # Properties used for caching.
        self._cancelled = False
        self._result_response = None  # type: Dict[str, Any]
        self._job_error_msg = self._error.message if self._error else None

    def qobj(self) -> Qobj:
        """Return the Qobj for this job.

        Note that this method might involve querying the API for results if the
        Job has been created in a previous Qiskit session.

        Returns:
            the Qobj for this job.

        Raises:
            IBMQJobApiError: if there was some unexpected failure in the server.
        """
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
            partial: Optional[bool] = False
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

        Args:
           timeout: number of seconds to wait for job
           wait: time between queries to IBM Q server
           partial: if true attempts to return partial results for the job.

        Returns:
            Result object

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

            if self._status is JobStatus.ERROR and partial:
                self._result = self._retrieve_partial_result()
                return self._result

            # Handle the rest of the exceptions as unexpected.
            raise IBMQJobFailureError('Unable to retrieve job result. Job has failed. '
                                      'Use job.error_message() to get more details.')

        if not self._result:  # type: ignore[has-type]
            with api_to_job_error():
                result_response = self._api.job_result(self.job_id(), self._use_object_storage)
                self._result = Result.from_dict(result_response)

        return self._result

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
            self._cancelled = 'error' not in response
            return self._cancelled
        except ApiError as error:
            self._cancelled = False
            raise IBMQJobApiError('Error cancelling job: %s' % error)

    def status(self) -> JobStatus:
        """Query the API to update the status.

        Returns:
            The status of the job, once updated.

        Raises:
            IBMQJobApiError: if there was some unexpected failure in the server.
        """
        if self._status in JOB_FINAL_STATES:
            return self._status

        with api_to_job_error():
            api_response = self._api.job_status(self.job_id())
            self._update_status_position(ApiJobStatus(api_response['status']),
                                         api_response.get('infoQueue', None))

        # Get all job attributes if the job is done.
        if self._status in JOB_FINAL_STATES:
            self.refresh()

        return self._status

    def _update_status_position(self, status: ApiJobStatus, info_queue: Optional[Dict]) -> None:
        """Update the job status and potentially queue position from an API response.

        Args:
            status: job status from the API response.
            info_queue: job queue information from the API response.
        """
        self._status = api_status_to_job_status(status)
        if status is ApiJobStatus.RUNNING:
            queued, self._queue_position = is_job_queued(info_queue)  # type: ignore[assignment]
            if queued:
                self._status = JobStatus.QUEUED

        if self._status is not JobStatus.QUEUED:
            self._queue_position = None

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

        if self._error:
            self._job_error_msg = self._error.message

        if not self._job_error_msg:
            # Attempt to retrieve partial results.
            self._result = self._retrieve_partial_result()

            # Since an error occurred, _result must be `None`. Check the response for errors.
            result_response = self._result_response
            if result_response and result_response['results']:
                # If individual errors given
                self._job_error_msg = build_error_report(result_response['results'])
            elif 'error' in result_response:
                self._job_error_msg = result_response['error']['message']
            else:
                # No error message given
                self._job_error_msg = "Unknown error."

        return self._job_error_msg

    def queue_position(self, refresh: bool = False) -> Optional[int]:
        """Return the position in the server queue.

        Args:
            refresh (bool): if True, query the API and return the latest value.
                Otherwise return the cached value.

        Returns:
            Position in the queue or ``None`` if position is unknown or not applicable.
        """
        if refresh:
            # Get latest position
            self.status()
        return self._queue_position

    def creation_date(self) -> str:
        """Return creation date.

        Returns:
            Job creation date.
        """
        return self._creation_date

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
            self._update_status_position(data.pop('_status'),
                                         data.pop('infoQueue', None))
        except ValidationError as ex:
            raise IBMQJobApiError("Unexpected return value received from the server.") from ex
        finally:
            JobResponseSchema.model_cls = saved_model_cls

    def _wait_for_completion(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            required_status: Tuple[JobStatus] = JOB_FINAL_STATES
    ) -> bool:
        """Wait until the job progress to a final state such as DONE or ERROR.

        Args:
            timeout: seconds to wait for job. If None, wait indefinitely.
            wait: seconds between queries.
            required_status: the final job status required.

        Returns:
            True if the final job status matches one of the required states.

        Raises:
            JobTimeoutError: if the job does not return results before a
                specified timeout.
        """
        if self._status in JOB_FINAL_STATES:
            return self._status in required_status

        with api_to_job_error():
            try:
                status_response = self._api.job_final_status(
                    self.job_id(), timeout=timeout, wait=wait)
            except UserTimeoutExceededError:
                raise JobTimeoutError(
                    'Timeout while waiting for job {}'.format(self._job_id))
        self._update_status_position(ApiJobStatus(status_response['status']),
                                     status_response.get('infoQueue', None))
        # Get all job attributes if the job is done.
        if self._status in JOB_FINAL_STATES:
            self.refresh()

        return self._status in required_status

    def _retrieve_partial_result(self) -> Optional[Result]:
        """Attempt to retrieve partial results for a job.

        Returns:
            The partial results for a job, or ``None`` if schema validation fails.
        """
        if not self._result and not self._result_response:  # type: ignore[misc]
            # No results, nor partial results, have been attained for this job yet.
            with api_to_job_error():
                # Set partial results, in case validation fails they are cached.
                self._result_response = self._api.job_result(self.job_id(),
                                                             self._use_object_storage)

            try:
                return Result.from_dict(self._result_response)
            except ModelValidationError:
                pass

        # Returned cached result.
        return self._result
