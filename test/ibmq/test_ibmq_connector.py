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

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_classic_api, requires_qe_access


class TestIBMQConnector(IBMQTestCase):
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


class TestAuthentication(IBMQTestCase):
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
