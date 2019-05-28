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


class TestProxies(QiskitTestCase):
    """Tests for proxies."""

    @requires_qe_access
    def test_proxies(self, qe_token, qe_url):
        """Test valid authenticating against IBM Q."""
        proxies = None
        #client = IBMQClient(qe_token, qe_url, proxies)
        pass
