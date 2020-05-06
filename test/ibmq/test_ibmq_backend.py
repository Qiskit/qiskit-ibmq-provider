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

from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.ibmqbackendservice import IBMQBackendService

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_device


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
