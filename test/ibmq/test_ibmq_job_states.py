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

# pylint: disable=missing-docstring

"""IBMQJob states test-suite."""

import time
import copy
from contextlib import suppress
from unittest import mock

from qiskit.providers.ibmq.apiconstants import API_JOB_FINAL_STATES, ApiJobStatus
from qiskit.test.mock import FakeQobj
from qiskit.providers import JobTimeoutError
from qiskit.providers.ibmq.job.exceptions import IBMQJobApiError, IBMQJobInvalidStateError
from qiskit.providers.ibmq.api.exceptions import (ApiError, UserTimeoutExceededError,
                                                  ApiIBMQProtocolError)
from qiskit.providers.ibmq.exceptions import IBMQBackendError
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend

from ..jobtestcase import JobTestCase


MOCKED_ERROR_RESULT = {
    'qObjectResult': {
        'backend_name': 'fake_backend',
        'backend_version': '0.1.1',
        'qobj_id': '123',
        'job_id': '123',
        'success': False,
        'results': [
            {
                'status': 'DONE',
                'success': True,
                'shots': 1,
                'data': {}
            },
            {
                'status': 'Error 1',
                'success': False,
                'shots': 1,
                'data': {}
            },
            {
                'status': 'Error 2',
                'success': False,
                'shots': 1,
                'data': {}
            }
        ]
    }
}

VALID_QOBJ_RESPONSE = {
    'status': 'COMPLETED',
    'kind': 'q-object',
    'creationDate': '2019-01-01T12:57:15.052Z',
    'id': '0123456789',
    'qObjectResult': {
        'backend_name': 'ibmqx2',
        'backend_version': '1.1.1',
        'job_id': 'XC1323XG2',
        'qobj_id': 'Experiment1',
        'success': True,
        'status': 'COMPLETED',
        'results': [
            {
                'header': {
                    'name': 'Bell state',
                    'memory_slots': 2,
                    'creg_sizes': [['c', 2]],
                    'clbit_labels': [['c', 0], ['c', 1]],
                    'qubit_labels': [['q', 0], ['q', 1]]
                },
                'shots': 1024,
                'status': 'DONE',
                'success': True,
                'data': {
                    'counts': {
                        '0x0': 480, '0x3': 490, '0x1': 20, '0x2': 34
                    }
                }
            },
            {
                'header': {
                    'name': 'Bell state XY',
                    'memory_slots': 2,
                    'creg_sizes': [['c', 2]],
                    'clbit_labels': [['c', 0], ['c', 1]],
                    'qubit_labels': [['q', 0], ['q', 1]]
                },
                'shots': 1024,
                'status': 'DONE',
                'success': True,
                'data': {
                    'counts': {
                        '0x0': 29, '0x3': 15, '0x1': 510, '0x2': 480
                    }
                }
            }
        ]
    }
}


VALID_JOB_RESPONSE = {
    'job_id': 'TEST_ID',
    'kind': 'q-object',
    'status': 'CREATING',
    'creation_date': '2019-01-01T13:15:58.425972'
}


class TestIBMQJobStates(JobTestCase):
    """Test the states of an IBMQJob."""

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self._current_api = None
        self._current_qjob = None

    def test_unrecognized_status(self):
        """Test unrecognized job state."""
        job = self.run_with_api(UnknownStatusAPI())
        with self.assertRaises(IBMQJobApiError):
            self.wait_for_initialization(job)

    def test_done_status(self):
        """Test job status progresses to done."""
        job = self.run_with_api(QueuedAPI())

        self.assertFalse(job.done())
        self.wait_for_initialization(job)

        self._current_api.progress()
        self.assertFalse(job.done())

        self._current_api.progress()
        self.assertTrue(job.done())

    def test_running_status(self):
        """Test job status progresses to running."""
        job = self.run_with_api(ValidatingAPI())

        self.assertFalse(job.running())
        self.wait_for_initialization(job)

        self._current_api.progress()
        self.assertTrue(job.running())

    def test_cancelled_status(self):
        """Test job status is cancelled."""
        job = self.run_with_api(CancellableAPI())

        self.assertFalse(job.cancelled())
        self.wait_for_initialization(job)

        self._current_api.progress()
        self.assertTrue(job.cancelled())

    def test_validating_job(self):
        """Test job status is validating."""
        job = self.run_with_api(ValidatingAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.VALIDATING)

    def test_error_while_creating_job(self):
        """Test job failing during creation."""
        job = self.run_with_api(ErrorWhileCreatingAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.ERROR)

    def test_error_while_validating_job(self):
        """Test job failing during validation."""
        job = self.run_with_api(ErrorWhileValidatingAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.VALIDATING)

        self._current_api.progress()
        self.assertEqual(job.status(), JobStatus.ERROR)

    def test_status_flow_for_non_queued_job(self):
        """Test job status progressing to done without being queued."""
        job = self.run_with_api(NonQueuedAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.RUNNING)

        self._current_api.progress()
        self.assertEqual(job.status(), JobStatus.DONE)

    def test_status_flow_for_queued_job(self):
        """Test job status progressing from queued to done."""
        job = self.run_with_api(QueuedAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.QUEUED)

        self._current_api.progress()
        self.assertEqual(job.status(), JobStatus.RUNNING)

        self._current_api.progress()
        self.assertEqual(job.status(), JobStatus.DONE)

    def test_status_flow_for_cancellable_job(self):
        """Test job status going from running to cancelled."""
        job = self.run_with_api(CancellableAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.RUNNING)

        can_cancel = job.cancel()
        self.assertTrue(can_cancel)

        self._current_api.progress()
        self.assertEqual(job.status(), JobStatus.CANCELLED)

    def test_status_flow_for_non_cancellable_job(self):
        """Test job cannot be cancelled."""
        job = self.run_with_api(NonCancellableAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.RUNNING)

        can_cancel = job.cancel()
        self.assertFalse(can_cancel)

        self._current_api.progress()
        self.assertEqual(job.status(), JobStatus.RUNNING)

    def test_status_flow_for_errored_cancellation(self):
        """Test job cancel encounters an error."""
        job = self.run_with_api(ErroredCancellationAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.RUNNING)
        can_cancel = job.cancel()
        self.assertFalse(can_cancel)
        self.assertEqual(job.status(), JobStatus.RUNNING)

    def test_status_flow_for_unable_to_run_valid_qobj(self):
        """Test API error while running a job."""
        with self.assertRaises(IBMQBackendError):
            self.run_with_api(UnavailableRunAPI())

    def test_api_throws_temporarily_but_job_is_finished(self):
        """Test job finishes after encountering API error."""
        job = self.run_with_api(ThrowingNonJobRelatedErrorAPI(errors_before_success=2))

        # First time we query the server...
        with self.assertRaises(IBMQJobApiError):
            # The error happens inside wait_for_initialization, the first time
            # it calls to status() after INITIALIZING.
            self.wait_for_initialization(job)

        # Also an explicit second time...
        with self.assertRaises(IBMQJobApiError):
            job.status()

        # Now the API gets fixed and doesn't throw anymore.
        self.assertEqual(job.status(), JobStatus.DONE)

    def test_error_while_running_job(self):
        """Test job failed."""
        job = self.run_with_api(ErrorWhileRunningAPI())

        self.wait_for_initialization(job)
        self.assertEqual(job.status(), JobStatus.RUNNING)

        self._current_api.progress()
        self.assertEqual(job.status(), JobStatus.ERROR)
        self.assertIn('Error 1', job.error_message())
        self.assertIn('Error 2', job.error_message())

    def test_cancelled_result(self):
        """Test getting results for a cancelled job."""
        job = self.run_with_api(CancellableAPI())

        self.wait_for_initialization(job)
        job.cancel()
        self._current_api.progress()
        with self.assertRaises(IBMQJobInvalidStateError):
            _ = job.result()
            self.assertEqual(job.status(), JobStatus.CANCELLED)

    def test_errored_result(self):
        """Test getting results for a failed job."""
        job = self.run_with_api(ThrowingGetJobAPI())
        self.wait_for_initialization(job)
        with self.assertRaises(IBMQJobApiError):
            job.result()

    def test_completed_result(self):
        """Test getting results for a completed job."""
        job = self.run_with_api(NonQueuedAPI())

        self.wait_for_initialization(job)
        self._current_api.progress()
        self.assertEqual(job.result().success, True)
        self.assertEqual(job.status(), JobStatus.DONE)

    def test_block_on_result_waiting_until_completed(self):
        """Test waiting for job results."""
        from concurrent import futures

        job = self.run_with_api(NonQueuedAPI())
        with futures.ThreadPoolExecutor() as executor:
            executor.submit(_auto_progress_api, self._current_api)

        result = job.result()
        self.assertEqual(result.success, True)
        self.assertEqual(job.status(), JobStatus.DONE)

    def test_block_on_result_waiting_until_cancelled(self):
        """Test canceling job while waiting for results."""
        from concurrent.futures import ThreadPoolExecutor

        job = self.run_with_api(CancellableAPI())
        with ThreadPoolExecutor() as executor:
            executor.submit(_auto_progress_api, self._current_api)

        with self.assertRaises(IBMQJobInvalidStateError):
            job.result()

        self.assertEqual(job.status(), JobStatus.CANCELLED)

    def test_block_on_result_waiting_until_exception(self):
        """Test getting API error while waiting for job results."""
        from concurrent.futures import ThreadPoolExecutor
        job = self.run_with_api(ThrowingAPI())

        with ThreadPoolExecutor() as executor:
            executor.submit(_auto_progress_api, self._current_api)

        with self.assertRaises(IBMQJobApiError):
            job.result()

    def test_never_complete_result_with_timeout(self):
        """Test timing out while waiting for job results."""
        job = self.run_with_api(NonQueuedAPI())

        self.wait_for_initialization(job)
        with self.assertRaises(JobTimeoutError):
            job.result(timeout=0.2)

    def test_only_final_states_cause_detailed_request(self):
        """Test job status call does not provide detailed information."""
        # The state ERROR_CREATING_JOB is only handled when running the job,
        # and not while checking the status, so it is not tested.
        all_state_apis = {'COMPLETED': NonQueuedAPI,
                          'CANCELLED': CancellableAPI,
                          'ERROR_VALIDATING_JOB': ErrorWhileValidatingAPI,
                          'ERROR_RUNNING_JOB': ErrorWhileRunningAPI}

        for status, api in all_state_apis.items():
            with self.subTest(status=status):
                job = self.run_with_api(api())
                self.wait_for_initialization(job)

                with suppress(BaseFakeAPI.NoMoreStatesError):
                    self._current_api.progress()

                with mock.patch.object(self._current_api, 'job_get',
                                       wraps=self._current_api.job_get):
                    job.status()
                    if ApiJobStatus(status) in API_JOB_FINAL_STATES:
                        self.assertTrue(self._current_api.job_get.called)
                    else:
                        self.assertFalse(self._current_api.job_get.called)

    def test_no_kind_job(self):
        """Test a job without the kind field."""
        job = self.run_with_api(NoKindJobAPI())
        with self.assertRaises(IBMQJobInvalidStateError):
            job.result()
        self.assertIsNone(job.qobj())

    def test_transpiling_status(self):
        """Test transpiling job state."""
        job = self.run_with_api(TranspilingStatusAPI())
        time.sleep(0.2)
        self.assertEqual(job.status(), JobStatus.INITIALIZING)

    def run_with_api(self, api):
        """Creates a new ``IBMQJob`` running with the provided API object."""
        backend = IBMQBackend(mock.Mock(), mock.Mock(), mock.Mock(), api_client=api)
        self._current_api = api
        self._current_qjob = backend.run(qobj=FakeQobj())  # pylint: disable=no-value-for-parameter
        self._current_qjob.refresh = mock.Mock()
        return self._current_qjob


def _auto_progress_api(api, interval=0.2):
    """Progress a ``BaseFakeAPI`` instance every `interval` seconds until reaching
    the final state.
    """
    with suppress(BaseFakeAPI.NoMoreStatesError):
        while True:
            time.sleep(interval)
            api.progress()


class BaseFakeAPI:
    """Base class for faking the IBM Quantum Experience API."""

    class NoMoreStatesError(Exception):
        """Raised when it is not possible to progress more."""

    _job_status = []

    _can_cancel = False

    def __init__(self):
        """BaseFakeAPI constructor."""
        self._state = 0
        self.config = {'hub': None, 'group': None, 'project': None}
        if self._can_cancel:
            self.config.update({
                'hub': 'test-hub',
                'group': 'test-group',
                'project': 'test-project'
            })

    def job_get(self, job_id):
        """Return information about a job."""
        if not job_id:
            return {'status': 'Error', 'error': 'Job ID not specified'}
        return self._job_status[self._state]

    def job_status(self, job_id):
        """Return the status of a job."""
        summary_fields = ['status', 'error', 'info_queue']
        complete_response = self.job_get(job_id)
        try:
            ApiJobStatus(complete_response['status'])
        except ValueError:
            raise ApiIBMQProtocolError('Api Error')
        return {key: value for key, value in complete_response.items()
                if key in summary_fields}

    def job_submit(self, *_args, **_kwargs):
        """Submit the job."""
        time.sleep(0.2)
        return VALID_JOB_RESPONSE

    def job_cancel(self, job_id, *_args, **_kwargs):
        """Cancel the job."""
        if not job_id:
            return {'status': 'Error', 'error': 'Job ID not specified'}
        return {'cancelled': True} if self._can_cancel else {
            'error': 'testing fake API can not cancel'}

    def job_final_status(self, job_id, *_args, **_kwargs):
        """Wait for job to enter a final state."""
        start_time = time.time()
        status_response = self.job_status(job_id)
        while ApiJobStatus(status_response['status']) not in API_JOB_FINAL_STATES:
            elapsed_time = time.time() - start_time
            timeout = _kwargs.get('timeout', None)
            if timeout is not None and elapsed_time >= timeout:
                raise UserTimeoutExceededError(
                    'Timeout while waiting for job {}'.format(job_id))
            time.sleep(5)
            status_response = self.job_status(job_id)
        return status_response

    def job_result(self, job_id, *_args, **_kwargs):
        """Get job result."""
        return self.job_get(job_id)['qObjectResult']

    def progress(self):
        """Progress to the next job state."""
        if self._state == len(self._job_status) - 1:
            raise self.NoMoreStatesError()
        self._state += 1


class UnknownStatusAPI(BaseFakeAPI):
    """Class for emulating an API with unknown status codes."""

    _job_status = [
        {'status': 'UNKNOWN'}
    ]


class ValidatingAPI(BaseFakeAPI):
    """Class for emulating an API with job validation."""

    _job_status = [
        {'status': 'VALIDATING'},
        {'status': 'RUNNING'}
    ]


class ErrorWhileValidatingAPI(BaseFakeAPI):
    """Class for emulating an API processing an invalid job."""

    _job_status = [
        {'status': 'VALIDATING'},
        {'status': 'ERROR_VALIDATING_JOB', **MOCKED_ERROR_RESULT}
    ]


class NonQueuedAPI(BaseFakeAPI):
    """Class for emulating a successfully-completed non-queued API."""

    _job_status = [
        {'status': 'RUNNING'},
        VALID_QOBJ_RESPONSE
    ]


class ErrorWhileCreatingAPI(BaseFakeAPI):
    """Class emulating an API processing a job that errors while creating the job."""

    _job_status = [
        {'status': 'ERROR_CREATING_JOB', **MOCKED_ERROR_RESULT}
    ]


class ErrorWhileRunningAPI(BaseFakeAPI):
    """Class emulating an API processing a job that errors while running."""

    _job_status = [
        {'status': 'RUNNING'},
        {'status': 'ERROR_RUNNING_JOB', **MOCKED_ERROR_RESULT}
    ]


class QueuedAPI(BaseFakeAPI):
    """Class for emulating a successfully-completed queued API."""

    _job_status = [
        {'status': 'QUEUED'},
        {'status': 'RUNNING'},
        {'status': 'COMPLETED'}
    ]


class RejectingJobAPI(BaseFakeAPI):
    """Class for emulating an API unable of initializing."""

    def job_submit(self, *_args, **_kwargs):
        return {'error': 'invalid qobj'}


class UnavailableRunAPI(BaseFakeAPI):
    """Class for emulating an API throwing before even initializing."""

    def job_submit(self, *_args, **_kwargs):
        time.sleep(0.2)
        raise ApiError('Api Error')


class ThrowingAPI(BaseFakeAPI):
    """Class for emulating an API throwing in the middle of execution."""

    _job_status = [
        {'status': 'RUNNING'}
    ]

    def job_get(self, job_id):
        raise ApiError('Api Error')


class ThrowingNonJobRelatedErrorAPI(BaseFakeAPI):
    """Class for emulating an scenario where the job is done but the API
    fails some times for non job-related errors.
    """

    _job_status = [
        {'status': 'COMPLETED'}
    ]

    def __init__(self, errors_before_success=2):
        super().__init__()
        self._number_of_exceptions_to_throw = errors_before_success

    def job_get(self, job_id):
        if self._number_of_exceptions_to_throw != 0:
            self._number_of_exceptions_to_throw -= 1
            raise ApiError('Api Error')

        return super().job_get(job_id)


class ThrowingGetJobAPI(BaseFakeAPI):
    """Class for emulating an API throwing in the middle of execution. But not in
    ``job_status()``, just in ``job_get()``.
    """

    _job_status = [
        {'status': 'COMPLETED'}
    ]

    def job_status(self, job_id):
        return self._job_status[self._state]

    def job_get(self, job_id):
        raise ApiError('Unexpected error')


class CancellableAPI(BaseFakeAPI):
    """Class for emulating an API with cancellation."""

    _job_status = [
        {'status': 'RUNNING'},
        {'status': 'CANCELLED'}
    ]

    _can_cancel = True


class NonCancellableAPI(BaseFakeAPI):
    """Class for emulating an API without cancellation running a long job."""

    _job_status = [
        {'status': 'RUNNING'},
        {'status': 'RUNNING'},
        {'status': 'RUNNING'}
    ]


class ErroredCancellationAPI(BaseFakeAPI):
    """Class for emulating an API with cancellation but throwing while trying."""

    _job_status = [
        {'status': 'RUNNING'},
        {'status': 'RUNNING'},
        {'status': 'RUNNING'}
    ]

    _can_cancel = True

    def job_cancel(self, job_id, *_args, **_kwargs):
        return {'status': 'Error', 'error': 'test-error-while-cancelling'}


class NoKindJobAPI(BaseFakeAPI):
    """Class for emulating an API with QASM jobs."""

    _job_status = [
        {'status': 'COMPLETED'}
    ]

    no_kind_response = copy.deepcopy(VALID_JOB_RESPONSE)
    del no_kind_response['kind']

    def job_submit(self, *_args, **_kwargs):
        return self.no_kind_response

    def job_result(self, job_id, *_args, **_kwargs):
        return self.no_kind_response


class TranspilingStatusAPI(BaseFakeAPI):
    """Class for emulating an API with transpiling status codes."""

    _job_status = [
        {'status': 'TRANSPILING'},
        {'status': 'TRANSPILED'}
    ]
