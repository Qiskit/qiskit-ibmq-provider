# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Custom TestCase for IBM Q Provider."""

from unittest import SkipTest

from qiskit.test.providers import BackendTestCase
from qiskit.providers.ibmq import IBMQ
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.test import requires_qe_access


class IBMQBackendTestCase(BackendTestCase):
    """
    Specialization for IBM Q Backends
    https://github.com/Qiskit/qiskit-ibmq-provider/issues/52
    Because the testing of backends from IBMQ is testing of instanced
    objects, we will not instance from a backend class, we will use the
    extant instances returned by IBMQ.backends() to dynamically create
    test classes and run the tests. The reason for dynamic class creation
    is to fill in backend_instance as class variable, straying the least from
    the BackendTestCase pattern.
    """
    backend_cls = None
    backend_instance = None

    def setUp(self):
        super().setUp()

    @classmethod
    def setUpClass(cls):
        if cls is IBMQBackendTestCase:
            raise SkipTest('Skipping base class tests')
        super().setUpClass()

    def __init__(self, backend_instance=None):
        if backend_instance:
            self.backend_instance = backend_instance
            self.backend_cls = type(self.backend_instance)

    def _get_backend(self):
        """Return an instance of a Provider.
        In the case of IBMQ Backends, we return an instance we received
        from IBMQ.backends() rather that try to instance the class ourselves.
        """
        return self.backend_instance
