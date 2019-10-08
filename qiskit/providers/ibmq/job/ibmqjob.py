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

from qiskit.providers import BaseJob, JobError, JobTimeoutError, BaseBackend
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import Qobj
from qiskit.result import Result
from qiskit.validation import BaseModel, bind_schema

from ..apiconstants import ApiJobStatus, ApiJobKind
from ..api.clients import AccountClient
from ..api.exceptions import ApiError, UserTimeoutExceededError
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

        except JobError as ex:
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

    Many of the ``IBMQJob`` methods can raise ``JobError`` if unexpected
    failures happened at the server level.

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
            _backend (BaseBackend): the backend instance used to run this job.
            api (AccountClient): object for connecting to the API.
            _job_id (str or None): job ID of this job.
            _creation_date (str): job creation date.
            kind (ApiJobKind): job kind.
            _status (ApiJobStatus): job status.
            kwargs (dict): additional job attributes, that will be added as
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
        self._api_error_msg = None

    def qobj(self) -> Qobj:
        """Return the Qobj for this job.

        Note that this method might involve querying the API for results if the
        Job has been created in a previous Qiskit session.

        Returns:
            Qobj: the Qobj for this job.

        Raises:
            JobError: if there was some unexpected failure in the server.
        """
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init
        if not self._qobj:
            self._wait_for_completion()
            with api_to_job_error():
                qobj = self._api.job_download_qobj(
                    self.job_id(), self._use_object_storage)
                self._qobj = Qobj.from_dict(qobj)

        return self._qobj

    def properties(self) -> Optional[BackendProperties]:
        """Return the backend properties for this job.

        The properties might not be available if the job hasn't completed,
        in which case None is returned.

        Returns:
            BackendProperties: the backend properties used for this job, or None if
                properties are not available.

        Raises:
            JobError: if there was some unexpected failure in the server.
        """
        with api_to_job_error():
            properties = self._api.job_properties(job_id=self.job_id())

        # Backend properties of a job might not be available if the job hasn't
        # completed. This is to ensure the properties returned are up to date.
        if not properties:
            return None
        return BackendProperties.from_dict(properties)

    def result(self, timeout: Optional[float] = None, wait: float = 5) -> Result:
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
           timeout (float): number of seconds to wait for job
           wait (float): time between queries to IBM Q server

        Returns:
            qiskit.Result: Result object

        Raises:
            JobError: if the job has not been submitted or has failed, or if
                there was some unexpected failure in the server.
        """
        # pylint: disable=arguments-differ
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init

        if not self._wait_for_completion(timeout=timeout, wait=wait,
                                         required_status=(JobStatus.DONE,)):
            raise JobError('Unable to retrieve job result. Job status '
                           'is {}'.format(str(self._status)))

        # TODO Can look for and reuse qObjectResult
        if not self._result:
            with api_to_job_error():
                result_response = self._api.job_result(self.job_id(), self._use_object_storage)
                self._result = Result.from_dict(result_response)

        return self._result

    def cancel(self) -> bool:
        """Attempt to cancel a job.

        Returns:
            bool: True if job can be cancelled, else False. Note this operation
            might not be possible depending on the environment.

        Raises:
            JobError: if the job has not been submitted or if there was
                some unexpected failure in the server.
        """
        try:
            response = self._api.job_cancel(self.job_id())
            self._cancelled = 'error' not in response
            return self._cancelled
        except ApiError as error:
            self._cancelled = False
            raise JobError('Error cancelling job: %s' % error)

    def status(self) -> JobStatus:
        """Query the API to update the status.

        Returns:
            qiskit.providers.JobStatus: The status of the job, once updated.

        Raises:
            JobError: if there was some unexpected failure in the server.
        """
        if self._status in JOB_FINAL_STATES:
            return self._status

        with api_to_job_error():
            # TODO: See result values
            api_response = self._api.job_status(self.job_id())
            self._update_status_position(ApiJobStatus(api_response['status']),
                                         api_response.get('infoQueue', None))

        return self._status

    def _update_status_position(self, status: ApiJobStatus, info_queue: Optional[Dict]) -> None:
        """Update the job status and potentially queue position from an API response.

        Args:
            status (ApiJobStatus): job status from the API response.
            info_queue (dict): job queue information from the API response.
        """
        self._status = api_status_to_job_status(status)
        if status is ApiJobStatus.RUNNING:
            queued, self._queue_position = is_job_queued(info_queue)
            if queued:
                self._status = JobStatus.QUEUED

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
            str: An error report if the job failed or ``None`` otherwise.
        """
        if self.job_id() is None or \
                not self._wait_for_completion(required_status=(JobStatus.ERROR,)):
            return None

        if not self._api_error_msg:
            job_response = self._api.job_get(self.job_id())
            if 'qObjectResult' in job_response:
                results = job_response['qObjectResult']['results']
                self._api_error_msg = build_error_report(results)
            elif 'qasms' in job_response:
                qasm_statuses = [qasm['status'] for qasm in job_response['qasms']]
                self._api_error_msg = 'Job resulted in the following QASM status(es): ' \
                                      '{}.'.format(', '.join(qasm_statuses))
            else:
                self._api_error_msg = job_response.get('status', 'An unknown error occurred.')

        return self._api_error_msg

    def queue_position(self) -> Optional[int]:
        """Return the position in the server queue.

        Returns:
            int: Position in the queue or ``None`` if position is unknown.
        """
        # Get latest position
        self.status()
        return self._queue_position

    def creation_date(self) -> str:
        """Return creation date.

        Returns:
            str: Job creation date.
        """
        return self._creation_date

    def job_id(self) -> str:
        """Return the job ID assigned by the API.

        Returns:
            str: the job ID.
        """
        return self._job_id

    def name(self) -> Optional[str]:
        """Return the name assigned to this job.

        Returns:
            str: the job name.
        """
        return self._name

    def time_per_step(self) -> Optional[Dict]:
        """Return the date and time information on each step of the job processing.

        Returns:
            dict: a dictionary containing the date and time information on each
                step of the job processing. The keys of the dictionary are the
                names of the steps, and the values are the date and time
                information. ``None`` is returned if the information is not
                yet available.
        """
        # TODO refresh job data
        return self._time_per_step

    def submit(self) -> None:
        """Submit job to IBM-Q.

        Note:
            This function waits for a job ID to become available.

        Events:
            ibmq.job.start: The job has started.

        Raises:
            JobError: If an error occurred during job submit.
        """
        if self.job_id() is not None:
            raise JobError("We have already submitted the job!")

        warnings.warn("Please use IBMQBackend.run() to submit a job.")

    def _wait_for_completion(
            self,
            timeout: Optional[float] = None,
            wait: float = 5,
            required_status: Tuple[JobStatus] = JOB_FINAL_STATES
    ) -> bool:
        """Wait until the job progress to a final state such as DONE or ERROR.

        Args:
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.
            wait (float): seconds between queries.
            required_status (tuple[JobStatus]): the final job status required.

        Returns:
            bool: True if the final job status matches one of the required states.

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
        return self._status in required_status
