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

"""Tests for the IBMQClient proxy support."""

import urllib
import subprocess

from requests.exceptions import ProxyError

from qiskit.providers.ibmq.api_v2 import IBMQClient
from qiskit.providers.ibmq.api_v2.exceptions import RequestsApiError
from qiskit.test import QiskitTestCase, requires_qe_access

from ..decorators import requires_new_api_auth

ADDRESS = '127.0.0.1'
PORT = '8080'


class TestProxies(QiskitTestCase):
    """Tests for proxy capabilities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Launch the mock server.
        cls.proxy_process = subprocess.Popen([
            'pproxy', '-v', '-i', 'http://{}:{}'.format(ADDRESS, PORT)
        ], stdout=subprocess.PIPE)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        # Close the mock server.
        if cls.proxy_process.returncode is None:
            cls.proxy_process.terminate()

    @requires_qe_access
    @requires_new_api_auth
    def test_proxies(self, qe_token, qe_url):
        """Should reach the proxy."""
        input_proxies = {
            'https': 'http://{}:{}'.format(ADDRESS, PORT)
        }

        qe_url_parts = urllib.parse.urlparse(qe_url)
        protocol_port = '443' if qe_url_parts.scheme == 'https' else '80'
        pproxy_desired_access_log_line = 'http {}:{}'.format(qe_url_parts.hostname, protocol_port)

        _ = IBMQClient(qe_token, qe_url, input_proxies)

        self.proxy_process.terminate()  # kill to be able of reading the output
        self.assertIn(
            pproxy_desired_access_log_line, self.proxy_process.stdout.read().decode('utf-8'))

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_port(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError as original exception."""
        input_proxies = {
            'https': '{}:{}'.format(ADDRESS, '6666')
        }

        with self.assertRaises(RequestsApiError) as context_manager:
            _ = IBMQClient(qe_token, qe_url, input_proxies)

        self.assertIsInstance(context_manager.exception.original_exception, ProxyError)

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_address(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError as original exception."""
        input_proxies = {
            'https': '{}:{}'.format('invalid', PORT)
        }

        with self.assertRaises(RequestsApiError) as context_manager:
            _ = IBMQClient(qe_token, qe_url, input_proxies)

        self.assertIsInstance(context_manager.exception.original_exception, ProxyError)
