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

"""Tests for the IBMQClient for API v2."""

import re
from unittest import skip

from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile
from qiskit.providers.ibmq import IBMQ
from qiskit.providers.ibmq.api_v2 import IBMQClient
from qiskit.providers.ibmq.api_v2.exceptions import ApiError, RequestsApiError
from qiskit.test import QiskitTestCase

from ..decorators import requires_new_api_auth, requires_qe_access
from ..contextmanagers import custom_envs, no_envs


class TestIBMQClient(QiskitTestCase):
    """Tests for IBMQConnector."""

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

    @staticmethod
    def _get_client(qe_token, qe_url):
        """Helper for instantiating an IBMQClient."""
        return IBMQClient(qe_token, qe_url)

    @requires_qe_access
    @requires_new_api_auth
    def test_valid_login(self, qe_token, qe_url):
        """Test valid authenticating against IBM Q."""
        client = self._get_client(qe_token, qe_url)
        self.assertTrue(client.client_api.session.access_token)

    @requires_qe_access
    @requires_new_api_auth
    def test_run_job(self, qe_token, qe_url):
        """Test running a job against a simulator."""
        IBMQ.enable_account(qe_token, qe_url)

        # Create a Qobj.
        backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(backend_name)
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)

        # Run the job through the IBMQClient directly.
        api = backend._api
        job = api.submit_job(qobj.to_dict(), backend_name)

        self.assertIn('status', job)
        self.assertIsNotNone(job['status'])

    @requires_qe_access
    @requires_new_api_auth
    def test_run_job_object_storage(self, qe_token, qe_url):
        """Test running a job against a simulator using object storage."""
        IBMQ.enable_account(qe_token, qe_url)

        # Create a Qobj.
        backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(backend_name)
        circuit = transpile(self.qc1, backend, seed_transpiler=self.seed)
        qobj = assemble(circuit, backend, shots=1)

        # Run the job through the IBMQClient directly using object storage.
        api = backend._api
        job = api.job_submit_object_storage(backend_name, qobj.to_dict())
        job_id = job['id']
        self.assertEqual(job['kind'], 'q-object-external-storage')

        # Wait for completion.
        api.job_final_status_websocket(job_id)

        # Fetch results and qobj via object storage.
        result = api.job_result_object_storage(job_id)
        qobj_downloaded = api.job_download_qobj_object_storage(job_id)

        self.assertEqual(qobj_downloaded, qobj.to_dict())
        self.assertEqual(result['status'], 'COMPLETED')

    @requires_qe_access
    @requires_new_api_auth
    def test_get_status_jobs(self, qe_token, qe_url):
        """Check get status jobs by user authenticated."""
        api = self._get_client(qe_token, qe_url)
        jobs = api.get_status_jobs(limit=2)
        self.assertEqual(len(jobs), 2)

    @requires_qe_access
    @requires_new_api_auth
    def test_backend_status(self, qe_token, qe_url):
        """Check the status of a real chip."""
        backend_name = ('ibmq_20_tokyo'
                        if self.using_ibmq_credentials else 'ibmqx4')
        api = self._get_client(qe_token, qe_url)
        is_available = api.backend_status(backend_name)
        self.assertIsNotNone(is_available['operational'])

    @requires_qe_access
    @requires_new_api_auth
    def test_backend_properties(self, qe_token, qe_url):
        """Check the properties of calibration of a real chip."""
        backend_name = ('ibmq_20_tokyo'
                        if self.using_ibmq_credentials else 'ibmqx4')
        api = self._get_client(qe_token, qe_url)

        properties = api.backend_properties(backend_name)
        self.assertIsNotNone(properties)

    @requires_qe_access
    @requires_new_api_auth
    def test_available_backends(self, qe_token, qe_url):
        """Check the backends available."""
        api = self._get_client(qe_token, qe_url)
        backends = api.available_backends()
        self.assertGreaterEqual(len(backends), 1)

    @requires_qe_access
    @requires_new_api_auth
    def test_api_version(self, qe_token, qe_url):
        """Check the version of the QX API."""
        api = self._get_client(qe_token, qe_url)
        version = api.api_version()
        self.assertIsNotNone(version)

    @requires_qe_access
    @requires_new_api_auth
    def test_exception_message(self, qe_token, qe_url):
        """Check exception has proper message."""
        api = self._get_client(qe_token, qe_url)

        with self.assertRaises(RequestsApiError) as exception_context:
            api.job_status('foo')

        raised_exception = exception_context.exception
        original_error = raised_exception.original_exception.response.json()['error']
        self.assertIn(original_error['message'], raised_exception.message,
                      "Original error message not in raised exception")
        self.assertIn(original_error['code'], raised_exception.message,
                      "Original error code not in raised exception")

    @requires_qe_access
    @requires_new_api_auth
    def test_custom_client_app_header(self, qe_token, qe_url):
        """Check custom client application header"""
        custom_header = 'batman'
        with custom_envs({'QE_CUSTOM_CLIENT_APP_HEADER': custom_header}):
            api = self._get_client(qe_token, qe_url)
            self.assertIn(custom_header,
                          api.client_api.session.headers['X-Qx-Client-Application'])

        # Make sure the header is re-initialized
        with no_envs(['QE_CUSTOM_CLIENT_APP_HEADER']):
            api = self._get_client(qe_token, qe_url)
            self.assertNotIn(custom_header,
                             api.client_api.session.headers['X-Qx-Client-Application'])

    def _submit_job_to_backend(self, backend_name):
        """Submit a generic qobj job to the backend

        Args:
            backend_name (str): backend name

        Returns:
            tuple(IBMQConnector, dict):
                IBMQConnector: API for communicating with IBMQ.
                dict: API response to the job submit.
        """
        backend = IBMQ.get_backend(backend_name)
        qobj = assemble(transpile([self.qc1, self.qc2], backend=backend, seed_transpiler=self.seed),
                        backend=backend, shots=1)

        api = backend._api
        job = api.submit_job(qobj.to_dict(), backend_name)
        return api, job


class TestAuthentication(QiskitTestCase):
    """Tests for the authentication features.

    These tests are in a separate TestCase as they need to control the
    instantiation of `IBMQConnector` directly.
    """

    @requires_qe_access
    @requires_new_api_auth
    def test_url_404(self, qe_token, qe_url):
        """Test login against a 404 URL"""
        url_404 = re.sub(r'/api.*$', '/api/TEST_404', qe_url)
        with self.assertRaises(ApiError):
            _ = IBMQClient(qe_token, url_404)

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_token(self, qe_token, qe_url):
        """Test login using invalid token."""
        qe_token = 'INVALID_TOKEN'
        with self.assertRaises(ApiError):
            _ = IBMQClient(qe_token, qe_url)

    @requires_qe_access
    @requires_new_api_auth
    def test_url_unreachable(self, qe_token, qe_url):
        """Test login against an invalid (malformed) URL."""
        qe_url = 'INVALID_URL'
        with self.assertRaises(ApiError):
            _ = IBMQClient(qe_token, qe_url)


class TestIBMQClientJobs(QiskitTestCase):
    """Tests for IBMQClient methods relating to inspecting its jobs."""

    # pylint: disable=arguments-differ
    @classmethod
    @requires_qe_access
    @requires_new_api_auth
    def setUpClass(cls, qe_token, qe_url):
        super().setUpClass()

        IBMQ.enable_account(qe_token, qe_url)

        # Create a circuit
        qr = QuantumRegister(2)
        cr = ClassicalRegister(2)
        qc1 = QuantumCircuit(qr, cr, name='qc1')
        seed = 73846087

        # Create a Qobj.
        cls.backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(cls.backend_name)
        circuit = transpile(qc1, backend, seed_transpiler=seed)
        cls.qobj = assemble(circuit, backend, shots=1)

        # Run the job through the IBMQClient directly.
        cls.client = backend._api
        cls.job = cls.client.submit_job(cls.qobj.to_dict(), cls.backend_name)

        cls.job_id = cls.job['id']

    def test_get_job_includes(self):
        """Check the include fields parameter for get_job."""
        # Get the job, including some fields.
        self.assertIn('backend', self.job)
        self.assertIn('shots', self.job)
        job_included = self.client.get_job(self.job_id, include_fields=['backend', 'shots'])

        # Ensure the result has only the included fields
        self.assertEqual({'backend', 'shots'}, set(job_included.keys()))

    def test_get_job_excludes(self):
        """Check the exclude fields parameter for get_job."""

        # Get the job, excluding a field.
        self.assertIn('shots', self.job)
        self.assertIn('backend', self.job)
        job_excluded = self.client.get_job(self.job_id, exclude_fields=['backend'])

        # Ensure the result only excludes the specified field
        self.assertNotIn('backend', job_excluded)
        self.assertIn('shots', self.job)

    def test_get_job_includes_nonexistent(self):
        """Check get_job including nonexistent fields."""
        # Get the job, including an nonexistent field.
        self.assertNotIn('dummy_include', self.job)
        job_included = self.client.get_job(self.job_id, include_fields=['dummy_include'])
        # Ensure the result is empty, since no existing fields are included
        self.assertFalse(job_included)

    def test_get_job_excludes_nonexistent(self):
        """Check get_job excluding nonexistent fields."""
        # Get the job, excluding an non-existent field.
        self.assertNotIn('dummy_exclude', self.job)
        self.assertIn('shots', self.job)
        job_excluded = self.client.get_job(self.job_id, exclude_fields=['dummy_exclude'])

        # Ensure the result only excludes the specified field. We can't do a direct
        # comparison against the original job because some fields might have changed.
        self.assertIn('shots', job_excluded)

    def test_job_submit(self):
        """Test job submission."""
        result = self.client.job_submit(self.backend_name, self.qobj.to_dict())
        status_present = ['status' in [dict_ for dict_ in result.get('qasms')]]
        self.assertTrue(status_present)

    @skip
    # TODO: Q-Object-External-Storage property is not allowed in this backend
    def test_job_submit_object_storage(self):
        """Test job submission using object storage."""
        # Get the job via object storage.
        # result = self.client.job_submit_object_storage(self.backend_name,
        #                                                self.qobj.to_dict())

        # TODO
        pass

    @skip
    # TODO: RequestsApiError: 404 Client Error: Not Found for url: [...] None, Error code: NotFound.
    def test_job_download_qobj_object_storage(self):
        """Test job Qobj download using object storage."""
        # result = self.client.job_download_qobj_object_storage(self.job_id)

        # TODO
        pass

    @skip
    # TODO: RequestsApiError: 404 Client Error: Not Found for url: [...] None, Error code: NotFound.
    def test_job_result_object_storage(self):
        """Test getting a job's result using object storage."""
        # result = self.client.job_result_object_storage(self.job_id)

        # TODO
        pass

    def test_job_get_responsive(self):
        """Test getting a job responds with something other than None."""
        result = self.client.job_get(self.job_id)
        status_present = ['status' in [dict_ for dict_ in result.get('qasms')]]
        self.assertTrue(status_present)

    def test_job_get_filtered_fields(self):
        """Test getting a job responds uses field filters correctly."""
        no_params_result = self.client.job_get(self.job_id)

        # test exclusion returns a different result than the default
        excluded_fields = ['qasms']
        excluded_fields_result = self.client.job_get(self.job_id, excluded_fields=excluded_fields)
        self.assertNotEqual(excluded_fields_result, no_params_result)

        # test inclusion returns a different result than the default
        included_fields = ['qasms']
        included_fields_result = self.client.job_get(self.job_id, included_fields=included_fields)
        self.assertNotEqual(included_fields_result, no_params_result)

        # test sending both an include and exclude list uses only the include list
        include_and_exclude_result = self.client.job_get(self.job_id,
                                                         included_fields=included_fields,
                                                         excluded_fields=excluded_fields)
        self.assertDictEqual(include_and_exclude_result, included_fields_result)

    def test_job_status(self):
        """Test getting job status."""
        result = self.client.job_status(self.job_id)
        status_present = 'status' in result
        self.assertTrue(status_present)

    def test_job_final_status_websocket(self):
        """Test getting a job's final status via websocket."""
        result = self.client.job_final_status_websocket(self.job_id)
        status_present = 'status' in result
        self.assertTrue(status_present)

    def test_job_properties(self):
        """Test getting job properties."""
        # TODO - is {} an acceptable response here?
        result = self.client.job_properties(self.job_id)
        self.assertIsNotNone(result)

    # TODO: RequestsApiError: 404 Client Error: Not Found for url: [...]
    def test_job_cancel(self):
        """Test cancelling a job."""
        result = self.client.job_cancel(self.job_id)
        print(result)

        # TODO
        pass
