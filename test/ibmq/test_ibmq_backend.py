# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBMQBackend Test."""

from inspect import getfullargspec
from datetime import timedelta, datetime
import warnings
from unittest import SkipTest
from unittest.mock import patch

from qiskit import QuantumCircuit, transpile, assemble
from qiskit.providers.models import QasmBackendConfiguration
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.ibmqbackendservice import IBMQBackendService

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_device, requires_provider
from ..utils import get_pulse_schedule, cancel_job


class TestIBMQBackend(IBMQTestCase):
    """Test ibmqbackend module."""

    @classmethod
    @requires_device
    def setUpClass(cls, backend):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.backend = backend

    def test_backend_jobs_signature(self):
        """Test ``IBMQBackend.jobs()`` signature is similar to ``IBMQBackendService.jobs()``.

        Ensure that the parameter list of ``IBMQBackend.jobs()`` is a subset of that
        of ``IBMQBackendService.jobs()``.
        """
        # Acceptable params `IBMQBackendService.jobs` has that `IBMQBackend.jobs` does not.
        acceptable_differing_params = {'backend_name'}

        # Retrieve parameter lists for both classes.
        backend_jobs_params = set(
            getattr(getfullargspec(IBMQBackend.jobs), 'args', [])
        )
        backend_service_jobs_params = set(
            getattr(getfullargspec(IBMQBackendService.jobs), 'args', [])
        )

        # Ensure parameter lists not empty
        self.assertTrue(backend_jobs_params)
        self.assertTrue(backend_service_jobs_params)

        # Remove acceptable params from `IBMQBackendService.jobs`.
        backend_service_jobs_params.difference_update(acceptable_differing_params)

        # Ensure method signatures are similar, other than the acceptable differences.
        self.assertEqual(backend_service_jobs_params, backend_jobs_params)

    def test_backend_status(self):
        """Check the status of a real chip."""
        self.assertTrue(self.backend.status().operational)

    def test_backend_properties(self):
        """Check the properties of calibration of a real chip."""
        self.assertIsNotNone(self.backend.properties())

    def test_backend_job_limit(self):
        """Check the backend job limits of a real backend."""
        job_limit = self.backend.job_limit()
        self.assertIsNotNone(job_limit)
        self.assertIsNotNone(job_limit.active_jobs)
        if job_limit.maximum_jobs:
            self.assertGreater(job_limit.maximum_jobs, 0)

    def test_backend_pulse_defaults(self):
        """Check the backend pulse defaults of each backend."""
        provider = self.backend.provider()
        for backend in provider.backends():
            with self.subTest(backend_name=backend.name()):
                defaults = backend.defaults()
                if backend.configuration().open_pulse:
                    self.assertIsNotNone(defaults)

    def test_backend_reservations(self):
        """Test backend reservations."""
        provider = self.backend.provider()
        backend = reservations = None
        for backend in provider.backends(simulator=False, operational=True):
            reservations = backend.reservations()
            if reservations:
                break

        if not reservations:
            self.skipTest("Test case requires reservations.")

        reserv = reservations[0]
        self.assertGreater(reserv.duration, 0)
        self.assertTrue(reserv.mode)
        before_start = reserv.start_datetime - timedelta(seconds=30)
        after_start = reserv.start_datetime + timedelta(seconds=30)
        before_end = reserv.end_datetime - timedelta(seconds=30)
        after_end = reserv.end_datetime + timedelta(seconds=30)

        # Each tuple contains the start datetime, end datetime, whether a
        # reservation should be found, and the description.
        sub_tests = [
            (before_start, after_end, True, 'before start, after end'),
            (before_start, before_end, True, 'before start, before end'),
            (after_start, before_end, True, 'after start, before end'),
            (before_start, None, True, 'before start, None'),
            (None, after_end, True, 'None, after end'),
            (before_start, before_start, False, 'before start, before start'),
            (after_end, after_end, False, 'after end, after end')
        ]

        for start_dt, end_dt, should_find, name in sub_tests:
            with self.subTest(name=name):
                f_reservs = backend.reservations(start_datetime=start_dt, end_datetime=end_dt)
                found = False
                for f_reserv in f_reservs:
                    if f_reserv == reserv:
                        found = True
                        break
                self.assertEqual(
                    found, should_find,
                    "Reservation {} found={}, used start datetime {}, end datetime {}".format(
                        reserv, found, start_dt, end_dt))

    def test_run_qobj(self):
        """Test running a Qobj."""
        qobj = assemble(transpile(ReferenceCircuits.bell(), self.backend), self.backend)
        with self.assertWarns(DeprecationWarning):
            job = self.backend.run(qobj)
        cancel_job(job)

    def test_backend_options(self):
        """Test backend options."""
        provider = self.backend.provider()
        backends = provider.backends(open_pulse=True, operational=True)
        if not backends:
            raise SkipTest('Skipping pulse test since no pulse backend found.')

        backend = backends[0]
        backend.options.shots = 2048
        backend.set_options(qubit_lo_freq=[4.9e9, 5.0e9],
                            meas_lo_freq=[6.5e9, 6.6e9],
                            meas_level=2)
        job = backend.run(get_pulse_schedule(backend), meas_level=1, foo='foo')
        qobj = backend.retrieve_job(job.job_id()).qobj()  # Use retrieved Qobj.
        self.assertEqual(qobj.config.shots, 2048)
        # Qobj config freq is in GHz.
        self.assertEqual(qobj.config.qubit_lo_freq, [4.9, 5.0])
        self.assertEqual(qobj.config.meas_lo_freq, [6.5, 6.6])
        self.assertEqual(qobj.config.meas_level, 1)
        self.assertEqual(qobj.config.foo, 'foo')
        cancel_job(job)

    def test_sim_backend_options(self):
        """Test simulator backend options."""
        provider = self.backend.provider()
        backend = provider.get_backend('ibmq_qasm_simulator')
        backend.options.shots = 2048
        backend.set_options(memory=True)
        job = backend.run(ReferenceCircuits.bell(), shots=1024, foo='foo')
        qobj = backend.retrieve_job(job.job_id()).qobj()
        self.assertEqual(qobj.config.shots, 1024)
        self.assertTrue(qobj.config.memory)
        self.assertEqual(qobj.config.foo, 'foo')

    def test_deprecate_id_instruction(self):
        """Test replacement of 'id' Instructions with 'Delay' instructions."""

        circuit_with_id = QuantumCircuit(2)
        circuit_with_id.id(0)
        circuit_with_id.id(0)
        circuit_with_id.id(1)

        config = QasmBackendConfiguration(
            basis_gates=['id'],
            supported_instructions=['delay'],
            dt=0.25,
            backend_name='test',
            backend_version=0.0,
            n_qubits=1,
            gates=[],
            local=False,
            simulator=False,
            conditional=False,
            open_pulse=False,
            memory=False,
            max_shots=1,
            coupling_map=None,
        )

        with patch.object(self.backend, 'configuration', return_value=config):
            with self.assertWarnsRegex(DeprecationWarning, r"'id' instruction"):
                self.backend._deprecate_id_instruction(circuit_with_id)

            self.assertEqual(circuit_with_id.count_ops(), {'delay': 3})


class TestIBMQBackendService(IBMQTestCase):
    """Test ibmqbackendservice module."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.last_week = datetime.now() - timedelta(days=7)

    def test_my_reservations(self):
        """Test my_reservations method"""
        reservations = self.provider.backend.my_reservations()
        for reserv in reservations:
            for attr in reserv.__dict__:
                self.assertIsNotNone(
                    getattr(reserv, attr),
                    "Reservation {} is missing attribute {}".format(reserv, attr))

    def test_deprecated_service(self):
        """Test deprecated backend service module."""
        ref_job = self.provider.backend.jobs(limit=10, end_datetime=self.last_week)[-1]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", category=DeprecationWarning)
            self.provider.backends()
            self.assertEqual(len(w), 0, "DeprecationWarning issued for provider.backends()")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", category=DeprecationWarning)
            _ = self.provider.backends.ibmq_qasm_simulator
            self.provider.backends.retrieve_job(ref_job.job_id())
            self.provider.backends.jobs(limit=1, end_datetime=self.last_week)
            self.provider.backends.my_reservations()
            self.assertGreaterEqual(len(w), 1)
