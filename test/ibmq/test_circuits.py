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

from qiskit.providers.ibmq.circuits.exceptions import CircuitAvailabilityError

from qiskit.result import Result
from qiskit.test import QiskitTestCase

from qiskit.providers.ibmq import IBMQ

from ..decorators import requires_qe_access


class TestCircuits(QiskitTestCase):
    """Tests IBM Q Circuits."""

    def setUp(self):
        super().setUp()

        if not os.getenv('CIRCUITS_TESTS'):
            self.skipTest('Circut tests disable')

    @requires_qe_access
    def test_circuit_random_uniform(self, qe_token, qe_url):
        """Test random_uniform circuit."""
        IBMQ.enable_account(qe_token, qe_url)
        results = IBMQ.circuits.random_uniform(number_of_qubits=4)

        self.assertIsInstance(results, Result)

    def test_load_account_required(self):
        """Test that an account needs to be loaded for using Circuits."""
        with self.assertRaises(CircuitAvailabilityError) as context_manager:
            _ = IBMQ.circuits.random_uniform(number_of_qubits=4)

        self.assertIn('account', str(context_manager.exception))
