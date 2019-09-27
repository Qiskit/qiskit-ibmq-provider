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

This module is used for creating asynchronous job objects for the
IBM Q Experience.
"""

import logging
from typing import Dict, Optional, Tuple

from qiskit.providers import BaseJob, JobError, JobTimeoutError, BaseBackend
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import Qobj, validate_qobj_against_schema
from qiskit.result import Result
from qiskit.tools.events.pubsub import Publisher
from qiskit.validation.exceptions import ModelValidationError

from .models import JobModel
from .decorators import requires_job_id
from ..apiconstants import ApiJobStatus, ApiJobKind
from ..api.clients import AccountClient
from ..api.exceptions import ApiError, UserTimeoutExceededError
from .utils import (current_utc_time, build_error_report, is_job_queued,
                    api_status_to_job_status, api_to_job_error)

logger = logging.getLogger(__name__)


class IBMQJob(JobModel, BaseJob):
    """Representation of a job that will be execute on a IBMQ backend.

    Represent the jobs that will be executed on IBM-Q simulators and real
    devices. Jobs are intended to be created calling ``run()`` on a particular
    backend.

    Creating a ``Job`` instance does not imply running it. You need to do it in
    separate steps::

        job = IBMQJob(...)
        job.submit()

    The ``submit()`` method will not return until the server has acknowledged
    the reception of the job.

    If the job was successfully submitted, you can inspect the job's status by
    using ``status()``. Status can be one of ``JobStatus`` members::

        from qiskit.providers.jobstatus import JobStatus

        job = IBMQJob(...)

        try:
            job.submit()
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

        job = IBMQJob(...)

        try:
            job.submit()
            print('The job {} was successfully submitted'.format(job.job_id()))

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
                 backend_obj: Optional[BaseBackend],
                 job_id: Optional[str],
                 api: AccountClient,
                 qobj: Optional[Qobj] = None,
                 name: Optional[str] = None,
                 use_websockets: bool = True,
                 **kwargs: Dict) -> None:
        """IBMQJob init function.

        We can instantiate jobs from two sources: A QObj, and an already submitted job returned by
        the API servers.

        Args:
            backend_obj (BaseBackend): The backend instance used to run this job.
            job_id (str or None): The job ID of an already submitted job.
                Pass `None` if you are creating a new job.
            api (AccountClient): object for connecting to the API.
            qobj (Qobj): The Quantum Object. See notes below.
            name (str): name to assign to the job.
            use_websockets (bool): if `True`, signals that the Job will
                _attempt_ to use websockets when pooling for final status.
            kwargs (dict): additional job attributes.

        Notes:
            It is mandatory to pass either ``qobj`` or ``job_id``. Passing a ``qobj``
            will ignore ``job_id`` and will create an instance to be submitted to the
            API server for job creation. Passing only a `job_id` will create an instance
            representing an already-created job retrieved from the API server.
        """
        # pylint: disable=super-init-not-called

        # Properties common to all Jobs.
        self._api = api
        self._backend = backend_obj
        self.name = name

        # Properties used for caching.
        self._cancelled = False
        self._api_error_msg = None
        self._result = None
        self._queue_position = None
        self._qobj_dict = None

        # Properties used for deciding the underlying API features to use.
        self._use_websockets = use_websockets

        if qobj:
            # This is a new job.
            self._qobj = qobj
            self._status = JobStatus.INITIALIZING
            self._creation_date = current_utc_time()
            self._use_object_storage = getattr(
                backend_obj.configuration(), 'allow_object_storage', False)
        else:
            self._init_job_model(**kwargs)
            # In case of not providing a `qobj`, it is assumed the job already
            # exists in the API (with `job_id`).
            self._qobj = None

        BaseJob.__init__(self, backend_obj, job_id)

    def qobj(self) -> Qobj:
        """Return the Qobj for this job.

        Note that this method might involve querying the API for results if the
        Job has been created in a previous Qiskit session.

        Returns:
            Qobj: the Qobj for this job.

        Raises:
            JobError: if there was some unexpected failure in the server.
        """
        if not self._qobj_dict:
            # Populate self._qobj_dict by retrieving the results.
            # TODO Can qobj be retrieved if the job was cancelled?
            self._wait_for_completion()
            with api_to_job_error():
                self._qobj_dict = self._api.job_download_qobj(
                    self.job_id(), self._use_object_storage)

        return Qobj.from_dict(self._qobj_dict)

    @requires_job_id
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

    @requires_job_id
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

        if not self._wait_for_completion(timeout=timeout, wait=wait,
                                         required_status=(JobStatus.DONE,)):
            raise JobError('Unable to retrieve job result. Job status '
                           'is {}'.format(str(self._status)))

        if not self._result:
            with api_to_job_error():
                result_response = self._api.job_result(self.job_id(), self._use_object_storage)
                self._result = Result.from_dict(result_response)

        return self._result

    @requires_job_id
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
        if self._job_id is None or self._status in JOB_FINAL_STATES:
            return self._status

        with api_to_job_error():
            # TODO: See result values
            api_response = self._api.job_status(self.job_id())
            self._update_status_position(api_response)

        return self._status

    def _update_status_position(self, api_response: Dict) -> None:
        """Update the job status and potentially queue position from an API response.

        Args:
            api_response (dict): API response for a status query.
        """
        self._api_job_status = ApiJobStatus(api_response['status'])

        self._status = api_status_to_job_status(self._api_job_status)
        if self._api_job_status is ApiJobStatus.RUNNING:
            queued, self._queue_position = is_job_queued(api_response)
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

    def queue_position(self) -> int:
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

    def submit(self) -> None:
        """Submit job to IBM-Q.

        Note:
            This function waits for a job ID to become available.

        Events:
            ibmq.job.start: The job has started.

        Raises:
            JobError: If an error occurred during job submit.
            SchemaValidationError: If the job validation fails.
        """
        if self._job_id is not None:
            raise JobError("We have already submitted the job!")

        # Validate the qobj
        validate_qobj_against_schema(self._qobj)
        self._qobj_dict = self._qobj.to_dict()

        self._submit_job()
        Publisher().publish("ibmq.job.start", self)

    def _submit_job(self) -> None:
        """Submit qobj job to IBM-Q."""
        backend_name = self.backend().name()

        with api_to_job_error():
            submit_info = self._api.job_submit(
                backend_name=backend_name,
                qobj_dict=self._qobj_dict,
                use_object_storage=self._use_object_storage,
                job_name=self.name)

            # Error in the job after submission:
            # Transition to the `ERROR` final state.
            if 'error' in submit_info:
                self._status = JobStatus.ERROR
                raise JobError('Error submitting job: {}'.format(str(submit_info['error'])))

            # Submission success.
            self._init_job_model(**submit_info)
            self._status = JobStatus.QUEUED

    @requires_job_id
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
                    self.job_id(), timeout=timeout, wait=wait,
                    use_websockets=self._use_websockets)
            except UserTimeoutExceededError:
                raise JobTimeoutError(
                    'Timeout while waiting for job {}'.format(self._job_id))
        self._update_status_position(status_response)
        return self._status in required_status

    def _init_job_model(self, **kwargs: Dict) -> None:
        """Initialize the job model attributes.

        Args:
            kwargs (dict): attribute dictionary

        Raises:
            JobError: if invalid job data received from the server.
        """
        try:
            data = self.from_dict(kwargs)
            JobModel.__init__(self, **data)
        except ModelValidationError as err:
            raise JobError("Invalid job data format received.") from err

        # Convert ApiJobStatus to JobStatus
        self._status = api_status_to_job_status(self._api_job_status)
        self._use_object_storage = (self._job_kind == ApiJobKind.QOBJECT_STORAGE)
