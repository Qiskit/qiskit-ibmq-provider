# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Backends Filtering Test."""

from qiskit.providers.ibmq import IBMQ, least_busy
from qiskit.test import QiskitTestCase, requires_qe_access


class TestBackendFilters(QiskitTestCase):
    """Qiskit Backend Filtering Tests."""

    @requires_qe_access
    def test_filter_config_properties(self, qe_token, qe_url):
        """Test filtering by configuration properties"""
        n_qubits = 20 if self.using_ibmq_credentials else 5

        IBMQ.enable_account(qe_token, qe_url)
        filtered_backends = IBMQ.backends(n_qubits=n_qubits, local=False)
        self.assertTrue(filtered_backends)

    @requires_qe_access
    def test_filter_status_dict(self, qe_token, qe_url):
        """Test filtering by dictionary of mixed status/configuration properties"""
        IBMQ.enable_account(qe_token, qe_url)
        filtered_backends = IBMQ.backends(
            operational=True,  # from status
            local=False, simulator=True)  # from configuration

        self.assertTrue(filtered_backends)

    @requires_qe_access
    def test_filter_config_callable(self, qe_token, qe_url):
        """Test filtering by lambda function on configuration properties"""
        IBMQ.enable_account(qe_token, qe_url)
        filtered_backends = IBMQ.backends(
            filters=lambda x: (not x.configuration().simulator
                               and x.configuration().n_qubits > 5))
        self.assertTrue(filtered_backends)

    @requires_qe_access
    def test_filter_least_busy(self, qe_token, qe_url):
        """Test filtering by least busy function"""
        IBMQ.enable_account(qe_token, qe_url)
        backends = IBMQ.backends()
        filtered_backends = least_busy(backends)
        self.assertTrue(filtered_backends)
