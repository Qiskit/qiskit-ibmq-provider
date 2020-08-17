# -*- coding: utf-8 -*-

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
from datetime import timedelta

from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.ibmqbackendservice import IBMQBackendService

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_device, requires_provider


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
                else:
                    self.assertIsNone(defaults)

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
        before_start = reserv.start_datetime - timedelta(seconds=30)
        # after_start = reserv.start_datetime + timedelta(seconds=30)
        before_end = reserv.end_datetime - timedelta(seconds=30)
        after_end = reserv.end_datetime + timedelta(seconds=30)

        # Each tuple contains the start datetime, end datetime, whether a
        # reservation should be found, and the description.
        # TODO re-enable sub test 3 after API is updated.
        sub_tests = [
            (before_start, after_end, True, 'before start, after end'),
            (before_start, before_end, True, 'before start, before end'),
            # (after_start, before_end, True, 'after start, before end'),
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


class TestIBMQBackendService(IBMQTestCase):
    """Test ibmqbackendservice module."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        cls.provider = provider

    def test_my_reservations(self):
        """Test my_reservations method"""
        reservations = self.provider.backends.my_reservations()
        for reserv in reservations:
            print(reserv)
            for attr in reserv.__dict__:
                self.assertIsNotNone(
                    getattr(reserv, attr),
                    "Reservation {} is missing attribute {}".format(reserv, attr))
