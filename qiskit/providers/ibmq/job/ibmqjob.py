# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
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
import pprint
import time
from concurrent import futures
from typing import Dict, Union, Optional

from qiskit.providers import BaseJob, JobError, JobTimeoutError, BaseBackend
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import Qobj, validate_qobj_against_schema
from qiskit.result import Result
from qiskit.tools.events.pubsub import Publisher
from qiskit.validation.exceptions import ModelValidationError

from ..api import ApiError, IBMQConnector
from ..apiconstants import ApiJobStatus
from ..api_v2.clients import BaseClient, AccountClient
from ..api_v2.rest.schemas.job import JobModel

from .utils import (current_utc_time, build_error_report, is_job_queued,
                    api_status_to_job_status)

logger = logging.getLogger(__name__)


class IBMQJob(JobModel, BaseJob):
    """Representation of a job that will be execute on a IBMQ backend.

    Represent the jobs that will be executed on IBM-Q simulators and real
    devices. Jobs are intended to be created calling ``run()`` on a particular
    backend.

    Creating a ``Job`` instance does not imply running it. You need to do it in
    separate steps::

        job = IBMQJob(...)
        job.submit() # It won't block.

    An error while submitting a job will cause the next call to ``status()`` to
    raise. If submitting the job successes, you can inspect the job's status by
    using ``status()``. Status can be one of ``JobStatus`` members::

        from qiskit.backends.jobstatus import JobStatus

        job = IBMQJob(...)
        job.submit()

        try:
            job_status = job.status() # It won't block. It will query the backend API.
            if job_status is JobStatus.RUNNING:
                print('The job is still running')

        except JobError as ex:
            print("Something wrong happened!: {}".format(ex))

    A call to ``status()`` can raise if something happens at the API level that
    prevents Qiskit from determining the status of the job. An example of this
    is a temporary connection lose or a network failure.

    The ``submit()`` and ``status()`` methods are examples of non-blocking API.
    ``Job`` instances also have `id()` and ``result()`` methods which will
    block::

        job = IBMQJob(...)
        job.submit()

        try:
            job_id = job.id() # It will block until completing submission.
            print('The job {} was successfully submitted'.format(job_id))

            job_result = job.result() # It will block until finishing.
            print('The job finished with result {}'.format(job_result))

        except JobError as ex:
            print("Something wrong happened!: {}".format(ex))

    Both methods can raise if something ath the API level happens that prevent
    Qiskit from determining the status of the job.

    Note:
        When querying the API for getting the status, two kinds of errors are
        possible. The most severe is the one preventing Qiskit from getting a
        response from the backend. This can be caused by a network failure or a
        temporary system break. In these cases, calling ``status()`` will raise.

        If Qiskit successfully retrieves the status of a job, it could be it
        finished with errors. In that case, ``status()`` will simply return
        ``JobStatus.ERROR`` and you can call ``error_message()`` to get more
        info.

    Attributes:
        _executor (futures.Executor): executor to handle asynchronous jobs
    """
    _executor = futures.ThreadPoolExecutor()

    def __init__(self,
                 backend: BaseBackend,
                 job_id: Optional[str],
                 api: Union[IBMQConnector, AccountClient],
                 qobj: Optional[Qobj] = None,
                 **kwargs) -> None:
        """IBMQJob init function.

        We can instantiate jobs from two sources: A QObj, and an already submitted job returned by
        the API servers.

        Args:
            backend (BaseBackend): The backend instance used to run this job.
            job_id (str or None): The job ID of an already submitted job.
                Pass `None` if you are creating a new job.
            api (IBMQConnector or BaseClient): object for connecting to the API.
            qobj (Qobj): The Quantum Object. See notes below

        Notes:
            It is mandatory to pass either ``qobj`` or ``job_id``. Passing a ``qobj``
            will ignore ``job_id`` and will create an instance to be submitted to the
            API server for job creation. Passing only a `job_id` will create an instance
            representing an already-created job retrieved from the API server.
        """
        # pylint: disable=unused-argument

        BaseJob.__init__(self, backend, job_id)

        # Properties common to all Jobs.
        self._api = api
        self._backend = backend
        self._future = None
        self._future_captured_exception = None

        # Properties used for caching.
        self._cancelled = False
        self._api_error_msg = None
        self._result = None
        self._queue_position = None
        self._qobj_payload = {}

        if qobj:
            self._qobj_raw = qobj
            self._status = JobStatus.INITIALIZING
            self._creation_date = current_utc_time()
        else:
            kwargs['id'] = job_id
            self._init_job_model(**kwargs)
            # In case of not providing a `qobj`, it is assumed the job already
            # exists in the API (with `job_id`).
            self._qobj_raw = None

    def qobj(self) -> Qobj:
        """Return the Qobj submitted for this job.

        Note that this method might involve querying the API for results if the
        Job has been created in a previous Qiskit session.

        Returns:
            Qobj: the Qobj submitted for this job.
        """
        if not self._qobj_payload:
            # Populate self._qobj_payload by retrieving the results.
            self._wait_for_completion()

            try:
                if isinstance(self._api, AccountClient):
                    self._qobj_payload = self._api.job_download_qobj(self.job_id())
                else:
                    self._qobj_payload = self._api.get_job(self._job_id)
            except ApiError as api_err:
                raise JobError(str(api_err))

        return Qobj.from_dict(self._qobj_payload)

    def properties(self) -> Optional[BackendProperties]:
        """Return the backend properties for this job.

        The properties might not be available if the job hasn't completed,
        in which case None is returned.

        Returns:
            BackendProperties: the backend properties used for this job, or None if
                properties are not available.
        """
        self._wait_for_submission()

        properties = self._api.job_properties(job_id=self.job_id())

        # Backend properties of a job might not be available if the job hasn't
        # completed. This is to ensure the properties returned are up to date.
        if not properties:
            return None
        return BackendProperties.from_dict(properties)

    # pylint: disable=arguments-differ
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
            JobError: if attempted to recover a result on a failed job.
        """
        self._wait_for_completion(timeout=timeout, wait=wait)

        if self._status is not JobStatus.DONE:
            raise JobError('Unable to retrieve job result. Job status '
                           'is {}'.format(str(self._status)))

        if not self._result:
            if isinstance(self._api, AccountClient):
                result_response = self._api.job_result(self.job_id())
                self._result = Result.from_dict(result_response)
            else:
                job_response = self._api.get_job(self._job_id)
                self._result = Result.from_dict(job_response['qObjectResult'])

        return self._result

    def cancel(self) -> bool:
        """Attempt to cancel a job.

        Note:
            This function waits for a job ID to become available if the job
            has been submitted but not yet queued.

        Returns:
            bool: True if job can be cancelled, else False. Note this operation
            might not be possible depending on the environment.

        Raises:
            JobError: if there was some unexpected failure in the server.
        """
        # Wait for the job ID to become available.
        self._wait_for_submission()

        try:
            response = self._api.cancel_job(self._job_id)
            self._cancelled = 'error' not in response
            return self._cancelled
        except ApiError as error:
            self._cancelled = False
            raise JobError('Error cancelling job: %s' % error.usr_msg)

    def status(self) -> JobStatus:
        """Query the API to update the status.

        Returns:
            qiskit.providers.JobStatus: The status of the job, once updated.

        Raises:
            JobError: if there was an exception during job submit
                          or the server sent an unknown answer.
        """
        # Implies self._job_id is None
        if self._future_captured_exception is not None:
            raise JobError(str(self._future_captured_exception))

        if self._job_id is None or self._status in JOB_FINAL_STATES:
            return self._status

        try:
            # TODO: See result values
            api_response = self._api.get_status_job(self._job_id)
            self._update_status(api_response)
        # pylint: disable=broad-except
        except Exception as err:
            raise JobError(str(err))

        return self._status

    def _update_status(self, api_response: Dict) -> None:
        """Update the job status from an API status.

        Args:
            api_response (dict): API response for a status query.

        Raises:
            JobError: if the API response could not be parsed.
        """
        # TODO we won't need to validate response once IBMQConnector goes away
        if 'status' not in api_response:
            raise JobError('Unrecognized answer from server: \n{}'.format(
                pprint.pformat(api_response)))

        try:
            api_status = ApiJobStatus(api_response['status'])
        except ValueError:
            raise JobError('Unrecognized status from server: {}'.format(
                api_response['status']))

        self._status = api_status_to_job_status(api_status)
        if api_status is ApiJobStatus.RUNNING:
            queued, self._queue_position = is_job_queued(api_response)
            if queued:
                self._status = JobStatus.QUEUED

    def error_message(self) -> Optional[str]:
        """Provide details about the reason of failure.

        Note:
            Some IBMQ job results can be read only once. A second attempt to
            query the API for the job will fail, as the job is "consumed".

            The first call to this method in an ``IBMQJob`` instance will query
            the API and consume the job if it errored at some point (otherwise
            it will return ``None``). Subsequent calls to that instance's method
            will also return the failure details, since they are cached.
            However, attempting to retrieve the error details again in another
            instance or session might fail due to the job having been consumed.

        Returns:
            str: An error report if the job errored or ``None`` otherwise.
        """
        self._wait_for_completion()
        if self.status() is not JobStatus.ERROR:
            return None

        if not self._api_error_msg:
            job_response = self._api.get_job(self._job_id)
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

    def job_id(self, timeout: float = 60) -> str:
        """Return the job ID assigned by the API.

        If the job ID is not set because the job is still initializing, this
        call will block until a job ID is available or the timeout is reached.

        Args:
            timeout (float): number of seconds to wait for the job ID.

        Returns:
            str: the job ID.
        """
        self._wait_for_submission(timeout)
        return self._job_id

    def submit(self, job_name: Optional[str] = None) -> None:
        """Submit job to IBM-Q.

        Args:
            job_name (str): custom name to be assigned to the job.

        Events:
            ibmq.job.start: The job has started.

        Raises:
            JobError: If we have already submitted the job.
            SchemaValidationError: If the job validation fails.
        """
        if self._future is not None or self._job_id is not None:
            raise JobError("We have already submitted the job!")

        # Validate the qobj
        validate_qobj_against_schema(self._qobj_raw)
        self._qobj_payload = self._qobj_raw.to_dict()

        self._future = self._executor.submit(self._submit_callback, job_name)
        Publisher().publish("ibmq.job.start", self)

    def _submit_callback(self, job_name: Optional[str] = None) -> None:
        """Submit qobj job to IBM-Q.

        Args:
            job_name (str): custom name to be assigned to the job.
        """
        backend_name = self.backend().name()

        try:
            kwargs = {}
            # TODO: job_name really should be a job attribute
            if isinstance(self._api, BaseClient):
                kwargs = {'job_name': job_name}
            submit_info = self._api.submit_job(
                backend_name=backend_name,
                qobj_dict=self._qobj_payload,
                **kwargs)

            # Error in the job after submission:
            # Transition to the `ERROR` final state.
            if 'error' in submit_info:
                self._status = JobStatus.ERROR
                self._api_error_msg = str(submit_info['error'])
                return

            # Submission success.
            self._init_job_model(**submit_info)
            self._status = JobStatus.QUEUED

        except Exception as err:  # pylint: disable=broad-except
            # Undefined error during submission:
            # Capture and keep it for raising it when calling status().

            import traceback
            traceback.print_exc()
            print(f">>>>>> err is {err}")

            self._future_captured_exception = err

    def _wait_for_completion(
            self, timeout: Optional[float] = None, wait: float = 5) -> None:
        """Wait until the job progress to a final state such as DONE or ERROR.

        Args:
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.
            wait (float): seconds between queries.

        Raises:
            JobTimeoutError: if the job does not return results before a
                specified timeout.
        """
        self._wait_for_submission(timeout)

        if self._status in JOB_FINAL_STATES:
            return

        if isinstance(self._api, AccountClient):
            status_response = self._api.job_final_status(
                self.job_id(), timeout=timeout, wait=wait)
            self._update_status(status_response)
        else:
            # Use traditional http requests
            self._wait_for_final_status(timeout, wait)

    def _wait_for_submission(self, timeout: float = 60) -> None:
        """Waits for the request to return a job ID"""
        if self._job_id is None:
            if self._future is None:
                raise JobError("You have to submit the job before doing a job related operation!")
            try:
                self._future.result(timeout=timeout)
            except TimeoutError as ex:
                raise JobTimeoutError(
                    "Timeout waiting for the job being submitted: {}".format(ex)
                )
            if self._future_captured_exception is not None:
                raise self._future_captured_exception
            if self._api_error_msg:
                raise JobError(self._api_error_msg)

    def _wait_for_final_status(self, timeout: Optional[float] = None, wait: float = 5):
        """Wait until the job progress to a final state.

        Args:
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.
            wait (float): seconds between queries.

        Raises:
            JobTimeoutError: if the job does not return results before a
                specified timeout.
        """
        start_time = time.time()
        while self.status() not in JOB_FINAL_STATES:
            elapsed_time = time.time() - start_time
            if timeout is not None and elapsed_time >= timeout:
                raise JobTimeoutError(
                    'Timeout while waiting for job {}'.format(self._job_id))

            logger.info('status = %s (%d seconds)', self._status, elapsed_time)
            time.sleep(wait)

    def _init_job_model(self, **kwargs):
        """Initialize the job model attributes

        Args:
            kwargs (dict): attribute dictionary
        """
        try:
            # from_dict() verifies data meets schema specification
            data = self.from_dict(kwargs)
            JobModel.__init__(self, **data)
        except ModelValidationError as err:
            raise JobError("Invalid job data format received from the server.") from err

        # Convert ApiJobStatus to JobStatus
        self._status = api_status_to_job_status(self._api_job_status)
