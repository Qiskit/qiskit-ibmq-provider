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

import asyncio
import datetime
import logging
import pprint
import time
from concurrent import futures

from qiskit.providers import BaseJob, JobError, JobTimeoutError
from qiskit.providers.jobstatus import JOB_FINAL_STATES, JobStatus
from qiskit.providers.models import BackendProperties
from qiskit.qobj import Qobj, validate_qobj_against_schema
from qiskit.result import Result

from .api import ApiError
from .api.apijobstatus import ApiJobStatus
from .api.exceptions import WebsocketTimeoutError

logger = logging.getLogger(__name__)


class IBMQJob(BaseJob):
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

    def __init__(self, backend, job_id, api, qobj=None,
                 creation_date=None, api_status=None):
        """IBMQJob init function.

        We can instantiate jobs from two sources: A QObj, and an already submitted job returned by
        the API servers.

        Args:
            backend (BaseBackend): The backend instance used to run this job.
            job_id (str or None): The job ID of an already submitted job.
                Pass `None` if you are creating a new job.
            api (IBMQConnector): IBMQ connector.
            qobj (Qobj): The Quantum Object. See notes below
            creation_date (str): When the job was run.
            api_status (str): `status` field directly from the API response.

        Notes:
            It is mandatory to pass either ``qobj`` or ``job_id``. Passing a ``qobj``
            will ignore ``job_id`` and will create an instance to be submitted to the
            API server for job creation. Passing only a `job_id` will create an instance
            representing an already-created job retrieved from the API server.
        """
        # pylint: disable=unused-argument
        super().__init__(backend, job_id)

        if qobj:
            validate_qobj_against_schema(qobj)

            self._qobj_payload = qobj.as_dict()
        else:
            self._qobj_payload = {}

        self._future_captured_exception = None
        self._api = api
        self._backend = backend
        self._cancelled = False
        self._status = JobStatus.INITIALIZING
        # In case of not providing a `qobj`, it is assumed the job already
        # exists in the API (with `job_id`).
        if qobj is None:
            # Some API calls (`get_status_jobs`, `get_status_job`) provide
            # enough information to recreate the `Job`. If that is the case, try
            # to make use of that information during instantiation, as
            # `self.status()` involves an extra call to the API.
            if api_status == ApiJobStatus.VALIDATING.value:
                self._status = JobStatus.VALIDATING
            elif api_status == ApiJobStatus.COMPLETED.value:
                self._status = JobStatus.DONE
            elif api_status == ApiJobStatus.CANCELLED.value:
                self._status = JobStatus.CANCELLED
                self._cancelled = True
            else:
                self.status()
        self._queue_position = None

        def current_utc_time():
            """Gets the current time in UTC format"""
            datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()

        self._creation_date = creation_date or current_utc_time()
        self._future = None
        self._api_error_msg = None
        self._result = None

    def qobj(self):
        """Return the Qobj submitted for this job.

        Note that this method might involve querying the API for results if the
        Job has been created in a previous Qiskit session.

        Returns:
            Qobj: the Qobj submitted for this job.
        """
        if not self._qobj_payload:
            # Populate self._qobj_payload by retrieving the results.
            self._wait_for_job()

        return Qobj.from_dict(self._qobj_payload)

    def properties(self):
        """Return the backend properties for this job.

        Returns:
            BackendProperties: the backend properties used for this job.
        """
        self._wait_for_submission()

        properties = self._api.job_properties(job_id=self.job_id())
        return BackendProperties.from_dict(properties)

    # pylint: disable=arguments-differ
    def result(self, timeout=None, wait=5):
        """Return the result of the job.

        Note:
            Some IBMQ job results can be read only once. A second attempt to
            query the API for the job will fail, as the job is "consumed".

            The first call to this method in an ``IBMQJob`` instance will query
            the API and consume the job if it finished successfully (otherwise
            it will raise a ``JobError`` exception without consumming the job).
            Subsequent calls to that instance's method will also return the
            results, since they are cached. However, attempting to retrieve the
            results again in another instance or session might fail due to the
            job having been consumed.

        Args:
           timeout (float): number of seconds to wait for job
           wait (int): time between queries to IBM Q server

        Returns:
            qiskit.Result: Result object

        Raises:
            JobError: if attempted to recover a result on a failed job.
        """
        self._wait_for_completion(timeout=timeout, wait=wait)

        status = self.status()
        if status is not JobStatus.DONE:
            raise JobError('Invalid job state. The job should be DONE but '
                           'it is {}'.format(str(status)))

        if not self._result:
            job_response = self._get_job()
            self._result = Result.from_dict(job_response['qObjectResult'])

        return self._result

    def cancel(self):
        """Attempt to cancel a job.

        Returns:
            bool: True if job can be cancelled, else False. Note this operation
            might not be possible depending on the environment.

        Raises:
            JobError: if there was some unexpected failure in the server.
        """
        try:
            response = self._api.cancel_job(self._job_id)
            self._cancelled = 'error' not in response
            return self._cancelled
        except ApiError as error:
            self._cancelled = False
            raise JobError('Error cancelling job: %s' % error.usr_msg)

    def status(self):
        """Query the API to update the status.

        Returns:
            qiskit.providers.JobStatus: The status of the job, once updated.

        Raises:
            JobError: if there was an exception in the future being executed
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

    def _update_status(self, api_response):
        """Update the job status from an API status.

        Args:
            api_response (dict): API response for a status query.

        Raises:
            JobError: if the API response could not be parsed.
        """
        if 'status' not in api_response:
            raise JobError('Unrecognized answer from server: \n{}'.format(
                pprint.pformat(api_response)))

        try:
            api_status = ApiJobStatus(api_response['status'])
        except ValueError:
            raise JobError('Unrecognized status from server: {}'.format(
                api_response['status']))

        if api_status is ApiJobStatus.VALIDATING:
            self._status = JobStatus.VALIDATING

        elif api_status is ApiJobStatus.RUNNING:
            self._status = JobStatus.RUNNING
            queued, self._queue_position = _is_job_queued(api_response)
            if queued:
                self._status = JobStatus.QUEUED

        elif api_status is ApiJobStatus.COMPLETED:
            self._status = JobStatus.DONE

        elif api_status is ApiJobStatus.CANCELLED:
            self._status = JobStatus.CANCELLED
            self._cancelled = True

        elif api_status in (ApiJobStatus.ERROR_CREATING_JOB,
                            ApiJobStatus.ERROR_VALIDATING_JOB,
                            ApiJobStatus.ERROR_RUNNING_JOB):
            self._status = JobStatus.ERROR

    def error_message(self):
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
            job_response = self._get_job()
            results = job_response['qObjectResult']['results']
            self._api_error_msg = _build_error_report(results)

        return self._api_error_msg

    def queue_position(self):
        """Return the position in the server queue.

        Returns:
            Number: Position in the queue.
        """
        return self._queue_position

    def creation_date(self):
        """Return creation date."""
        return self._creation_date

    def job_id(self):
        """Return backend determined id.

        If the Id is not set because the job is already initializing, this call
        will block until we have an Id.
        """
        self._wait_for_submission()
        return self._job_id

    def submit(self):
        """Submit job to IBM-Q.

        Raises:
            JobError: If we have already submitted the job.
        """
        # TODO: Validation against the schema should be done here and not
        # during initialization. Once done, we should document that the method
        # can raise QobjValidationError.
        if self._future is not None or self._job_id is not None:
            raise JobError("We have already submitted the job!")
        self._future = self._executor.submit(self._submit_callback)

    def _submit_callback(self):
        """Submit qobj job to IBM-Q.

        Returns:
            dict: A dictionary with the response of the submitted job
        """
        backend_name = self.backend().name()

        try:
            submit_info = self._api.run_job(self._qobj_payload, backend_name=backend_name)
        # pylint: disable=broad-except
        except Exception as err:
            # Undefined error during submission:
            # Capture and keep it for raising it when calling status().
            self._future_captured_exception = err
            return None

        # Error in the job after submission:
        # Transition to the `ERROR` final state.
        if 'error' in submit_info:
            self._status = JobStatus.ERROR
            self._api_error_msg = str(submit_info['error'])
            return submit_info

        # Submission success.
        self._creation_date = submit_info.get('creationDate')
        self._status = JobStatus.QUEUED
        self._job_id = submit_info.get('id')
        return submit_info

    def _wait_for_job(self, timeout=None, wait=5):
        """Blocks until the job is complete and returns the job content from the
        API, consuming it.

        Args:
            timeout (float): number of seconds to wait for job.
            wait (int): time between queries to IBM Q server.

        Return:
            dict: a dictionary with the contents of the job.

        Raises:
            JobError: if there is an error while requesting the results.
        """
        self._wait_for_completion(timeout, wait)

        try:
            job_response = self._get_job()
            if not self._qobj_payload:
                self._qobj_payload = job_response.get('qObject', {})
        except ApiError as api_err:
            raise JobError(str(api_err))

        return job_response

    def _get_job(self):
        """Query the API for retrieving the job complete state, consuming it.

        Returns:
            dict: a dictionary with the contents of the result.

        Raises:
            JobTimeoutError: if the job does not return results before a
                specified timeout.
            JobError: if something wrong happened in some of the server API
                calls.
        """
        if self._cancelled:
            raise JobError(
                'Job result impossible to retrieve. The job was cancelled.')

        return self._api.get_job(self._job_id)

    def _wait_for_completion(self, timeout=None, wait=5):
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

        # TODO: reenable during #61.
        # if 'websocket_url' in self._api.config:
        #     self._wait_for_final_status_websocket(timeout)
        # else:
        #     self._wait_for_final_status(timeout, wait)

        self._wait_for_final_status(timeout, wait)

    def _wait_for_submission(self, timeout=60):
        """Waits for the request to return a job ID"""
        if self._job_id is None:
            if self._future is None:
                raise JobError("You have to submit before asking for status or results!")
            try:
                submit_info = self._future.result(timeout=timeout)
                if self._future_captured_exception is not None:
                    raise self._future_captured_exception
            except TimeoutError as ex:
                raise JobTimeoutError(
                    "Timeout waiting for the job being submitted: {}".format(ex)
                )
            if 'error' in submit_info:
                self._status = JobStatus.ERROR
                self._api_error_msg = str(submit_info['error'])
                raise JobError(str(submit_info['error']))

    def _wait_for_final_status(self, timeout=None, wait=5):
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

    def _wait_for_final_status_websocket(self, timeout=None):
        """Wait until the job progress to a final state using websockets.

        Args:
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.

        Raises:
            JobTimeoutError: if the job does not return results before a
                specified timeout.
        """
        websocket_client = self._api.websocket_client()

        try:
            status_response = asyncio.get_event_loop().run_until_complete(
                websocket_client.get_job_status(self._job_id,
                                                timeout=timeout))
            self._update_status(status_response)
        except WebsocketTimeoutError:
            raise JobTimeoutError(
                'Timeout while waiting for job {}'.format(self._job_id))


def _is_job_queued(api_job_status_response):
    """Checks whether a job has been queued or not.

    Args:
        api_job_status_response (dict): status response of the job.

    Returns:
        Pair[boolean, int]: a pair indicating if the job is queued and in which
            position.
    """
    is_queued, position = False, 0
    if 'infoQueue' in api_job_status_response:
        if 'status' in api_job_status_response['infoQueue']:
            queue_status = api_job_status_response['infoQueue']['status']
            is_queued = queue_status == 'PENDING_IN_QUEUE'
        if 'position' in api_job_status_response['infoQueue']:
            position = api_job_status_response['infoQueue']['position']
    return is_queued, position


def _build_error_report(results):
    """Build an user-friendly error report for a failed job.

    Args:
        results (dict): result section of the job response.

    Returns:
        str: the error report.
    """
    error_list = []
    for index, result in enumerate(results):
        if not result['success']:
            error_list.append('Experiment {}: {}'.format(index, result['status']))

    error_report = 'The following experiments failed:\n{}'.format('\n'.join(error_list))
    return error_report
