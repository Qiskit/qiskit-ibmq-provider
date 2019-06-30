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
from unittest import skipIf

from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.ibmq.exceptions import IBMQAccountError, IBMQApiUrlError
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory, QX_AUTH_URL
from qiskit.providers.ibmq.ibmqprovider import IBMQProvider

from ..ibmqtestcase import IBMQTestCase
from ..decorators import (requires_qe_access,
                          requires_new_api_auth,
                          requires_classic_api)
from ..contextmanagers import (custom_qiskitrc, no_file, no_envs,
                               CREDENTIAL_ENV_VARS)


API1_URL = 'https://quantumexperience.ng.bluemix.net/api'
API2_URL = 'https://api.quantum-computing.ibm.com/api'
AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'


class TestIBMQFactoryEnableAccount(IBMQTestCase):
    """Tests for IBMQFactory `enable_account()`."""

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


class TestIBMQFactoryAccountsDeprecation(IBMQTestCase):
    """Tests for IBMQFactory account-related deprecated methods."""

    @classmethod
    def setUpClass(cls):
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

    @requires_qe_access
    @requires_classic_api
    def test_api1_accounts_compatibility(self, qe_token, qe_url):
        """Test backward compatibility for IBMQProvider account methods."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with warnings.catch_warnings(record=True) as warnings_list:
            accounts = ibmq.active_accounts()[0]
            self.assertEqual(accounts['token'], qe_token)
            self.assertEqual(accounts['url'], qe_url)
            ibmq.disable_accounts()
            number_of_accounts = len(ibmq.active_accounts())

        self.assertEqual(number_of_accounts, 0)
        self.assertEqual(len(warnings_list), 3)
        for warn in warnings_list:
            self.assertTrue(issubclass(warn.category, DeprecationWarning))

    @requires_qe_access
    @requires_classic_api
    def test_backends(self, qe_token, qe_url):
        """Test backward compatibility for IBMQProvider backends method."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        ibmq_provider = IBMQProvider()
        ibmq_provider.enable_account(qe_token, qe_url)
        ibmq_provider_backend_names = [b.name() for b in ibmq_provider.backends()]

        with warnings.catch_warnings(record=True) as warnings_list:
            ibmq_backend_names = [b.name() for b in ibmq.backends()]

        self.assertEqual(set(ibmq_backend_names),
                         set(ibmq_provider_backend_names))
        self.assertTrue(issubclass(warnings_list[0].category,
                                   DeprecationWarning))


@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestIBMQFactoryAccountsOnDisk(IBMQTestCase):
    """Tests for the IBMQ account handling on disk."""

    @classmethod
    def setUpClass(cls):
        cls.v2_token = 'API2_TOKEN'
        cls.v1_token = 'API1_TOKEN'

    def setUp(self):
        super().setUp()

        # Reference for saving accounts.
        self.factory = IBMQFactory()
        self.provider = IBMQProvider()

    def test_save_account_v2(self):
        """Test saving an API 2 account."""
        with custom_qiskitrc():
            self.factory.save_account(self.v2_token, url=AUTH_URL)
            stored_cred = self.factory.stored_account()

        self.assertEqual(stored_cred['token'], self.v2_token)
        self.assertEqual(stored_cred['url'], AUTH_URL)

    def test_save_account_v1(self):
        """Test saving an API 1 account."""
        with custom_qiskitrc():
            with self.assertRaises(IBMQAccountError):
                self.factory.save_account(self.v1_token, url=API1_URL)

    def test_stored_account_v1(self):
        """Test listing a stored API 1 account."""
        with custom_qiskitrc():
            self.provider.save_account(self.v1_token, url=API1_URL)
            with self.assertRaises(IBMQAccountError):
                self.factory.stored_account()

    def test_delete_account_v2(self):
        """Test deleting an API 2 account."""
        with custom_qiskitrc():
            self.factory.save_account(self.v2_token, url=AUTH_URL)
            self.factory.delete_account()
            stored_cred = self.factory.stored_account()

        self.assertEqual(len(stored_cred), 0)

    def test_delete_account_v1(self):
        """Test deleting an API 1 account."""
        with custom_qiskitrc():
            self.provider.save_account(self.v1_token, url=API1_URL)
            with self.assertRaises(IBMQAccountError):
                self.factory.delete_account()

    @requires_qe_access
    @requires_new_api_auth
    def test_load_account_v2(self, qe_token, qe_url):
        """Test saving an API 2 account."""
        if qe_url != QX_AUTH_URL:
            # .save_account() expects an auth 2 production URL.
            self.skipTest('Test requires production auth URL')

        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            self.factory.save_account(qe_token, url=qe_url)
            self.factory.load_account()

        self.assertEqual(self.factory._credentials.token, qe_token)
        self.assertEqual(self.factory._credentials.url, qe_url)
        self.assertEqual(self.factory._v1_provider._accounts, {})

    def test_load_account_v1(self):
        """Test saving an API 1 account."""
        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            self.provider.save_account(self.v1_token, url=API1_URL)
            with self.assertRaises(IBMQAccountError):
                self.factory.load_account()
