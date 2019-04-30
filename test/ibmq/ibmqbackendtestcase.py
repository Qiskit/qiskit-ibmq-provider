# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Custom TestCase for IBM Q Provider."""

from unittest import SkipTest

from qiskit.test.providers import BackendTestCase


class IBMQBackendTestCase(BackendTestCase):
    """Specialization for IBM Q Backends
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

    @classmethod
    def setUpClass(cls):
        if cls is IBMQBackendTestCase:
            raise SkipTest('Skipping base class tests')
        super().setUpClass()

    def _get_backend(self):
        """Return an instance of a Backend.
        In the case of IBMQ Backends, we return an instance we received
        from IBMQ.backends() rather that try to instance the class ourselves.
        """
        return self.backend_instance
