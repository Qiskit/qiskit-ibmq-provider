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
        """Test `IBMQBackend.jobs` signature is similar to `IBMQBackendService.jobs`

        The signature of `IBMQBackend.jobs` is similar to the signature of
        `IBMQBackendService.jobs` if its parameter list is a subset of the
        parameter list of `IBMQBackendService.jobs`.
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

        # Ensure `IBMQBackend.jobs` does not have any additional parameters.
        additional_params = backend_jobs_params - backend_service_jobs_params
        self.assertTrue((len(additional_params) == 0),
                        "IBMQBackend.jobs does not match the signature of "
                        "IBMQBackendService.jobs. IBMQBackend.jobs has "
                        "the additional parameter(s): {}"
                        .format(additional_params))

        # Ensure `IBMQBackend.jobs` is not missing any parameters.
        missing_params = backend_service_jobs_params - backend_jobs_params
        self.assertEqual(acceptable_differing_params, missing_params,
                         "IBMQBackend.jobs does not match the signature of "
                         "IBMQBackendService.jobs. IBMQBackend.jobs is "
                         "missing the parameter(s): {}"
                         .format(missing_params - acceptable_differing_params))
