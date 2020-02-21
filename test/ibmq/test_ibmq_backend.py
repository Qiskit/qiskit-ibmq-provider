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


class TestIBMQBackend(IBMQTestCase):
    """Test ibmqbackend module."""

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
