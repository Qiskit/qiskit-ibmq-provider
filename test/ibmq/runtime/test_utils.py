# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for runtime utils."""

from qiskit.providers.ibmq.runtime.utils import ProviderRequestParams
from qiskit import QuantumCircuit


from ...ibmqtestcase import IBMQTestCase


class TestProviderRequestParams(IBMQTestCase):
    """ Tests the correctness of the ProviderRequestParams class """

    def test_provider_request_params(self):
        """ Test valid and invalid constructions of ProviderRequestParams """
        # Valid construction
        ProviderRequestParams(circuits=QuantumCircuit(), shots=2048, optimization_level=3)
        # Invalid construction: Missing required property `circuits`
        with self.assertRaises(TypeError):
            ProviderRequestParams(shots=2048, optimization_level=2, rep_delay=0.1)
