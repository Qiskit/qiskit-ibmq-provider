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

from unittest import mock
from datetime import datetime

from dateutil import tz
from qiskit.providers.ibmq import least_busy
from qiskit.providers.ibmq import IBMQError

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider, requires_device


class TestBackendFilters(IBMQTestCase):
    """Qiskit Backend Filtering Tests."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider

    @requires_device
    def test_filter_config_properties(self, backend):
        """Test filtering by configuration properties."""
        # Use the default backend as a reference for the filter.
        provider = backend._provider
        n_qubits = backend.configuration().n_qubits

        filtered_backends = provider.backends(n_qubits=n_qubits, local=False)

        self.assertTrue(filtered_backends)
        for filtered_backend in filtered_backends[:5]:
            with self.subTest(filtered_backend=filtered_backend):
                self.assertEqual(n_qubits, filtered_backend.configuration().n_qubits)
                self.assertFalse(filtered_backend.configuration().local)

    def test_filter_status_dict(self):
        """Test filtering by dictionary of mixed status/configuration properties."""
        filtered_backends = self.provider.backends(
            operational=True,  # from status
            local=False, simulator=True)  # from configuration

        self.assertTrue(filtered_backends)
        for backend in filtered_backends[:5]:
            with self.subTest(backend=backend):
                self.assertTrue(backend.status().operational)
                self.assertFalse(backend.configuration().local)
                self.assertTrue(backend.configuration().simulator)

    def test_filter_config_callable(self):
        """Test filtering by lambda function on configuration properties."""
        filtered_backends = self.provider.backends(
            filters=lambda x: (not x.configuration().simulator
                               and x.configuration().n_qubits >= 5))

        self.assertTrue(filtered_backends)
        for backend in filtered_backends[:5]:
            with self.subTest(backend=backend):
                self.assertFalse(backend.configuration().simulator)
                self.assertGreaterEqual(backend.configuration().n_qubits, 5)

    def test_filter_least_busy(self):
        """Test filtering by least busy function."""
        backends = self.provider.backends()
        least_busy_backend = least_busy(backends)
        self.assertTrue(least_busy_backend)

    def test_filter_least_busy_reservation(self):
        """Test filtering by least busy function, with reservations."""
        backend = reservations = None
        for backend in self.provider.backends(simulator=False, operational=True,
                                              status_msg='active'):
            reservations = backend.reservations()
            if reservations:
                break

        if not reservations:
            self.skipTest("Test case requires reservations.")

        reserv = reservations[0]
        now = datetime.now(tz=tz.tzlocal())
        window = 60
        if reserv.start_datetime > now:
            window = (reserv.start_datetime - now).seconds * 60
        self.assertRaises(IBMQError, least_busy, [backend], window)

        self.assertEqual(least_busy([backend], None), backend)

        backs = [backend]
        for back in self.provider.backends(simulator=False, operational=True,
                                           status_msg='active'):
            if back.name() != backend.name():
                backs.append(back)
                break
        self.assertTrue(least_busy(backs, window))

    def test_filter_least_busy_paused(self):
        """Test filtering by least busy function, with paused backend."""
        backends = self.provider.backends()
        if len(backends) < 2:
            self.skipTest("Test needs at least 2 backends.")
        paused_backend = backends[0]
        paused_status = paused_backend.status()
        paused_status.status_msg = 'internal'
        paused_status.pending_jobs = 0
        paused_backend.status = mock.MagicMock(return_value=paused_status)

        least_busy_backend = least_busy(backends)
        self.assertTrue(least_busy_backend)
        self.assertNotEqual(least_busy_backend.name(), paused_backend.name())
        self.assertEqual(least_busy_backend.status().status_msg, 'active')

    def test_filter_min_num_qubits(self):
        """Test filtering by minimum number of qubits."""
        filtered_backends = self.provider.backends(
            min_num_qubits=5, simulator=False,
            filters=lambda b: b.configuration().quantum_volume >= 10)

        self.assertTrue(filtered_backends)
        for backend in filtered_backends[:5]:
            with self.subTest(backend=backend):
                self.assertGreaterEqual(backend.configuration().n_qubits, 5)
                self.assertTrue(backend.configuration().quantum_volume, 10)

    def test_filter_input_allowed(self):
        """Test filtering by input allowed"""
        subtests = ('job', ['job'], ['job', 'runtime'])

        for input_type in subtests:
            with self.subTest(input_type=input_type):
                filtered = self.provider.backends(input_allowed=input_type)
                self.assertTrue(filtered)
                if not isinstance(input_type, list):
                    input_type = [input_type]
                for backend in filtered[:5]:
                    self.assertTrue(set(input_type) <= set(backend.configuration().input_allowed))
