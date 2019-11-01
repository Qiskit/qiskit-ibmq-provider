# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for the AccountClient for IBM Q Experience."""

from unittest import mock
import re

from requests.exceptions import RequestException

from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile
from qiskit.providers.ibmq.api.clients import AccountClient, AuthClient
from qiskit.providers.ibmq.api.exceptions import ApiError, RequestsApiError
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory
from qiskit.providers.jobstatus import JobStatus

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_qe_access, requires_device
from ..contextmanagers import custom_envs, no_envs


class TestAccountClient(IBMQTestCase):
    """Tests for AccountClient."""

    def setUp(self):
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
    def setUpClass(cls):
        cls.provider = cls._get_provider()
        cls.access_token = cls.provider._api.client_api.session.access_token

    @classmethod
    @requires_qe_access
    def _get_provider(cls, qe_token=None, qe_url=None):
        """Helper for getting account credentials."""
        ibmq_factory = IBMQFactory()
        provider = ibmq_factory.enable_account(qe_token, qe_url)
        return provider

    def _get_client(self):
        """Helper for instantiating an AccountClient."""
        return AccountClient(self.access_token,
                             self.provider.credentials.url,
                             self.provider.credentials.websockets_url,
                             use_websockets=True)

    def test_job_submit(self):
        """Test job_submit, running a job against a simulator."""
        # Create a Qobj.
        backend_name = 'ibmq_qasm_simulator'
        backend = self.provider.get_backend(backend_name)
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)

        # Run the job through the AccountClient directly.
        api = backend._api
        job = api.job_submit(backend_name, qobj.to_dict(), use_object_storage=False)

        self.assertIn('status', job)
        self.assertIsNotNone(job['status'])

    def test_job_submit_object_storage(self):
        """Test running a job against a simulator using object storage."""
        # Create a Qobj.
        backend_name = 'ibmq_qasm_simulator'
        backend = self.provider.get_backend(backend_name)
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)

        # Run the job through the AccountClient directly using object storage.
        api = backend._api

        try:
            job = api._job_submit_object_storage(backend_name, qobj.to_dict())
        except RequestsApiError as ex:
            # Get the original connection that was raised.
            original_exception = ex.__cause__

            if isinstance(original_exception, RequestException):
                # Get the response from the original request exception.
                error_response = original_exception.response    # pylint: disable=no-member
                if error_response is not None and error_response.status_code == 400:
                    try:
                        api_code = error_response.json()['error']['code']

                        # If we reach that point, it means the backend does not
                        # support qobject storage.
                        self.assertEqual(api_code, 'Q_OBJECT_STORAGE_IS_NOT_ALLOWED')
                        return
                    except (ValueError, KeyError):
                        pass
            raise

        job_id = job['id']
        self.assertEqual(job['kind'], 'q-object-external-storage')

        # Wait for completion.
        api.job_final_status(job_id)

        # Fetch results and qobj via object storage.
        result = api._job_result_object_storage(job_id)
        qobj_downloaded = api._job_download_qobj_object_storage(job_id)

        self.assertEqual(qobj_downloaded, qobj.to_dict())
        self.assertEqual(result['status'], 'COMPLETED')

    def test_job_submit_object_storage_fallback(self):
        """Test job_submit fallback when object storage fails."""
        # Create a Qobj.
        backend_name = 'ibmq_qasm_simulator'
        backend = self.provider.get_backend(backend_name)
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)

        # Run via the AccountClient, making object storage fail.
        api = backend._api
        with mock.patch.object(api, '_job_submit_object_storage',
                               side_effect=Exception()), \
                mock.patch.object(api, '_job_submit_post') as mocked_post:
            _ = api.job_submit(backend_name, qobj.to_dict(), use_object_storage=True)

        # Assert the POST has been called.
        self.assertEqual(mocked_post.called, True)

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

    def test_backend_pulse_defaults(self):
        """Check the backend pulse defaults of each backend."""
        api = self._get_client()
        api_backends = api.list_backends()

        for backend_info in api_backends:
            backend_name = backend_info['backend_name']
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
        self.assertIn(original_error['code'], raised_exception.message,
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
        job = backend.run(qobj)
        job_id = job.job_id()

        max_retry = 2
        for _ in range(max_retry):
            try:
                api.job_cancel(job_id)
                self.assertEqual(job.status(), JobStatus.CANCELLED)
                break
            except RequestsApiError as ex:
                if 'JOB_NOT_RUNNING' in str(ex):
                    self.assertEqual(job.status(), JobStatus.DONE)
                    break
                else:
                    # We may hit the JOB_NOT_CANCELLED error if the job is
                    # in a temporary, noncancellable state. In this case we'll
                    # just retry.
                    self.assertIn('JOB_NOT_CANCELLED', str(ex))


class TestAccountClientJobs(IBMQTestCase):
    """Tests for AccountClient methods related to jobs.

    This TestCase submits a Job during class invocation, available at
    `cls.job`. Tests should inspect that job according to their needs.
    """

    @classmethod
    def setUpClass(cls):
        cls.provider = cls._get_provider()
        cls.access_token = cls.provider._api.client_api.session.access_token

        backend_name = 'ibmq_qasm_simulator'
        backend = cls.provider.get_backend(backend_name)
        cls.client = backend._api
        cls.job = cls.client.job_submit(
            backend_name, cls._get_qobj(backend).to_dict(),
            use_object_storage=backend.configuration().allow_object_storage)
        cls.job_id = cls.job['id']

    @classmethod
    @requires_qe_access
    def _get_provider(cls, qe_token=None, qe_url=None):
        """Helper for getting account credentials."""
        ibmq_factory = IBMQFactory()
        provider = ibmq_factory.enable_account(qe_token, qe_url)
        return provider

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
        self.assertIn('status', response)

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
            'creationDate': {'lte': self.job['creationDate']}})

        # Ensure our job is skipped
        for job in jobs_raw:
            self.assertNotEqual(job['id'], self.job_id)

    def test_list_jobs_statuses_filter(self):
        """Test listing job statuses with a filter."""
        jobs_raw = self.client.list_jobs_statuses(extra_filter={'id': self.job_id})
        self.assertEqual(len(jobs_raw), 1)
        self.assertEqual(jobs_raw[0]['id'], self.job_id)


class TestAuthClient(IBMQTestCase):
    """Tests for the AuthClient."""

    @requires_qe_access
    def test_valid_login(self, qe_token, qe_url):
        """Test valid authenticating against IBM Q."""
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
