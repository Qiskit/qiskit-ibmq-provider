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
from qiskit.providers.ibmq.api_v2.exceptions import ApiError
from qiskit.test import QiskitTestCase, requires_qe_access

from ..decorators import requires_new_api_auth

import asyncio
import pproxy as pp


class TestProxies(QiskitTestCase):
    """Tests for proxy capabilities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Launch the mock server.
        server = pp.Server('ss://127.0.0.1:8080')
        remote = pp.Connection('ss://127.0.0.1:8080')
        args = dict(rserver=[remote],
                    verbose=print)
        cls.server = asyncio.get_event_loop().run_until_complete(server.start_server(args))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        # Close the mock server.
        loop = asyncio.get_event_loop()
        loop.stop()

    @requires_qe_access
    @requires_new_api_auth
    def test_proxies(self, qe_token, qe_url):
        """Test IBMQClient proxy support."""
        proxies = {
            'https': '127.0.0.1:8080'
        }

        IBMQClient(qe_token, qe_url, proxies)
        return
