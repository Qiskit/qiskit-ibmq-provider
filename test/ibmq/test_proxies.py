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

import subprocess

from qiskit.providers.ibmq.api_v2 import IBMQClient
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
        cls.proxy_process = subprocess.Popen(
           ['pproxy', '-l', 'http://{}:{}'.format(ADDRESS, PORT)])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        # Close the mock server.
        cls.proxy_process.kill()

    @requires_qe_access
    @requires_new_api_auth
    def test_proxies(self, qe_token, qe_url):
        """Test IBMQClient proxy connection."""
        input_proxies = {
            'https': '{}:{}'.format(ADDRESS, PORT)
        }

        client = IBMQClient(qe_token, qe_url, input_proxies)
        self.assertEqual(client.proxies, input_proxies)
