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
from ..decorators import requires_provider, requires_device


class TestBackendFilters(IBMQTestCase):
    """Qiskit Backend Filtering Tests."""

    @requires_device
    def test_filter_config_properties(self, backend):
        """Test filtering by configuration properties."""
        # Use the default backend as a reference for the filter.
        provider = backend._provider
        n_qubits = backend.configuration().n_qubits

        filtered_backends = provider.backends(n_qubits=n_qubits, local=False)

        self.assertTrue(filtered_backends)
        for filtered_backend in filtered_backends:
            with self.subTest(filtered_backend=filtered_backend):
                self.assertEqual(n_qubits, filtered_backend.configuration().n_qubits)
                self.assertFalse(filtered_backend.configuration().local)

    @requires_provider
    def test_filter_status_dict(self, provider):
        """Test filtering by dictionary of mixed status/configuration properties."""
        filtered_backends = provider.backends(
            operational=True,  # from status
            local=False, simulator=True)  # from configuration

        self.assertTrue(filtered_backends)
        for backend in filtered_backends:
            with self.subTest(backend=backend):
                self.assertTrue(backend.status().operational)
                self.assertFalse(backend.configuration().local)
                self.assertTrue(backend.configuration().simulator)

    @requires_provider
    def test_filter_config_callable(self, provider):
        """Test filtering by lambda function on configuration properties."""
        filtered_backends = provider.backends(
            filters=lambda x: (not x.configuration().simulator
                               and x.configuration().n_qubits >= 5))

        self.assertTrue(filtered_backends)
        for backend in filtered_backends:
            with self.subTest(backend=backend):
                self.assertFalse(backend.configuration().simulator)
                self.assertGreaterEqual(backend.configuration().n_qubits, 5)

    @requires_provider
    def test_filter_least_busy(self, provider):
        """Test filtering by least busy function."""
        backends = provider.backends()
        least_busy_backend = least_busy(backends)
        self.assertTrue(least_busy_backend)
