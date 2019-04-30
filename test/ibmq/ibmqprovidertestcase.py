# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""
    Specialization for IBM Q Providers.
    https://github.com/Qiskit/qiskit-ibmq-provider/issues/52
    Because the testing of backends from IBMQ is testing of instanced
    objects, we will not instance from a backend class, we will use the
    extant instances returned by IBMQ.backends() to dynamically create
    test classes and run the tests. The reason for dynamic class creation
    is to fill in backend_instance as class variable, straying the least from
    the BackendTestCase pattern.
    """

from unittest import SkipTest

from qiskit.test.providers import ProviderTestCase
from qiskit.providers.ibmq import IBMQ
from qiskit.providers.ibmq.ibmqprovider import IBMQProvider
from qiskit.test import requires_qe_access

from .ibmqbackendtestcase import IBMQBackendTestCase


class IBMQProviderTestCase(ProviderTestCase):
    """
    Specialization for IBM QE
    """
    provider_cls = IBMQProvider

    def setUp(self):
        super().setUp()

    @classmethod
    def setUpClass(cls):
        if cls is IBMQProviderTestCase:
            raise SkipTest('Skipping base class tests')
        super().setUpClass()

    def test_backends(self):
        """Test the provider has backends."""
        raise SkipTest(
            'Test_backends is subsumed in TestIBMQBackends.test_backends_IBMQBackendTestCase'
        )

    def test_get_backend(self):
        """Test getting a backend from the provider."""
        raise SkipTest(
            'Skip test_get_backend as subsumed in TestIBMQBackends test cases')
