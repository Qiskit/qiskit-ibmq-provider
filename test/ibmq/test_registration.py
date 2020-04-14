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

"""Test the registration and credentials modules."""

import logging
import os
import warnings
from io import StringIO
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from unittest import skipIf
from unittest.mock import patch
from requests_ntlm import HttpNtlmAuth

from qiskit.providers.ibmq import IBMQ, IBMQFactory
from qiskit.providers.ibmq.credentials import (
    Credentials, discover_credentials, qconfig,
    read_credentials_from_qiskitrc, store_credentials)
from qiskit.providers.ibmq.credentials.updater import (
    update_credentials, QE2_AUTH_URL, QE2_URL, QE_URL)
from qiskit.providers.ibmq.exceptions import IBMQAccountError

from ..ibmqtestcase import IBMQTestCase
from ..contextmanagers import custom_envs, no_envs, custom_qiskitrc, no_file, CREDENTIAL_ENV_VARS


IBMQ_TEMPLATE = 'https://localhost/api/Hubs/{}/Groups/{}/Projects/{}'

PROXIES = {
    'urls': {
        'http': 'http://user:password@127.0.0.1:5678',
        'https': 'https://user:password@127.0.0.1:5678'
    }
}


# TODO: NamedTemporaryFiles do not support name in Windows
@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestCredentials(IBMQTestCase):
    """Tests for the credential modules."""

    def test_autoregister_no_credentials(self):
        """Test ``register()`` with no credentials available."""
        with no_file('Qconfig.py'), custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            with self.assertRaises(IBMQAccountError) as context_manager:
                IBMQ.load_account()

        self.assertIn('No IBM Quantum Experience credentials found', str(context_manager.exception))

    def test_store_credentials_overwrite(self):
        """Test overwriting qiskitrc credentials."""
        credentials = Credentials('QISKITRC_TOKEN', url=QE2_AUTH_URL)
        credentials2 = Credentials('QISKITRC_TOKEN_2', url=QE2_AUTH_URL)

        factory = IBMQFactory()

        with custom_qiskitrc():
            store_credentials(credentials)
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")

            # Get the logger for `store_credentials`.
            config_rc_logger = logging.getLogger(store_credentials.__module__)

            # Attempt overwriting.
            with self.assertLogs(logger=config_rc_logger, level='WARNING') as log_records:
                store_credentials(credentials)
                self.assertIn('already present', log_records.output[0])

            with no_file('Qconfig.py'), no_envs(CREDENTIAL_ENV_VARS), mock_ibmq_provider():
                # Attempt overwriting.
                store_credentials(credentials2, overwrite=True)
                factory.load_account()

        # Ensure that the credentials are the overwritten ones.
        self.assertEqual(factory._credentials, credentials2)

    def test_environ_over_qiskitrc(self):
        """Test order, without qconfig"""
        credentials = Credentials('QISKITRC_TOKEN', url=QE2_AUTH_URL)

        with custom_qiskitrc():
            # Prepare the credentials: both env and qiskitrc present
            store_credentials(credentials)
            with no_file('Qconfig.py'), custom_envs({'QE_TOKEN': 'ENVIRON_TOKEN',
                                                     'QE_URL': 'ENVIRON_URL'}):
                credentials, _ = discover_credentials()

        self.assertEqual(len(credentials), 1)
        self.assertEqual(list(credentials.values())[0].token, 'ENVIRON_TOKEN')

    def test_qconfig_over_all(self):
        """Test order, with qconfig"""
        credentials = Credentials('QISKITRC_TOKEN', url=QE2_AUTH_URL)

        with custom_qiskitrc():
            # Prepare the credentials: qconfig, env and qiskitrc present
            store_credentials(credentials)
            with custom_qconfig(b"APItoken='QCONFIG_TOKEN'"),\
                    custom_envs({'QE_TOKEN': 'ENVIRON_TOKEN'}):
                credentials, _ = discover_credentials()

        self.assertEqual(len(credentials), 1)
        self.assertEqual(list(credentials.values())[0].token, 'QCONFIG_TOKEN')


class TestCredentialsKwargs(IBMQTestCase):
    """Test for ``Credentials.connection_parameters()``."""

    def test_no_proxy_params(self):
        """Test when no proxy parameters are passed."""
        no_params_expected_result = {'verify': True}
        no_params_credentials = Credentials('dummy_token', 'https://dummy_url')
        result = no_params_credentials.connection_parameters()
        self.assertDictEqual(no_params_expected_result, result)

    def test_verify_param(self):
        """Test 'verify' arg is acknowledged."""
        false_verify_expected_result = {'verify': False}
        false_verify_credentials = Credentials(
            'dummy_token', 'https://dummy_url', verify=False)
        result = false_verify_credentials.connection_parameters()
        self.assertDictEqual(false_verify_expected_result, result)

    def test_proxy_param(self):
        """Test using only proxy urls (no NTLM credentials)."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        proxies_only_expected_result = {'verify': True, 'proxies': urls}
        proxies_only_credentials = Credentials(
            'dummy_token', 'https://dummy_url', proxies={'urls': urls})
        result = proxies_only_credentials.connection_parameters()
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
        result = proxies_with_ntlm_credentials.connection_parameters()

        # Verify the NTLM credentials.
        self.assertEqual(
            ntlm_expected_result['auth'].username, result['auth'].username)
        self.assertEqual(
            ntlm_expected_result['auth'].password, result['auth'].password)

        # Remove the HttpNtlmAuth objects for direct comparison of the dicts.
        ntlm_expected_result.pop('auth')
        result.pop('auth')
        self.assertDictEqual(ntlm_expected_result, result)

    def test_malformed_proxy_param(self):
        """Test input with malformed nesting of the proxies dictionary."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        malformed_nested_proxies_dict = {'proxies': urls}
        malformed_nested_credentials = Credentials(
            'dummy_token', 'https://dummy_url',
            proxies=malformed_nested_proxies_dict)

        # Malformed proxy entries should be ignored.
        expected_result = {'verify': True}
        result = malformed_nested_credentials.connection_parameters()
        self.assertDictEqual(expected_result, result)

    def test_malformed_ntlm_params(self):
        """Test input with malformed NTLM credentials."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        malformed_ntlm_credentials_dict = {
            'urls': urls,
            'username_ntlm': 1234,
            'password_ntlm': 5678
        }
        malformed_ntlm_credentials = Credentials(
            'dummy_token', 'https://dummy_url',
            proxies=malformed_ntlm_credentials_dict)
        # Should raise when trying to do username.split('\\', <int>)
        # in NTLM credentials due to int not facilitating 'split'.
        with self.assertRaises(AttributeError):
            _ = malformed_ntlm_credentials.connection_parameters()


@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestIBMQAccountUpdater(IBMQTestCase):
    """Tests for the ``update_credentials()`` helper."""

    def setUp(self):
        """Initial test setup."""
        super().setUp()

        # Avoid stdout output during tests.
        self.patcher = patch('sys.stdout', new=StringIO())
        self.patcher.start()

    def tearDown(self):
        """Test cleanup."""
        super().tearDown()

        # Reenable stdout output.
        self.patcher.stop()

    def assertCorrectApi2Credentials(self, token, credentials_dict):
        """Asserts that there is only one credentials belonging to API 2."""
        self.assertEqual(len(credentials_dict), 1)
        credentials = list(credentials_dict.values())[0]
        self.assertEqual(credentials.url, QE2_AUTH_URL)
        self.assertIsNone(credentials.hub)
        self.assertIsNone(credentials.group)
        self.assertIsNone(credentials.project)
        if token:
            self.assertEqual(credentials.token, token)

    def test_qe_credentials(self):
        """Test converting QE credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url=QE_URL))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertCorrectApi2Credentials('A', loaded_accounts)

    def test_qconsole_credentials(self):
        """Test converting Qconsole credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A',
                                          url=IBMQ_TEMPLATE.format('a', 'b', 'c')))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertCorrectApi2Credentials('A', loaded_accounts)

    def test_proxy_credentials(self):
        """Test converting credentials with proxy values."""
        with custom_qiskitrc():
            store_credentials(Credentials('A',
                                          url=IBMQ_TEMPLATE.format('a', 'b', 'c'),
                                          proxies=PROXIES))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertCorrectApi2Credentials('A', loaded_accounts)

            # Extra assert on preserving proxies.
            credentials = list(loaded_accounts.values())[0]
            self.assertEqual(credentials.proxies, PROXIES)

    def test_multiple_credentials(self):
        """Test converting multiple credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url=QE2_AUTH_URL))
            store_credentials(Credentials('B',
                                          url=IBMQ_TEMPLATE.format('a', 'b', 'c')))
            store_credentials(Credentials('C',
                                          url=IBMQ_TEMPLATE.format('d', 'e', 'f')))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            # We don't assert over the token, as it depends on the order of
            # the qiskitrc, which is not guaranteed.
            self.assertCorrectApi2Credentials(None, loaded_accounts)

    def test_api2_non_auth_credentials(self):
        """Test converting api 2 non auth credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url=QE2_URL))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertCorrectApi2Credentials('A', loaded_accounts)

    def test_auth2_credentials(self):
        """Test converting already API 2 auth credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url=QE2_AUTH_URL))
            credentials = update_credentials(force=True)

            # No credentials should be returned.
            self.assertIsNone(credentials)

    def test_unknown_credentials(self):
        """Test converting credentials with an unknown URL."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url='UNKNOWN_URL'))
            credentials = update_credentials(force=True)

            # No credentials should be returned nor updated.
            self.assertIsNone(credentials)
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertEqual(list(loaded_accounts.values())[0].url,
                             'UNKNOWN_URL')


# Context managers


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


def _mocked_initialize_provider(self, credentials: Credentials):
    """Mock ``_initialize_provider()``, just storing the credentials."""
    self._credentials = credentials


@contextmanager
def mock_ibmq_provider():
    """Mock the initialization of ``IBMQFactory``, so it does not query the API."""
    patcher = patch.object(IBMQFactory, '_initialize_providers',
                           side_effect=_mocked_initialize_provider,
                           autospec=True)
    patcher2 = patch.object(IBMQFactory, '_check_api_version',
                            return_value={'new_api': True, 'api-auth': '0.1'})
    patcher.start()
    patcher2.start()
    yield
    patcher2.stop()
    patcher.stop()
