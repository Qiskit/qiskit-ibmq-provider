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

"""Tests for the IBMQFactory class."""

import os
from unittest import skipIf
from configparser import ConfigParser, ParsingError

from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.ibmq.api.exceptions import RequestsApiError
from qiskit.providers.ibmq.exceptions import (IBMQAccountError, IBMQAccountValueError,
                                              IBMQAccountCredentialsInvalidUrl,
                                              IBMQAccountCredentialsInvalidToken)
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory, QX_AUTH_URL
from qiskit.providers.ibmq.credentials.hubgroupproject import HubGroupProject

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_qe_access
from ..contextmanagers import (custom_qiskitrc, no_file, no_envs,
                               CREDENTIAL_ENV_VARS)
from ..utils import get_provider

API_URL = 'https://api.quantum-computing.ibm.com/api'
AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'
API1_URL = 'https://quantumexperience.ng.bluemix.net/api'


class TestIBMQFactoryEnableAccount(IBMQTestCase):
    """Tests for IBMQFactory ``enable_account()``."""

    @requires_qe_access
    def test_auth_url(self, qe_token, qe_url):
        """Test login into an auth account."""
        ibmq = IBMQFactory()
        provider = ibmq.enable_account(qe_token, qe_url)
        self.assertIsInstance(provider, AccountProvider)

    def test_old_api_url(self):
        """Test login into an API v1 auth account."""
        qe_token = 'invalid'
        qe_url = API1_URL

        with self.assertRaises(IBMQAccountCredentialsInvalidUrl) as context_manager:
            ibmq = IBMQFactory()
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('authentication URL', str(context_manager.exception))

    def test_non_auth_url(self):
        """Test login into a non-auth account."""
        qe_token = 'invalid'
        qe_url = API_URL

        with self.assertRaises(IBMQAccountCredentialsInvalidUrl) as context_manager:
            ibmq = IBMQFactory()
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('authentication URL', str(context_manager.exception))

    def test_non_auth_url_with_hub(self):
        """Test login into a non-auth account with h/g/p."""
        qe_token = 'invalid'
        qe_url = API_URL + '/Hubs/X/Groups/Y/Projects/Z'

        with self.assertRaises(IBMQAccountCredentialsInvalidUrl) as context_manager:
            ibmq = IBMQFactory()
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('authentication URL', str(context_manager.exception))

    @requires_qe_access
    def test_enable_twice(self, qe_token, qe_url):
        """Test login into an already logged-in account."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with self.assertRaises(IBMQAccountError) as context_manager:
            ibmq.enable_account(qe_token, qe_url)

        self.assertIn('already', str(context_manager.exception))

    @requires_qe_access
    def test_enable_twice_invalid(self, qe_token, qe_url):
        """Test login into an invalid account during an already logged-in account."""
        ibmq = IBMQFactory()
        ibmq.enable_account(qe_token, qe_url)

        with self.assertRaises(IBMQAccountError) as context_manager:
            qe_token_api1 = 'invalid'
            qe_url_api1 = API1_URL
            ibmq.enable_account(qe_token_api1, qe_url_api1)

        self.assertIn('already', str(context_manager.exception))

    @requires_qe_access
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

    @skipIf(os.name == 'nt', 'Test not supported in Windows')
    @requires_qe_access
    def test_enable_specified_provider(self, qe_token, qe_url):
        """Test enabling an account with a specified provider."""
        ibmq = IBMQFactory()
        non_default_provider = get_provider(ibmq, qe_token, qe_url, default=False)
        enabled_provider = ibmq.enable_account(token=qe_token, url=qe_url,
                                               hub=non_default_provider.credentials.hub,
                                               group=non_default_provider.credentials.group,
                                               project=non_default_provider.credentials.project)
        self.assertEqual(non_default_provider, enabled_provider)


@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestIBMQFactoryAccounts(IBMQTestCase):
    """Tests for account handling."""

    @classmethod
    def setUpClass(cls):
        """Initial class setup."""
        super().setUpClass()
        cls.token = 'API_TOKEN'

    def setUp(self):
        """Initial test setup."""
        super().setUp()

        # Reference for saving accounts.
        self.factory = IBMQFactory()

    def test_save_account(self):
        """Test saving an account."""
        with custom_qiskitrc():
            self.factory.save_account(self.token, url=AUTH_URL)
            stored_cred = self.factory.stored_account()

        self.assertEqual(stored_cred['token'], self.token)
        self.assertEqual(stored_cred['url'], AUTH_URL)

    def test_save_account_specified_provider(self):
        """Test saving an account with a specified provider."""
        default_hgp_to_save = 'default_hub/default_group/default_project'

        with custom_qiskitrc() as custom_qiskitrc_cm:
            hgp = HubGroupProject.from_stored_format(default_hgp_to_save)
            self.factory.save_account(token=self.token, url=AUTH_URL,
                                      hub=hgp.hub, group=hgp.group, project=hgp.project)

            # Ensure the `default_provider` name was written to the config file.
            config_parser = ConfigParser()
            try:
                config_parser.read(custom_qiskitrc_cm.tmp_file.name)
            except ParsingError as ex:
                self.log.warning('There was an issue parsing the custom_qiskitrc file: %s', str(ex))

            for name in config_parser.sections():
                single_credentials = dict(config_parser.items(name))
                self.assertIn('default_provider', single_credentials)
                self.assertEqual(single_credentials['default_provider'], default_hgp_to_save)

    def test_save_account_specified_provider_invalid(self):
        """Test saving an account without specifying all the hub/group/project fields."""
        invalid_hgps_to_save = [HubGroupProject('', 'default_group', ''),
                                HubGroupProject('default_hub', None, 'default_project')]
        for invalid_hgp in invalid_hgps_to_save:
            with self.subTest(invalid_hgp=invalid_hgp), custom_qiskitrc():
                with self.assertRaises(IBMQAccountValueError) as context_manager:
                    self.factory.save_account(token=self.token, url=AUTH_URL,
                                              hub=invalid_hgp.hub,
                                              group=invalid_hgp.group,
                                              project=invalid_hgp.project)
                self.assertIn('The hub, group, and project parameters must all be specified',
                              str(context_manager.exception))

    def test_delete_account(self):
        """Test deleting an account."""
        with custom_qiskitrc():
            self.factory.save_account(self.token, url=AUTH_URL)
            self.factory.delete_account()
            stored_cred = self.factory.stored_account()

        self.assertEqual(len(stored_cred), 0)

    @requires_qe_access
    def test_load_account(self, qe_token, qe_url):
        """Test loading an account."""
        if qe_url != QX_AUTH_URL:
            # .save_account() expects an auth production URL.
            self.skipTest('Test requires production auth URL')

        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            self.factory.save_account(qe_token, url=qe_url)
            self.factory.load_account()

        self.assertEqual(self.factory._credentials.token, qe_token)
        self.assertEqual(self.factory._credentials.url, qe_url)

    @requires_qe_access
    def test_load_account_saved_provider(self, qe_token, qe_url):
        """Test loading an account that contains a saved provider."""
        if qe_url != QX_AUTH_URL:
            # .save_account() expects an auth production URL.
            self.skipTest('Test requires production auth URL')

        # Get a non default provider.
        non_default_provider = get_provider(self.factory, qe_token, qe_url, default=False)

        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            self.factory.save_account(token=qe_token, url=qe_url,
                                      hub=non_default_provider.credentials.hub,
                                      group=non_default_provider.credentials.group,
                                      project=non_default_provider.credentials.project)
            saved_provider = self.factory.load_account()
            self.assertEqual(saved_provider, non_default_provider)

        self.assertEqual(self.factory._credentials.token, qe_token)
        self.assertEqual(self.factory._credentials.url, qe_url)

    @requires_qe_access
    def test_load_account_saved_provider_invalid_hgp(self, qe_token, qe_url):
        """Test loading an account that contains a saved provider that does not exist."""
        if qe_url != QX_AUTH_URL:
            # .save_account() expects an auth production URL.
            self.skipTest('Test requires production auth URL')

        # Hub, group, project in correct format but does not exists.
        invalid_hgp_to_store = 'invalid_hub/invalid_group/invalid_project'
        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            hgp = HubGroupProject.from_stored_format(invalid_hgp_to_store)
            self.factory.save_account(token=qe_token, url=qe_url,
                                      hub=hgp.hub, group=hgp.group, project=hgp.project)
            with self.assertRaises(IBMQAccountError) as context_manager:
                self.factory.load_account()
            self.assertIn('(hub/group/project) stored on disk could not be found',
                          str(context_manager.exception))

    def test_load_account_saved_provider_invalid_format(self):
        """Test loading an account that contains a saved provider in an invalid format."""
        # Format {'test_case_input': 'error message from raised exception'}
        invalid_hgps = {
            'hub_group_project': 'Use the "<hub_name>/<group_name>/<project_name>" format',
            'default_hub//default_project': 'Every field must be specified',
            'default_hub/default_group/': 'Every field must be specified'
        }

        for invalid_hgp, error_message in invalid_hgps.items():
            with self.subTest(invalid_hgp=invalid_hgp):
                with no_file('Qconfig.py'), custom_qiskitrc() as temp_qiskitrc, \
                        no_envs(CREDENTIAL_ENV_VARS):
                    # Save the account.
                    self.factory.save_account(token=self.token, url=AUTH_URL)
                    # Add an invalid provider field to the account stored.
                    with open(temp_qiskitrc.tmp_file.name, 'a') as _file:
                        _file.write('default_provider = {}'.format(invalid_hgp))
                    # Ensure an error is raised if the stored provider is in an invalid format.
                    with self.assertRaises(IBMQAccountError) as context_manager:
                        self.factory.load_account()
                    self.assertIn(error_message, str(context_manager.exception))

    @requires_qe_access
    def test_disable_account(self, qe_token, qe_url):
        """Test disabling an account """
        self.factory.enable_account(qe_token, qe_url)
        self.factory.disable_account()
        self.assertIsNone(self.factory._credentials)

    @requires_qe_access
    def test_active_account(self, qe_token, qe_url):
        """Test active_account for an account """
        self.assertIsNone(self.factory.active_account())

        self.factory.enable_account(qe_token, qe_url)
        active_account = self.factory.active_account()
        self.assertIsNotNone(active_account)
        self.assertEqual(active_account['token'], qe_token)
        self.assertEqual(active_account['url'], qe_url)

    def test_save_token_invalid(self):
        """Test saving an account with invalid tokens. See #391."""
        invalid_tokens = [None, '', 0]
        for invalid_token in invalid_tokens:
            with self.subTest(invalid_token=invalid_token):
                with self.assertRaises(IBMQAccountCredentialsInvalidToken) as context_manager:
                    self.factory.save_account(token=invalid_token)
                self.assertIn('Invalid IBM Quantum Experience token',
                              str(context_manager.exception))


class TestIBMQFactoryProvider(IBMQTestCase):
    """Tests for IBMQFactory provider related methods."""

    @requires_qe_access
    def _get_provider(self, qe_token=None, qe_url=None):
        """Return default provider."""
        return self.ibmq.enable_account(qe_token, qe_url)

    def setUp(self):
        """Initial test setup."""
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
