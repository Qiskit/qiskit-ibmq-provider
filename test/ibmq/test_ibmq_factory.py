# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for the IBMQFactory."""

from qiskit.providers.ibmq.exceptions import IBMQApiURLError
from qiskit.providers.ibmq.ibmqfactory import QX_AUTH_URL, IBMQFactory

from qiskit.test import QiskitTestCase

from ..decorators import requires_new_api_auth, requires_qe_access

API1_URL = 'https://quantumexperience.ng.bluemix.net/api'
API2_URL = 'https://api.quantum-computing.ibm.com/api'


class TestIBMQClientAccounts(QiskitTestCase):
    """Tests for IBMQConnector."""

    @requires_qe_access
    @requires_new_api_auth
    def test_auth_url(self, qe_token, qe_url):
        """Test enabling an API 2 auth account."""
        qe_url = QX_AUTH_URL

        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

    def test_non_auth_url(self):
        """Test enabling an API 2 non-auth account."""
        qe_token = 'invalid'
        qe_url = API2_URL

        with self.assertRaises(IBMQApiURLError) as context_manager:
            ibmq = IBMQFactory()
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('authentication URL', str(context_manager.exception))

    def test_non_auth_url_with_hub(self):
        """Test enabling an API 2 non-auth account with h/g/p."""
        qe_token = 'invalid'
        qe_url = API2_URL + '/Hubs/X/Groups/Y/Projects/Z'

        with self.assertRaises(IBMQApiURLError) as context_manager:
            ibmq = IBMQFactory()
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('authentication URL', str(context_manager.exception))
