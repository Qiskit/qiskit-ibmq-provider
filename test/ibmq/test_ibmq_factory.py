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
import os
import warnings
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from unittest import skipIf

from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.ibmq.credentials import configrc
from qiskit.providers.ibmq.exceptions import IBMQAccountError, IBMQApiUrlError
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory
from qiskit.providers.ibmq.ibmqprovider import IBMQProvider

from qiskit.test import QiskitTestCase

from ..decorators import (requires_qe_access,
                          requires_new_api_auth,
                          requires_classic_api)


API1_URL = 'https://quantumexperience.ng.bluemix.net/api'
API2_URL = 'https://api.quantum-computing.ibm.com/api'
AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'


class TestIBMQClientAccounts(QiskitTestCase):
    """Tests for IBMQConnector."""

    @classmethod
    def setUpClass(cls):
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

    @requires_qe_access
    @requires_new_api_auth
    def test_auth_url(self, qe_token, qe_url):
        """Test login into an API 2 auth account."""
        ibmq = IBMQFactory()
        provider = ibmq.enable_account(qe_token, qe_url)
        self.assertIsInstance(provider, AccountProvider)

    @requires_qe_access
    @requires_classic_api
    def test_api1_url(self, qe_token, qe_url):
        """Test login into an API 1 auth account."""
        ibmq = IBMQFactory()
        provider = ibmq.enable_account(qe_token, qe_url)
        self.assertIsInstance(provider, IBMQProvider)

    def test_non_auth_url(self):
        """Test login into an API 2 non-auth account."""
        qe_token = 'invalid'
        qe_url = API2_URL

        with self.assertRaises(IBMQApiUrlError) as context_manager:
            ibmq = IBMQFactory()
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('authentication URL', str(context_manager.exception))

    def test_non_auth_url_with_hub(self):
        """Test login into an API 2 non-auth account with h/g/p."""
        qe_token = 'invalid'
        qe_url = API2_URL + '/Hubs/X/Groups/Y/Projects/Z'

        with self.assertRaises(IBMQApiUrlError) as context_manager:
            ibmq = IBMQFactory()
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('authentication URL', str(context_manager.exception))

    @requires_qe_access
    @requires_new_api_auth
    def test_api2_after_api2(self, qe_token, qe_url):
        """Test login into an already logged-in account."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with self.assertRaises(IBMQAccountError) as context_manager:
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('already', str(context_manager.exception))

    @requires_qe_access
    @requires_new_api_auth
    def test_api1_after_api2(self, qe_token, qe_url):
        """Test login into API 1 during an already logged-in API 2 account."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with self.assertRaises(IBMQAccountError) as context_manager:
            qe_token_api1 = 'invalid'
            qe_url_api1 = API1_URL
            ibmq.enable_account(qe_token_api1, qe_url_api1)

        self.assertIn('already', str(context_manager.exception))

    @requires_qe_access
    @requires_classic_api
    def test_api2_after_api1(self, qe_token, qe_url):
        """Test login into API 2 during an already logged-in API 1 account."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with self.assertRaises(IBMQAccountError) as context_manager:
            qe_token_api2 = 'invalid'
            qe_url_api2 = AUTH_URL
            ibmq.enable_account(qe_token_api2, qe_url_api2)

        self.assertIn('already', str(context_manager.exception))

    @requires_qe_access
    @requires_classic_api
    def test_api1_accounts_compatibility(self, qe_token, qe_url):
        """Test backward compatibility for IBMQProvider account methods."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with warnings.catch_warnings(record=True) as w:
            accounts = ibmq.active_accounts()[0]
            self.assertEqual(accounts['token'], qe_token)
            self.assertEqual(accounts['url'], qe_url)

            ibmq.disable_accounts()
            self.assertEqual(len(ibmq.active_accounts()), 0)
            self.assertEqual(len(w), 3)
            for warn in w:
                self.assertTrue(issubclass(warn.category, DeprecationWarning))

    @requires_qe_access
    @requires_classic_api
    @skipIf(os.name == 'nt', 'Test not supported in Windows')
    def test_api1_qiskitrc_compatibility(self, qe_token, qe_url):
        """Test backward compatibility for IBMQProvider qiskitrc related methods."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with warnings.catch_warnings(record=True) as w:
            with custom_qiskitrc():
                ibmq.save_account(token=qe_token, url=qe_url)
                accounts = ibmq.stored_accounts()[0]
                self.assertEqual(accounts['token'], qe_token)
                self.assertEqual(accounts['url'], qe_url)
                ibmq.delete_accounts()
                self.assertEqual(len(ibmq.stored_accounts()), 0)

            self.assertEqual(len(w), 4)
            for warn in w:
                self.assertTrue(issubclass(warn.category, DeprecationWarning))

    @requires_qe_access
    @requires_classic_api
    def test_api1_backends_compatibility(self, qe_token, qe_url):
        """Test backward compatibility for IBMQProvider backends method."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        ibmq_provider = IBMQProvider()
        ibmq_provider.enable_account(qe_token, qe_url)
        ibmq_provider_backend_names = [b.name() for b in ibmq_provider.backends()]

        with warnings.catch_warnings(record=True) as w:
            ibmq_backend_names = [b.name() for b in ibmq.backends()]
            self.assertEqual(set(ibmq_backend_names), set(ibmq_provider_backend_names))
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))


@contextmanager
def custom_qiskitrc(contents=b''):
    """Context manager that uses a temporary qiskitrc."""
    # Create a temporary file with the contents.
    tmp_file = NamedTemporaryFile()
    tmp_file.write(contents)
    tmp_file.flush()

    # Temporarily modify the default location of the qiskitrc file.
    default_qiskitrc_file_original = configrc.DEFAULT_QISKITRC_FILE
    configrc.DEFAULT_QISKITRC_FILE = tmp_file.name
    yield

    # Delete the temporary file and restore the default location.
    tmp_file.close()
    configrc.DEFAULT_QISKITRC_FILE = default_qiskitrc_file_original
