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

"""Test IBMQConnector."""

import re

from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile
from qiskit.providers.ibmq import IBMQ
from qiskit.providers.ibmq.api import (ApiError, BadBackendError, IBMQConnector)
from qiskit.test import QiskitTestCase, requires_qe_access
from ..decorators import requires_classic_api


class TestIBMQConnector(QiskitTestCase):
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
    def _get_api(qe_token, qe_url):
        """Helper for instantating an IBMQConnector."""
        return IBMQConnector(qe_token, config={'url': qe_url})

    @requires_qe_access
    @requires_classic_api
    def test_api_auth_token(self, qe_token, qe_url):
        """Authentication with IBMQ Platform."""
        api = self._get_api(qe_token, qe_url)
        credential = api.check_credentials()
        self.assertTrue(credential)

    def test_api_auth_token_fail(self):
        """Invalid authentication with IBQM Platform."""
        self.assertRaises(ApiError,
                          IBMQConnector, 'fail')

    @requires_qe_access
    @requires_classic_api
    def test_api_run_job(self, qe_token, qe_url):
        """Test running a job against a simulator."""
        IBMQ.enable_account(qe_token, qe_url)

        backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(backend_name)
        qobj = assemble(transpile(self.qc1, backend=backend, seed_transpiler=self.seed),
                        backend=backend, shots=1)

        api = backend._api
        job = api.submit_job(qobj.as_dict(), backend_name)
        check_status = None
        if 'status' in job:
            check_status = job['status']
        self.assertIsNotNone(check_status)

    @requires_qe_access
    @requires_classic_api
    def test_api_run_job_fail_backend(self, qe_token, qe_url):
        """Test running a job against an invalid backend."""
        IBMQ.enable_account(qe_token, qe_url)

        backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(backend_name)
        qobj = assemble(transpile(self.qc1, backend=backend, seed_transpiler=self.seed),
                        backend=backend, shots=1)

        api = backend._api
        self.assertRaises(BadBackendError, api.submit_job, qobj.as_dict(),
                          'INVALID_BACKEND_NAME')

    @requires_qe_access
    @requires_classic_api
    def test_api_get_jobs(self, qe_token, qe_url):
        """Check get jobs by user authenticated."""
        api = self._get_api(qe_token, qe_url)
        jobs = api.get_jobs(2)
        self.assertEqual(len(jobs), 2)

    @requires_qe_access
    @requires_classic_api
    def test_api_get_status_jobs(self, qe_token, qe_url):
        """Check get status jobs by user authenticated."""
        api = self._get_api(qe_token, qe_url)
        jobs = api.get_status_jobs(1)
        self.assertEqual(len(jobs), 1)

    @requires_qe_access
    @requires_classic_api
    def test_api_backend_status(self, qe_token, qe_url):
        """Check the status of a real chip."""
        backend_name = ('ibmq_20_tokyo'
                        if self.using_ibmq_credentials else 'ibmqx4')
        api = self._get_api(qe_token, qe_url)
        is_available = api.backend_status(backend_name)
        self.assertIsNotNone(is_available['operational'])

    @requires_qe_access
    @requires_classic_api
    def test_api_backend_properties(self, qe_token, qe_url):
        """Check the properties of calibration of a real chip."""
        backend_name = ('ibmq_20_tokyo'
                        if self.using_ibmq_credentials else 'ibmqx4')
        api = self._get_api(qe_token, qe_url)

        properties = api.backend_properties(backend_name)
        self.assertIsNotNone(properties)

    @requires_qe_access
    @requires_classic_api
    def test_api_backends_available(self, qe_token, qe_url):
        """Check the backends available."""
        api = self._get_api(qe_token, qe_url)
        backends = api.available_backends()
        self.assertGreaterEqual(len(backends), 1)

    @requires_qe_access
    @requires_classic_api
    def test_qx_api_version(self, qe_token, qe_url):
        """Check the version of the QX API."""
        api = self._get_api(qe_token, qe_url)
        version = api.api_version()
        self.assertIn('new_api', version)

    @requires_qe_access
    @requires_classic_api
    def test_get_job_includes(self, qe_token, qe_url):
        """Check the field includes parameter for get_job."""
        IBMQ.enable_account(qe_token, qe_url)

        backend_name = 'ibmq_qasm_simulator'
        backend = IBMQ.get_backend(backend_name)
        qobj = assemble(transpile([self.qc1, self.qc2], backend=backend, seed_transpiler=self.seed),
                        backend=backend, shots=1)

        api = backend._api
        job = api.submit_job(qobj.as_dict(), backend_name)
        job_id = job['id']

        # Get the job, excluding a parameter.
        self.assertIn('deleted', job)
        job_excluded = api.get_job(job_id, exclude_fields=['deleted'])
        self.assertNotIn('deleted', job_excluded)


class TestAuthentication(QiskitTestCase):
    """Tests for the authentication features.

    These tests are in a separate TestCase as they need to control the
    instantiation of `IBMQConnector` directly.
    """
    @requires_qe_access
    @requires_classic_api
    def test_url_404(self, qe_token, qe_url):
        """Test accessing a 404 URL"""
        url_404 = re.sub(r'/api.*$', '/api/TEST_404', qe_url)
        with self.assertRaises(ApiError):
            _ = IBMQConnector(qe_token,
                              config={'url': url_404})

    @requires_qe_access
    @requires_classic_api
    def test_invalid_token(self, qe_token, qe_url):
        """Test using an invalid token"""
        qe_token = 'INVALID_TOKEN'
        with self.assertRaises(ApiError):
            _ = IBMQConnector(qe_token, config={'url': qe_url})

    @requires_qe_access
    @requires_classic_api
    def test_url_unreachable(self, qe_token, qe_url):
        """Test accessing an invalid URL"""
        qe_url = 'INVALID_URL'
        with self.assertRaises(ApiError):
            _ = IBMQConnector(qe_token, config={'url': qe_url})
