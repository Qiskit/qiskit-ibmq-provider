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

"""Test the registration and credentials features of the IBMQ module."""

import os
import warnings
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from unittest import skipIf
from unittest.mock import patch
from requests.exceptions import ProxyError
from requests_ntlm import HttpNtlmAuth

from qiskit.providers.ibmq import IBMQ
from qiskit.providers.ibmq.credentials import (
    Credentials, configrc, discover_credentials, qconfig,
    read_credentials_from_qiskitrc, store_credentials)
from qiskit.providers.ibmq.credentials.environ import VARIABLES_MAP
from qiskit.providers.ibmq.exceptions import IBMQAccountError
from qiskit.providers.ibmq.ibmqprovider import QE_URL
from qiskit.providers.ibmq.ibmqsingleprovider import IBMQSingleProvider
from qiskit.providers.ibmq.api_v2.exceptions import RequestsApiError
from qiskit.test import QiskitTestCase

from ..contextmanagers import custom_envs, no_envs

IBMQ_TEMPLATE = 'https://localhost/api/Hubs/{}/Groups/{}/Projects/{}'

PROXIES = {
    'urls': {
        'http': 'http://user:password@127.0.0.1:5678',
        'https': 'https://user:password@127.0.0.1:5678'
    }
}

CREDENTIAL_ENV_VARS = VARIABLES_MAP.keys()


# TODO: NamedTemporaryFiles do not support name in Windows
@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestIBMQAccounts(QiskitTestCase):
    """Tests for the IBMQ account handling."""
    def test_enable_account(self):
        """Test enabling one account."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.enable_account('QISKITRC_TOKEN', url='someurl',
                                proxies=PROXIES)

            # Compare the session accounts with the ones stored in file.
            loaded_accounts = read_credentials_from_qiskitrc()
            _, provider = list(IBMQ._accounts.items())[0]

            self.assertEqual(loaded_accounts, {})
            self.assertEqual('QISKITRC_TOKEN', provider.credentials.token)
            self.assertEqual('someurl', provider.credentials.url)
            self.assertEqual(PROXIES, provider.credentials.proxies)

    def test_enable_multiple_accounts(self):
        """Test enabling multiple accounts, combining QX and IBMQ."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.enable_account('QISKITRC_TOKEN')
            IBMQ.enable_account('QISKITRC_TOKEN',
                                url=IBMQ_TEMPLATE.format('a', 'b', 'c'))
            IBMQ.enable_account('QISKITRC_TOKEN',
                                url=IBMQ_TEMPLATE.format('a', 'b', 'X'))

            # Compare the session accounts with the ones stored in file.
            loaded_accounts = read_credentials_from_qiskitrc()
            self.assertEqual(loaded_accounts, {})
            self.assertEqual(len(IBMQ._accounts), 3)

    def test_enable_duplicate_accounts(self):
        """Test enabling the same credentials twice."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.enable_account('QISKITRC_TOKEN')

            self.assertEqual(len(IBMQ._accounts), 1)

    def test_save_account(self):
        """Test saving one account."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.save_account('QISKITRC_TOKEN', url=QE_URL,
                              proxies=PROXIES)

            # Compare the session accounts with the ones stored in file.
            stored_accounts = read_credentials_from_qiskitrc()
            self.assertEqual(len(stored_accounts.keys()), 1)

    def test_save_multiple_accounts(self):
        """Test saving several accounts, combining QX and IBMQ"""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.save_account('QISKITRC_TOKEN')
            IBMQ.save_account('QISKITRC_TOKEN',
                              url=IBMQ_TEMPLATE.format('a', 'b', 'c'))
            IBMQ.save_account('QISKITRC_TOKEN',
                              IBMQ_TEMPLATE.format('a', 'b', 'X'))

            # Compare the session accounts with the ones stored in file.
            stored_accounts = read_credentials_from_qiskitrc()
            self.assertEqual(len(stored_accounts), 3)
            for account_name, provider in IBMQ._accounts.items():
                self.assertEqual(provider.credentials,
                                 stored_accounts[account_name])

    def test_save_duplicate_accounts(self):
        """Test saving the same credentials twice."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.save_account('QISKITRC_TOKEN')
            with self.assertWarns(UserWarning) as context_manager:
                IBMQ.save_account('QISKITRC_TOKEN')

            self.assertIn('Set overwrite', str(context_manager.warning))
            # Compare the session accounts with the ones stored in file.
            stored_accounts = read_credentials_from_qiskitrc()
            self.assertEqual(len(stored_accounts), 1)

    def test_disable_accounts(self):
        """Test disabling an account in a session."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.enable_account('QISKITRC_TOKEN')
            IBMQ.disable_accounts(token='QISKITRC_TOKEN')

            self.assertEqual(len(IBMQ._accounts), 0)

    def test_delete_accounts(self):
        """Test deleting an account from disk."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.save_account('QISKITRC_TOKEN')
            self.assertEqual(len(read_credentials_from_qiskitrc()), 1)

            IBMQ._accounts.clear()
            IBMQ.delete_accounts(token='QISKITRC_TOKEN')
            self.assertEqual(len(read_credentials_from_qiskitrc()), 0)

    def test_disable_all_accounts(self):
        """Test disabling all accounts from session."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.enable_account('QISKITRC_TOKEN')
            IBMQ.enable_account('QISKITRC_TOKEN',
                                url=IBMQ_TEMPLATE.format('a', 'b', 'c'))
            IBMQ.disable_accounts()
            self.assertEqual(len(IBMQ._accounts), 0)

    def test_delete_all_accounts(self):
        """Test deleting all accounts from disk."""
        with custom_qiskitrc(), mock_ibmq_provider():
            IBMQ.save_account('QISKITRC_TOKEN')
            IBMQ.save_account('QISKITRC_TOKEN',
                              url=IBMQ_TEMPLATE.format('a', 'b', 'c'))
            self.assertEqual(len(read_credentials_from_qiskitrc()), 2)
            IBMQ.delete_accounts()
            self.assertEqual(len(IBMQ._accounts), 0)
            self.assertEqual(len(read_credentials_from_qiskitrc()), 0)

    def test_pass_bad_proxy(self):
        """Test proxy pass through."""
        with self.assertRaises(RequestsApiError) as context_manager:
            IBMQ.enable_account('dummy_token', 'https://dummy_url',
                                proxies=PROXIES)
        self.assertIsInstance(context_manager.exception.original_exception, ProxyError)


# TODO: NamedTemporaryFiles do not support name in Windows
@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestCredentials(QiskitTestCase):
    """Tests for the credential subsystem."""

    def test_autoregister_no_credentials(self):
        """Test register() with no credentials available."""
        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            with self.assertRaises(IBMQAccountError) as context_manager:
                IBMQ.load_accounts()

        self.assertIn('No IBMQ credentials found', str(context_manager.exception))

    def test_store_credentials_overwrite(self):
        """Test overwriting qiskitrc credentials."""
        credentials = Credentials('QISKITRC_TOKEN', url=QE_URL, hub='HUB')
        credentials2 = Credentials('QISKITRC_TOKEN_2', url=QE_URL)

        with custom_qiskitrc():
            store_credentials(credentials)
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            # Attempt overwriting.
            with warnings.catch_warnings(record=True) as w:
                store_credentials(credentials)
                self.assertIn('already present', str(w[0]))

            with no_file('Qconfig.py'), no_envs(CREDENTIAL_ENV_VARS), mock_ibmq_provider():
                # Attempt overwriting.
                store_credentials(credentials2, overwrite=True)
                IBMQ.load_accounts()

        # Ensure that the credentials are the overwritten ones - note that the
        # 'hub' parameter was removed.
        self.assertEqual(len(IBMQ._accounts), 1)
        self.assertEqual(list(IBMQ._accounts.values())[0].credentials.token,
                         'QISKITRC_TOKEN_2')

    def test_environ_over_qiskitrc(self):
        """Test order, without qconfig"""
        credentials = Credentials('QISKITRC_TOKEN', url=QE_URL)

        with custom_qiskitrc():
            # Prepare the credentials: both env and qiskitrc present
            store_credentials(credentials)
            with no_file('Qconfig.py'), custom_envs({'QE_TOKEN': 'ENVIRON_TOKEN',
                                                     'QE_URL': 'ENVIRON_URL'}):
                credentials = discover_credentials()

        self.assertEqual(len(credentials), 1)
        self.assertEqual(list(credentials.values())[0].token, 'ENVIRON_TOKEN')

    def test_qconfig_over_all(self):
        """Test order, with qconfig"""
        credentials = Credentials('QISKITRC_TOKEN', url=QE_URL)

        with custom_qiskitrc():
            # Prepare the credentials: qconfig, env and qiskitrc present
            store_credentials(credentials)
            with custom_qconfig(b"APItoken='QCONFIG_TOKEN'"),\
                    custom_envs({'QE_TOKEN': 'ENVIRON_TOKEN'}):
                credentials = discover_credentials()

        self.assertEqual(len(credentials), 1)
        self.assertEqual(list(credentials.values())[0].token, 'QCONFIG_TOKEN')

    def test_no_proxy_params(self):
        """Test when no proxy parameters are passed."""
        no_params_expected_result = {'verify': True, 'proxies': None, 'auth': None}
        no_params_credentials = Credentials('dummy_token', 'https://dummy_url')
        result = dict(no_params_credentials.connection_parameters())
        self.assertDictEqual(no_params_expected_result, result)

    def test_verify_param(self):
        """Test 'verify' arg is acknowledged."""
        false_verify_expected_result = {'verify': False, 'proxies': None, 'auth': None}
        false_verify_credentials = Credentials('dummy_token', 'https://dummy_url', verify=False)
        result = dict(false_verify_credentials.connection_parameters())
        self.assertDictEqual(false_verify_expected_result, result)

    def test_proxy_param(self):
        """Test using only proxy urls (no NTLM credentials)."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        proxies_only_expected_result = {'verify': True, 'proxies': urls, 'auth': None}
        proxies_only_credentials = Credentials(
            'dummy_token', 'https://dummy_url', proxies={'urls': urls})
        result = dict(proxies_only_credentials.connection_parameters())
        self.assertDictEqual(proxies_only_expected_result, result)

    def test_proxies_param_with_ntlm(self):
        """Test proxies with NTLM credentials."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        proxies_with_ntlm_dict = {
            'urls': urls,
            'username_ntlm': 'domain\\username',
            'password_ntlm': 'password'
        }
        ntlm_expected_result = {
            'verify': True,
            'proxies': urls,
            'auth': HttpNtlmAuth('domain\\username', 'password')
        }
        proxies_with_ntlm_credentials = Credentials(
            'dummy_token', 'https://dummy_url', proxies=proxies_with_ntlm_dict)
        result = dict(proxies_with_ntlm_credentials.connection_parameters())

        # verify the NTLM credentials
        self.assertEqual(
            ntlm_expected_result['auth'].username, result['auth'].username)
        self.assertEqual(
            ntlm_expected_result['auth'].password, result['auth'].password)

        # remove the NTLM HttpNtlmAuth objects for direct comparison of the dicts
        ntlm_expected_result.pop('auth')
        result.pop('auth')
        self.assertDictEqual(ntlm_expected_result, result)

    def test_malformed_proxy_param(self):
        """Test input with malformed nesting of the proxies dictionary."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        malformed_nested_proxies_dict = {'proxies': urls}
        malformed_nested_credentials = Credentials(
            'dummy_token', 'https://dummy_url', proxies=malformed_nested_proxies_dict)
        with self.assertRaises(KeyError):
            _ = dict(malformed_nested_credentials.connection_parameters())

    def test_malformed_ntlm_params(self):
        """Test input with malformed NTLM credentials."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        malformed_ntlm_credentials_dict = {
            'urls': urls,
            'username_ntlm': 1234,
            'password_ntlm': 5678
        }
        malformed_ntlm_credentials = Credentials(
            'dummy_token', 'https://dummy_url', proxies=malformed_ntlm_credentials_dict)
        # should raise when trying to do username.split('\\', <int>)
        # in NTLM credentials due to int not facilitating 'split'
        with self.assertRaises(AttributeError):
            _ = dict(malformed_ntlm_credentials.connection_parameters())


# Context managers

@contextmanager
def no_file(filename):
    """Context manager that disallows access to a file."""
    def side_effect(filename_):
        """Return False for the specified file."""
        if filename_ == filename:
            return False
        return isfile_original(filename_)

    # Store the original `os.path.isfile` function, for mocking.
    isfile_original = os.path.isfile
    patcher = patch('os.path.isfile', side_effect=side_effect)
    patcher.start()
    yield
    patcher.stop()


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


@contextmanager
def custom_qconfig(contents=b''):
    """Context manager that uses a temporary qconfig.py."""
    # Create a temporary file with the contents.
    tmp_file = NamedTemporaryFile(suffix='.py')
    tmp_file.write(contents)
    tmp_file.flush()

    # Temporarily modify the default location of the qiskitrc file.
    default_qconfig_file_original = qconfig.DEFAULT_QCONFIG_FILE
    qconfig.DEFAULT_QCONFIG_FILE = tmp_file.name
    yield

    # Delete the temporary file and restore the default location.
    tmp_file.close()
    qconfig.DEFAULT_QCONFIG_FILE = default_qconfig_file_original


@contextmanager
def mock_ibmq_provider():
    """Mock the initialization of IBMQSingleProvider, so it does not query the api."""
    patcher = patch.object(IBMQSingleProvider, '_authenticate', return_value=None)
    patcher2 = patch.object(IBMQSingleProvider, '_discover_remote_backends', return_value={})
    patcher.start()
    patcher2.start()
    yield
    patcher2.stop()
    patcher.stop()
