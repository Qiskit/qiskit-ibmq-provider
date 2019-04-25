# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Custom TestCase for IBM Q Provider."""

from qiskit.test.providers import ProviderTestCase
from qiskit.providers.ibmq import IBMQ
from qiskit.providers.ibmq.ibmqprovider import IBMQProvider
from qiskit.test import requires_qe_access


class IBMQProviderTestCase(ProviderTestCase):
    """
    Specialization for IBM QE
    """
    provider_cls = IBMQProvider
