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
from unittest import SkipTest, skip

from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.providers.ibmq import IBMQ
from qiskit.providers.ibmq.api_v2 import IBMQClient
from qiskit.providers.ibmq.api_v2.exceptions import ApiError
from qiskit.test import QiskitTestCase, requires_qe_access
from qiskit.tools.compiler import compile


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
        if not ('quantum-computing.ibm.com/api' in qe_url and
                'auth' in qe_url):
            raise SkipTest('Test needs credentials for new API')
        return IBMQClient(qe_token, qe_url)

    @requires_qe_access
    def test_valid_login(self, qe_token, qe_url):
        """Test valid authenticating against IBM Q."""
        client = self._get_client(qe_token, qe_url)
        self.assertTrue(client.api_client.session.access_token)

    @requires_qe_access
    def test_run_job(self, qe_token, qe_url):
        """Test running a job against a simulator."""
        _ = self._get_client(qe_token, qe_url)
        IBMQ.enable_account(qe_token, qe_url)

        # Create a Qobj.
        backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(backend_name)
        qobj = compile(self.qc1, backend=backend, seed=self.seed, shots=1)

        # Run the job through the IBMQClient directly.
        api = backend._api
        job = api.run_job(qobj.as_dict(), backend_name)

        self.assertIn('status', job)
        self.assertIsNotNone(job['status'])

    @requires_qe_access
    def test_get_status_jobs(self, qe_token, qe_url):
        """Check get status jobs by user authenticated."""
        api = self._get_client(qe_token, qe_url)
        jobs = api.get_status_jobs(limit=2)
        self.assertEqual(len(jobs), 2)

    @requires_qe_access
    def test_backend_status(self, qe_token, qe_url):
        """Check the status of a real chip."""
        backend_name = ('ibmq_20_tokyo'
                        if self.using_ibmq_credentials else 'ibmqx4')
        api = self._get_client(qe_token, qe_url)
        is_available = api.backend_status(backend_name)
        self.assertIsNotNone(is_available['operational'])

    @requires_qe_access
    def test_backend_properties(self, qe_token, qe_url):
        """Check the properties of calibration of a real chip."""
        backend_name = ('ibmq_20_tokyo'
                        if self.using_ibmq_credentials else 'ibmqx4')
        api = self._get_client(qe_token, qe_url)

        properties = api.backend_properties(backend_name)
        self.assertIsNotNone(properties)

    @requires_qe_access
    def test_available_backends(self, qe_token, qe_url):
        """Check the backends available."""
        api = self._get_client(qe_token, qe_url)
        backends = api.available_backends()
        self.assertGreaterEqual(len(backends), 1)

    @requires_qe_access
    def test_api_version(self, qe_token, qe_url):
        """Check the version of the QX API."""
        api = self._get_client(qe_token, qe_url)
        version = api.api_version()
        self.assertIsNotNone(version)

    @skip('TODO: reenable after API check')
    @requires_qe_access
    def test_get_job_includes(self, qe_token, qe_url):
        """Check the field includes parameter for get_job."""
        _ = self._get_client(qe_token, qe_url)
        IBMQ.enable_account(qe_token, qe_url)

        backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(backend_name)
        qobj = compile([self.qc1, self.qc2],
                       backend=backend, seed=self.seed, shots=1)

        api = backend._api
        job = api.run_job(qobj.as_dict(), backend_name)
        job_id = job['id']

        # Get the job, excluding a parameter.
        self.assertIn('shots', job)
        job_excluded = api.get_job(job_id, exclude_fields=['shots'])
        self.assertNotIn('shots', job_excluded)


class TestAuthentication(QiskitTestCase):
    """Tests for the authentication features.

    These tests are in a separate TestCase as they need to control the
    instantiation of `IBMQConnector` directly.
    """

    @requires_qe_access
    def test_url_404(self, qe_token, qe_url):
        """Test login against a 404 URL"""
        url_404 = re.sub(r'/api.*$', '/api/TEST_404', qe_url)
        with self.assertRaises(ApiError):
            _ = IBMQClient(qe_token, url_404)

    @requires_qe_access
    def test_invalid_token(self, qe_token, qe_url):
        """Test login using invalid token."""
        qe_token = 'INVALID_TOKEN'
        with self.assertRaises(ApiError):
            _ = IBMQClient(qe_token, qe_url)

    @requires_qe_access
    def test_url_unreachable(self, qe_token, qe_url):
        """Test login against an invalid (malformed) URL."""
        qe_url = 'INVALID_URL'
        with self.assertRaises(ApiError):
            _ = IBMQClient(qe_token, qe_url)
