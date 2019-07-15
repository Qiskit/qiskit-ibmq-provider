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
from qiskit.providers.ibmq.api_v2.exceptions import RequestsApiError
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

    @requires_qe_access
    @requires_new_api_auth
    def test_pass_unreachable_proxy(self, qe_token, qe_url):
        """Test using an unreachable proxy while enabling an account."""
        proxies = {
            'urls': {
                'http': 'http://user:password@127.0.0.1:5678',
                'https': 'https://user:password@127.0.0.1:5678'
            }
        }
        ibmq = IBMQFactory()
        with self.assertRaises(RequestsApiError) as context_manager:
            ibmq.enable_account(qe_token, qe_url, proxies=proxies)
        self.assertIn('ProxyError', str(context_manager.exception))


class TestIBMQFactoryDeprecation(IBMQTestCase):
    """Tests for IBMQFactory deprecated methods."""

    @classmethod
    def setUpClass(cls):
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")

    @requires_qe_access
    @requires_classic_api
    def test_api1_disable_accounts(self, qe_token, qe_url):
        """Test backward compatibility for API 1 disable_accounts()."""
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

    @skipIf(os.name == 'nt', 'Test not supported in Windows')
    @requires_qe_access
    @requires_classic_api
    def test_api1_load_accounts(self, qe_token, qe_url):
        """Test backward compatibility for API 1 load_accounts()."""
        ibmq_factory = IBMQFactory()

        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            with self.assertWarns(DeprecationWarning):
                ibmq_factory.save_account(qe_token, qe_url)

            with self.assertWarns(DeprecationWarning):
                ibmq_factory.load_accounts()

        self.assertEqual(
            list(ibmq_factory._v1_provider._accounts.values())[0].credentials.token,
            qe_token)

    @skipIf(os.name == 'nt', 'Test not supported in Windows')
    def test_api1_delete_accounts(self):
        """Test backward compatibility for API 1 delete_accounts()."""
        ibmq_provider = IBMQProvider()
        ibmq_factory = IBMQFactory()

        with custom_qiskitrc():
            ibmq_provider.save_account('QISKITRC_TOKEN', url=API1_URL)

            with self.assertWarns(DeprecationWarning):
                ibmq_factory.delete_accounts()
            with self.assertWarns(DeprecationWarning):
                stored_accounts = ibmq_factory.stored_accounts()

        self.assertEqual(len(stored_accounts), 0)

    @requires_qe_access
    @requires_classic_api
    def test_api1_backends(self, qe_token, qe_url):
        """Test backward compatibility for API 1 backends()."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        ibmq_provider = IBMQProvider()
        ibmq_provider.enable_account(qe_token, qe_url)
        ibmq_provider_backend_names = [b.name() for b in ibmq_provider.backends()]

        with self.assertWarns(DeprecationWarning):
            ibmq_backend_names = [b.name() for b in ibmq.backends()]

        self.assertEqual(set(ibmq_backend_names),
                         set(ibmq_provider_backend_names))

    @requires_qe_access
    @requires_classic_api
    def test_api1_get_backend(self, qe_token, qe_url):
        """Test backward compatibility for API 1 get_backend()."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        ibmq_provider = IBMQProvider()
        ibmq_provider.enable_account(qe_token, qe_url)
        backend = ibmq_provider.backends()[0]

        with self.assertWarns(DeprecationWarning):
            ibmq_backend = ibmq.get_backend(backend.name())

        self.assertEqual(backend.name(), ibmq_backend.name())


@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestIBMQFactoryAccounts(IBMQTestCase):
    """Tests for the IBMQ account handling."""

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
        """Test loading an API 2 account."""
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
        """Test loading an API 1 account."""
        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            self.provider.save_account(self.v1_token, url=API1_URL)
            with self.assertRaises(IBMQAccountError):
                self.factory.load_account()

    @requires_qe_access
    @requires_new_api_auth
    def test_disable_account_v2(self, qe_token, qe_url):
        """Test disabling an API 2 account """
        self.factory.enable_account(qe_token, qe_url)
        self.factory.disable_account()
        self.assertIsNone(self.factory._credentials)

    @requires_qe_access
    @requires_classic_api
    def test_disable_account_v1(self, qe_token, qe_url):
        """Test disabling an API 1 account """
        self.factory.enable_account(qe_token, qe_url)
        with self.assertRaises(IBMQAccountError):
            self.factory.disable_account()

    @requires_qe_access
    @requires_new_api_auth
    def test_active_account_v2(self, qe_token, qe_url):
        """Test active_account for an API 2 account """
        self.assertIsNone(self.factory.active_account())

        self.factory.enable_account(qe_token, qe_url)
        active_account = self.factory.active_account()
        self.assertIsNotNone(active_account)
        self.assertEqual(active_account['token'], qe_token)
        self.assertEqual(active_account['url'], qe_url)

    @requires_qe_access
    @requires_classic_api
    def test_active_account_v1(self, qe_token, qe_url):
        """Test active_account for an API 1 account """
        self.factory.enable_account(qe_token, qe_url)
        with self.assertRaises(IBMQAccountError):
            self.factory.active_account()


class TestIBMQFactoryProvider(IBMQTestCase):
    """Tests for IBMQFactory provider related methods."""

    @requires_qe_access
    @requires_new_api_auth
    def _get_provider(self, qe_token=None, qe_url=None):
        return self.ibmq.enable_account(qe_token, qe_url)

    def setUp(self):
        super().setUp()

        self.ibmq = IBMQFactory()
        self.provider = self._get_provider()
        self.credentials = self.provider.credentials

    def test_get_provider(self):
        """Test get single provider."""
        provider = self.ibmq.get_provider(
            hub=self.credentials.hub,
            group=self.credentials.group,
            project=self.credentials.project)
        self.assertEqual(self.provider, provider)

    def test_providers_with_filter(self):
        """Test providers() with a filter."""
        provider = self.ibmq.providers(
            hub=self.credentials.hub,
            group=self.credentials.group,
            project=self.credentials.project)[0]
        self.assertEqual(self.provider, provider)

    def test_providers_no_filter(self):
        """Test providers() without a filter."""
        providers = self.ibmq.providers()
        self.assertIn(self.provider, providers)
