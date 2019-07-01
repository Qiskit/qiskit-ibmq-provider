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

"""Backends Filtering Test."""

from qiskit.providers.ibmq import least_busy

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider


class TestBackendFilters(IBMQTestCase):
    """Qiskit Backend Filtering Tests."""

    @requires_provider
    def test_filter_config_properties(self, provider):
        """Test filtering by configuration properties"""
        n_qubits = 20 if self.using_ibmq_credentials else 5

        filtered_backends = provider.backends(n_qubits=n_qubits, local=False)
        self.assertTrue(filtered_backends)

    @requires_provider
    def test_filter_status_dict(self, provider):
        """Test filtering by dictionary of mixed status/configuration properties"""
        filtered_backends = provider.backends(
            operational=True,  # from status
            local=False, simulator=True)  # from configuration

        self.assertTrue(filtered_backends)

    @requires_provider
    def test_filter_config_callable(self, provider):
        """Test filtering by lambda function on configuration properties"""
        filtered_backends = provider.backends(
            filters=lambda x: (not x.configuration().simulator
                               and x.configuration().n_qubits >= 5))
        self.assertTrue(filtered_backends)

    @requires_provider
    def test_filter_least_busy(self, provider):
        """Test filtering by least busy function"""
        backends = provider.backends()
        filtered_backends = least_busy(backends)
        self.assertTrue(filtered_backends)
