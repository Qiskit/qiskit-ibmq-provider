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

"""Tests for Circuits."""

import os

from qiskit.providers.ibmq.ibmqfactory import IBMQFactory
from qiskit.result import Result

from ..decorators import requires_new_api_auth, requires_qe_access
from ..ibmqtestcase import IBMQTestCase


class TestCircuits(IBMQTestCase):
    """Tests IBM Q Circuits."""

    def setUp(self):
        super().setUp()

        if not os.getenv('CIRCUITS_TESTS'):
            self.skipTest('Circut tests disable')

    @requires_qe_access
    @requires_new_api_auth
    def test_circuit_random_uniform(self, qe_token, qe_url):
        """Test random_uniform circuit."""
        ibmq_factory = IBMQFactory()
        provider = ibmq_factory.enable_account(qe_token, qe_url)
        results = provider.circuits.random_uniform(number_of_qubits=4)

        self.assertIsInstance(results, Result)
