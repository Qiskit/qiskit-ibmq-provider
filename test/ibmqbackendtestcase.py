# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Custom TestCase for IBM Q Provider."""

from qiskit.test.providers import BackendTestCase


class IBMQBackendTestCase(BackendTestCase):
    """
    Subclass of Qiskit BackendTestCase per standard Qiskit Testing regimen
    """
