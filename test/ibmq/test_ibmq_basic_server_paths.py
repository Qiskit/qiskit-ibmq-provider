# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests that hit all of the server paths with both public/premium providers."""

from qiskit.compiler import assemble, transpile
from qiskit.test.reference_circuits import ReferenceCircuits

from qiskit.providers.ibmq import least_busy
from ..decorators import requires_providers
from ..ibmqtestcase import IBMQTestCase


class TestIBMQBasicServerPaths(IBMQTestCase):
    """Test the basic server paths using both public/premium providers."""

    @classmethod
    @requires_providers
    def setUpClass(cls, providers):
        super().setUpClass()
        cls.providers = providers  # List[AccountProvider]
        cls._qc = ReferenceCircuits.bell()
        cls.seed = 73846087  # TODO: Change this after looking it up.

    def test_job_submission(self):
        """Test submitting a job."""
        for provider in self.providers:
            print(provider)
            with self.subTest(provider=provider):
                backend = least_busy(provider.backends())
                circuit = transpile(self._qc, backend, seed_transpiler=self.seed)
                qobj = assemble(circuit, backend, shots=1)
                job = backend.run(qobj, validate_qobj=True)

                # Fetch the results and qobj.
                result = job.result()
                qobj_downloaded = job.qobj()

                self.assertEqual(qobj_downloaded, qobj.to_dict())
                self.assertTrue(result.success)

