# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for the AccountClient class."""

import re
import traceback
from unittest import mock
from urllib3.connectionpool import HTTPConnectionPool
from urllib3.exceptions import MaxRetryError

from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile
from qiskit.providers.ibmq.apiconstants import ApiJobStatus
from qiskit.providers.ibmq.api.clients import AccountClient, AuthClient
from qiskit.providers.ibmq.api.exceptions import ApiError, RequestsApiError
from qiskit.providers.ibmq.job.utils import get_cancel_status
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.utils.utils import RefreshQueue

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_qe_access, requires_device, requires_provider
from ..contextmanagers import custom_envs, no_envs
from ..http_server import SimpleServer, ServerErrorOnceHandler


class TestAccountClient(IBMQTestCase):
    """Tests for AccountClient."""

    def setUp(self):
        """Initial test setup."""
        qr = QuantumRegister(2)
        cr = ClassicalRegister(2)
        self.qc1 = QuantumCircuit(qr, cr, name='qc1')
        self.qc2 = QuantumCircuit(qr, cr, name='qc2')
        self.qc1.h(qr)
        self.qc2.h(qr[0])
        self.qc2.cx(qr[0], qr[1])
        self.qc1.measure(qr[0], cr[0])
        self.qc1.measure(qr[1], cr[1])
        self.qc2.measure(qr[0], cr[0])
        self.qc2.measure(qr[1], cr[1])
        self.seed = 73846087

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.access_token = cls.provider._api.client_api.session.access_token

    def _get_client(self):
        """Helper for instantiating an AccountClient."""
        return AccountClient(self.access_token,
                             self.provider.credentials.url,
                             self.provider.credentials.websockets_url,
                             use_websockets=True)

    def test_job_submit_object_storage(self):
        """Test running a job against a simulator using object storage."""
        # Create a Qobj.
        backend_name = 'ibmq_qasm_simulator'
        backend = self.provider.get_backend(backend_name)
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)

        # Run the job through the AccountClient directly using object storage.
        api = backend._api

        job = api.job_submit(backend_name, qobj.to_dict())
        job_id = job['job_id']
        self.assertNotIn('shots', job)
        self.assertEqual(job['kind'], 'q-object-external-storage')

        # Wait for completion.
        api.job_final_status(job_id)

        # Fetch results and qobj via object storage.
        result = api._job_result_object_storage(job_id)
        qobj_downloaded = api._job_download_qobj_object_storage(job_id)

        self.assertEqual(qobj_downloaded, qobj.to_dict())
        self.assertEqual(result['status'], 'COMPLETED')

    def test_list_jobs_statuses(self):
        """Check get status jobs by user authenticated."""
        api = self._get_client()
        jobs = api.list_jobs_statuses(limit=2)
        self.assertEqual(len(jobs), 2)

    @requires_device
    def test_backend_status(self, backend):
        """Check the status of a real chip."""
        api = self._get_client()
        is_available = api.backend_status(backend.name())
        self.assertIsNotNone(is_available['operational'])

    @requires_device
    def test_backend_properties(self, backend):
        """Check the properties of calibration of a real chip."""
        api = self._get_client()

        properties = api.backend_properties(backend.name())
        self.assertIsNotNone(properties)

    @requires_device
    def test_backend_job_limit(self, backend):
        """Check the backend job limits of a real backend."""
        api = self._get_client()

        job_limit = api.backend_job_limit(backend.name())
        self.assertIsNotNone(job_limit)
        self.assertIsNotNone(job_limit['maximum_jobs'])
        self.assertIsNotNone(job_limit['running_jobs'])
        self.assertNotEqual(job_limit['maximum_jobs'], 0)

    def test_backend_pulse_defaults(self):
        """Check the backend pulse defaults of each backend."""
        api = self._get_client()
        api_backends = api.list_backends()
        # TODO revert to testing all backends when api is fixed
        test_backend_names = ['ibmq_armonk', 'ibmq_vigo', 'ibmq_qasm_simulator']

        for backend_info in api_backends:
            backend_name = backend_info['backend_name']
            if backend_name not in test_backend_names:
                continue
            with self.subTest(backend_name=backend_name):
                defaults = api.backend_pulse_defaults(backend_name=backend_name)
                is_open_pulse = backend_info['open_pulse']

                if is_open_pulse:
                    self.assertTrue(defaults)
                else:
                    self.assertFalse(defaults)

    def test_exception_message(self):
        """Check exception has proper message."""
        api = self._get_client()

        with self.assertRaises(RequestsApiError) as exception_context:
            api.job_status('foo')

        raised_exception = exception_context.exception
        original_error = raised_exception.__cause__.response.json()['error']
        self.assertIn(original_error['message'], raised_exception.message,
                      "Original error message not in raised exception")
        self.assertIn(str(original_error['code']), raised_exception.message,
                      "Original error code not in raised exception")

    def test_custom_client_app_header(self):
        """Check custom client application header."""
        custom_header = 'batman'
        with custom_envs({'QE_CUSTOM_CLIENT_APP_HEADER': custom_header}):
            api = self._get_client()
            self.assertIn(custom_header,
                          api.client_api.session.headers['X-Qx-Client-Application'])

        # Make sure the header is re-initialized
        with no_envs(['QE_CUSTOM_CLIENT_APP_HEADER']):
            api = self._get_client()
            self.assertNotIn(custom_header,
                             api.client_api.session.headers['X-Qx-Client-Application'])

    def test_list_backends(self):
        """Test listing backends."""
        api = self._get_client()
        provider_backends = {backend.name() for backend
                             in self.provider.backends()}
        api_backends = {backend_info['backend_name'] for backend_info
                        in api.list_backends()}

        self.assertEqual(provider_backends, api_backends)

    def test_job_cancel(self):
        """Test canceling a job."""
        backend_name = 'ibmq_qasm_simulator'
        backend = self.provider.get_backend(backend_name)
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)

        api = backend._api
        job = backend.run(qobj, validate_qobj=True)
        job_id = job.job_id()

        max_retry = 2
        for _ in range(max_retry):
            try:
                cancel_response = api.job_cancel(job_id)
                is_cancelled = get_cancel_status(cancel_response)
                if is_cancelled:
                    status = job.status()
                    self.assertEqual(status, JobStatus.CANCELLED,
                                     'cancel() was successful for job {} but its status is {}.'
                                     .format(job.job_id(), status))
                    break
            except RequestsApiError as ex:
                if 'JOB_NOT_RUNNING' in str(ex):
                    self.assertEqual(job.status(), JobStatus.DONE)
                    break
                # We may hit the JOB_NOT_CANCELLED error if the job is
                # in a temporary, noncancellable state. In this case we'll
                # just retry.
                self.assertIn('JOB_NOT_CANCELLED', str(ex))

    def test_access_token_not_in_exception_traceback(self):
        """Check that access token is replaced within chained request exceptions."""
        backend = self.provider.backends.ibmq_qasm_simulator
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)
        api = backend._api

        exception_message = 'The access token in this exception ' \
                            'message should be replaced: {}'.format(self.access_token)
        exception_traceback_str = ''
        try:
            with mock.patch.object(
                    HTTPConnectionPool,
                    'urlopen',
                    side_effect=MaxRetryError(
                        HTTPConnectionPool('host'), 'url', reason=exception_message)):
                _ = api.job_submit(backend.name(), qobj.to_dict())
        except RequestsApiError:
            exception_traceback_str = traceback.format_exc()

        self.assertTrue(exception_traceback_str)
        if self.access_token in exception_traceback_str:
            self.fail('Access token not replaced in request exception traceback.')

    def test_job_submit_retry(self):
        """Test job submit requests get retried."""
        backend_name = 'ibmq_qasm_simulator'
        backend = self.provider.get_backend(backend_name)
        api = backend._api

        # Send request to local server.
        valid_data = {'id': 'fake_id', 'url': SimpleServer.URL, 'job': {'id': 'fake_id'}}
        SimpleServer(handler_class=ServerErrorOnceHandler, valid_data=valid_data).start()
        api.client_api.session.base_url = SimpleServer.URL

        api.job_submit(backend_name, {})


class TestAccountClientJobs(IBMQTestCase):
    """Tests for AccountClient methods related to jobs.

    This TestCase submits a Job during class invocation, available at
    ``cls.job``. Tests should inspect that job according to their needs.
    """

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.access_token = cls.provider._api.client_api.session.access_token

        backend_name = 'ibmq_qasm_simulator'
        backend = cls.provider.get_backend(backend_name)
        cls.client = backend._api
        cls.job = cls.client.job_submit(
            backend_name, cls._get_qobj(backend).to_dict())
        cls.job_id = cls.job['job_id']

    @staticmethod
    def _get_qobj(backend):
        """Return a Qobj."""
        # Create a circuit.
        qr = QuantumRegister(2)
        cr = ClassicalRegister(2)
        qc1 = QuantumCircuit(qr, cr, name='qc1')
        seed = 73846087

        # Assemble the Qobj.
        qobj = assemble(transpile([qc1], backend=backend,
                                  seed_transpiler=seed),
                        backend=backend, shots=1)

        return qobj

    def test_job_get(self):
        """Test job_get."""
        response = self.client.job_get(self.job_id)
        self.assertIn('status', response)

    def test_job_status(self):
        """Test getting job status."""
        response = self.client.job_status(self.job_id)
        self.assertIn('status', response)

    def test_job_final_status_websocket(self):
        """Test getting a job's final status via websocket."""
        response = self.client._job_final_status_websocket(self.job_id)
        self.assertEqual(response.pop('status', None), ApiJobStatus.COMPLETED.value)

    def test_job_final_status_polling(self):
        """Test getting a job's final status via polling."""
        status_queue = RefreshQueue(maxsize=1)
        response = self.client._job_final_status_polling(self.job_id, status_queue=status_queue)
        self.assertEqual(response.pop('status', None), ApiJobStatus.COMPLETED.value)
        self.assertNotEqual(status_queue.qsize(), 0)

    def test_job_properties(self):
        """Test getting job properties."""
        # Force the job to finish.
        _ = self.client._job_final_status_websocket(self.job_id)

        response = self.client.job_properties(self.job_id)
        # Since the job is against a simulator, it will have no properties.
        self.assertFalse(response)

    def test_list_jobs_statuses_limit(self):
        """Test listing job statuses with a limit."""
        jobs_raw = self.client.list_jobs_statuses(limit=1)
        self.assertEqual(len(jobs_raw), 1)

    def test_list_jobs_statuses_skip(self):
        """Test listing job statuses with an offset."""
        jobs_raw = self.client.list_jobs_statuses(limit=1, skip=1, extra_filter={
            'creationDate': {'lte': self.job['creation_date']}})

        # Ensure our job is skipped
        for job in jobs_raw:
            self.assertNotEqual(job['job_id'], self.job_id)

    def test_list_jobs_statuses_filter(self):
        """Test listing job statuses with a filter."""
        jobs_raw = self.client.list_jobs_statuses(extra_filter={'id': self.job_id})
        self.assertEqual(len(jobs_raw), 1)
        self.assertEqual(jobs_raw[0]['job_id'], self.job_id)


class TestAuthClient(IBMQTestCase):
    """Tests for the AuthClient."""

    @requires_qe_access
    def test_valid_login(self, qe_token, qe_url):
        """Test valid authentication."""
        client = AuthClient(qe_token, qe_url)
        self.assertTrue(client.client_api.session.access_token)

    @requires_qe_access
    def test_url_404(self, qe_token, qe_url):
        """Test login against a 404 URL"""
        url_404 = re.sub(r'/api.*$', '/api/TEST_404', qe_url)
        with self.assertRaises(ApiError):
            _ = AuthClient(qe_token, url_404)

    @requires_qe_access
    def test_invalid_token(self, qe_token, qe_url):
        """Test login using invalid token."""
        qe_token = 'INVALID_TOKEN'
        with self.assertRaises(ApiError):
            _ = AuthClient(qe_token, qe_url)

    @requires_qe_access
    def test_url_unreachable(self, qe_token, qe_url):
        """Test login against an invalid (malformed) URL."""
        qe_url = 'INVALID_URL'
        with self.assertRaises(ApiError):
            _ = AuthClient(qe_token, qe_url)

    @requires_qe_access
    def test_api_version(self, qe_token, qe_url):
        """Check the version of the QX API."""
        api = AuthClient(qe_token, qe_url)
        version = api.api_version()
        self.assertIsNotNone(version)

    @requires_qe_access
    def test_user_urls(self, qe_token, qe_url):
        """Check the user urls of the QX API."""
        api = AuthClient(qe_token, qe_url)
        user_urls = api.user_urls()
        self.assertIsNotNone(user_urls)
        self.assertTrue('http' in user_urls and 'ws' in user_urls)

    @requires_qe_access
    def test_user_hubs(self, qe_token, qe_url):
        """Check the user hubs of the QX API."""
        api = AuthClient(qe_token, qe_url)
        user_hubs = api.user_hubs()
        self.assertIsNotNone(user_hubs)
        for user_hub in user_hubs:
            with self.subTest(user_hub=user_hub):
                self.assertTrue('hub' in user_hub
                                and 'group' in user_hub
                                and 'project' in user_hub)
