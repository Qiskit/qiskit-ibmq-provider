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

"""Tests for random number services."""

from qiskit.providers.ibmq.random.cqcextractor import CQCExtractor
from qiskit.providers.ibmq.random.utils import bitarray_to_bytes

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider


class TestRandom(IBMQTestCase):
    """Tests for random number services."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.provider.random._random_client = FakeRandomClient()
        cls.provider.random._initialized = False

    def test_list_random_services(self):
        """Test listing random number services."""
        random_services = self.provider.random.services()
        cqc_found = False
        for service in random_services:
            if service.name == 'cqc_extractor':
                self.assertIsInstance(service, CQCExtractor)
                cqc_found = True
        self.assertTrue(cqc_found, "CQC extractor not found.")

    def test_get_random_service(self):
        """Test retrieving a specific service."""
        self.assertIsInstance(self.provider.random.get_service('cqc_extractor'), CQCExtractor)
        self.assertIsInstance(self.provider.random.cqc_extractor, CQCExtractor)

    def test_extractor_run(self):
        """Test running an extractor."""
        extractor = self.provider.random.get_service('cqc_extractor')
        some_int = 42
        some_byte = some_int.to_bytes(1, 'big')
        output = extractor.run(5, 3, some_byte, some_byte, 0, 0)
        self.assertEqual(output, [0, 1, 0])


class FakeRandomClient:
    """Client to return fake extractor data."""

    def list_services(self):
        """Return fake random services."""
        return [{'name': 'cqc', 'extractors': ['fake_ext1', 'fake_ext2']}]

    def extract(self, *args, **kwargs):
        """Return fake random output."""
        # pylint: disable=unused-argument
        return bitarray_to_bytes([0, 1, 0])
