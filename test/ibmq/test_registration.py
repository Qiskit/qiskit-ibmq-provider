# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
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
from unittest import skipIf
from unittest.mock import patch
from typing import Dict, Any
import copy

from requests_ntlm import HttpNtlmAuth
from qiskit.providers.ibmq import IBMQ, IBMQFactory
from qiskit.providers.ibmq.credentials import (
    Credentials, discover_credentials,
    read_credentials_from_qiskitrc, store_credentials,
    store_preferences, HubGroupProject)
from qiskit.providers.ibmq.credentials.updater import (
    update_credentials, QE2_AUTH_URL, QE2_URL, QE_URL)
from qiskit.providers.ibmq.credentials import configrc
from qiskit.providers.ibmq.exceptions import IBMQAccountError

from ..ibmqtestcase import IBMQTestCase
from ..contextmanagers import (custom_envs, no_envs, custom_qiskitrc, CREDENTIAL_ENV_VARS,
                               mock_ibmq_provider)


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

    def test_load_account_no_credentials(self) -> None:
        """Test ``load_account()`` with no credentials available."""
        with custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
            with self.assertRaises(IBMQAccountError) as context_manager:
                IBMQ.load_account()

        self.assertIn('No IBM Quantum Experience credentials found',
                      str(context_manager.exception))

    def test_store_credentials_overwrite(self) -> None:
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

            with no_envs(CREDENTIAL_ENV_VARS), mock_ibmq_provider():
                # Attempt overwriting.
                store_credentials(credentials2, overwrite=True)
                factory.load_account()

        # Ensure that the credentials are the overwritten ones.
        self.assertEqual(factory._credentials, credentials2)

    def test_environ_over_qiskitrc(self) -> None:
        """Test credential discovery order."""
        credentials = Credentials('QISKITRC_TOKEN', url=QE2_AUTH_URL)

        with custom_qiskitrc():
            # Prepare the credentials: both env and qiskitrc present
            store_credentials(credentials)
            with custom_envs({'QE_TOKEN': 'ENVIRON_TOKEN',
                              'QE_URL': 'ENVIRON_URL'}):
                credentials, _ = discover_credentials()

        self.assertEqual(len(credentials), 1)
        self.assertEqual(list(credentials.values())[0].token, 'ENVIRON_TOKEN')


class TestCredentialsKwargs(IBMQTestCase):
    """Test for ``Credentials.connection_parameters()``."""

    def test_no_proxy_params(self) -> None:
        """Test when no proxy parameters are passed."""
        no_params_expected_result = {'verify': True}
        no_params_credentials = Credentials('dummy_token', 'https://dummy_url')
        result = no_params_credentials.connection_parameters()
        self.assertDictEqual(no_params_expected_result, result)

    def test_verify_param(self) -> None:
        """Test 'verify' arg is acknowledged."""
        false_verify_expected_result = {'verify': False}
        false_verify_credentials = Credentials(
            'dummy_token', 'https://dummy_url', verify=False)
        result = false_verify_credentials.connection_parameters()
        self.assertDictEqual(false_verify_expected_result, result)

    def test_proxy_param(self) -> None:
        """Test using only proxy urls (no NTLM credentials)."""
        urls = {'http': 'localhost:8080', 'https': 'localhost:8080'}
        proxies_only_expected_result = {'verify': True, 'proxies': urls}
        proxies_only_credentials = Credentials(
            'dummy_token', 'https://dummy_url', proxies={'urls': urls})
        result = proxies_only_credentials.connection_parameters()
        self.assertDictEqual(proxies_only_expected_result, result)

    def test_proxies_param_with_ntlm(self) -> None:
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

    def test_malformed_proxy_param(self) -> None:
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

    def test_malformed_ntlm_params(self) -> None:
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
class TestPreferences(IBMQTestCase):
    """Tests for the preferences."""

    def test_save_preferences(self):
        """Test saving preferences."""
        preferences = self._get_pref_dict()
        with custom_qiskitrc():
            store_preferences(preferences)
            _, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual(preferences, stored_pref)

    def test_update_preferences(self):
        """Test updating preferences."""
        pref1 = self._get_pref_dict()
        with custom_qiskitrc():
            store_preferences(pref1)
            pref2 = self._get_pref_dict(pref_val=False)
            store_preferences(pref2)
            _, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual(pref2, stored_pref)

    def test_new_provider_pref(self):
        """Test adding preference for another provider."""
        pref1 = self._get_pref_dict()
        with custom_qiskitrc():
            store_preferences(pref1)
            pref2 = self._get_pref_dict('hub2/group2/project2', pref_val=False)
            store_preferences(pref2)
            _, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual({**pref1, **pref2}, stored_pref)

    def test_update_one_of_many_providers(self):
        """Test updating one of many provider preferences."""
        pref1 = self._get_pref_dict(pref_val=False)
        pref2 = self._get_pref_dict('hub2/group2/project2', pref_val=False)
        with custom_qiskitrc():
            store_preferences(pref1)
            store_preferences(pref2)
            pref1 = self._get_pref_dict(pref_val=True)
            store_preferences(pref1)

            _, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual({**pref1, **pref2}, stored_pref)

    def test_save_same_value_twice(self):
        """Test saving same value twice."""
        pref = self._get_pref_dict(pref_val=True)
        with custom_qiskitrc():
            store_preferences(pref)
            store_preferences(pref)

            _, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual(pref, stored_pref)

    def test_new_pref_cat(self):
        """Test adding a new preference category."""
        pref1 = self._get_pref_dict()
        orig_active_pref = copy.deepcopy(configrc._ACTIVE_PREFERENCES)
        try:
            configrc._ACTIVE_PREFERENCES.update(
                {'foo': {'bar': str}})
            with custom_qiskitrc():
                store_preferences(pref1)
                new_cat = self._get_pref_dict(cat="foo", pref_key="bar", pref_val='foobar')
                store_preferences(new_cat)
                _, stored_pref = read_credentials_from_qiskitrc()

                key = list(pref1.keys())[0]
                pref1[key].update(new_cat[key])
                self.assertEqual(pref1, stored_pref)
        finally:
            configrc._ACTIVE_PREFERENCES = orig_active_pref

    def test_overwrite_category_keys(self):
        """Test overwriting preference keys in a category."""
        pref1 = self._get_pref_dict()
        orig_active_pref = copy.deepcopy(configrc._ACTIVE_PREFERENCES)
        try:
            configrc._ACTIVE_PREFERENCES['experiment'].update({'foo': str})
            with custom_qiskitrc():
                store_preferences(pref1)
                new_cat = self._get_pref_dict(pref_key="foo", pref_val='bar')
                store_preferences(new_cat)
                _, stored_pref = read_credentials_from_qiskitrc()

                key = list(pref1.keys())[0]
                pref1[key]['experiment'] = {'foo': 'bar'}
                self.assertEqual(pref1, stored_pref)
        finally:
            configrc._ACTIVE_PREFERENCES = orig_active_pref

    def test_save_preferences_credentials(self):
        """Test saving both preferences and credentials."""
        preferences = self._get_pref_dict()
        credentials = Credentials('QISKITRC_TOKEN', url=QE2_AUTH_URL)
        with custom_qiskitrc():
            store_preferences(preferences)
            store_credentials(credentials)
            stored_cred, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual(preferences, stored_pref)
            self.assertEqual(credentials, stored_cred[credentials.unique_id()])

    def test_update_preferences_with_credentials(self):
        """Test updating preferences with credentials."""
        preferences = self._get_pref_dict()
        pref2 = self._get_pref_dict(pref_val=False)
        credentials = Credentials('QISKITRC_TOKEN', url=QE2_AUTH_URL)
        credentials2 = Credentials('QISKITRC_TOKEN_2', url=QE2_AUTH_URL)
        with custom_qiskitrc():
            store_preferences(preferences)
            store_credentials(credentials)
            # Update preferences.
            store_preferences(pref2)
            stored_cred, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual(pref2, stored_pref)
            self.assertEqual(credentials, stored_cred[credentials.unique_id()])
            # Update credentials.
            store_credentials(credentials2, overwrite=True)
            stored_cred, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual(pref2, stored_pref)
            self.assertEqual(credentials2, stored_cred[credentials2.unique_id()])

    def test_remove_credentials(self):
        """Test removing credentials when preferences are set."""
        preferences = self._get_pref_dict()
        credentials = Credentials('QISKITRC_TOKEN', url=QE2_AUTH_URL)
        with custom_qiskitrc():
            store_credentials(credentials)
            store_preferences(preferences)
            configrc.remove_credentials(credentials)
            stored_cred, stored_pref = read_credentials_from_qiskitrc()
            self.assertEqual(preferences, stored_pref)
            self.assertFalse(stored_cred)

    def _get_pref_dict(
            self,
            hgp: str = 'my-hub/my-group/my-project',
            cat: str = 'experiment',
            pref_key: str = 'auto_save',
            pref_val: Any = True
    ) -> Dict:
        """Generate a new preference dictionary."""
        hub, group, project = hgp.split('/')
        return {HubGroupProject(hub, group, project): {cat: {pref_key: pref_val}}}


@skipIf(os.name == 'nt', 'Test not supported in Windows')
class TestIBMQAccountUpdater(IBMQTestCase):
    """Tests for the ``update_credentials()`` helper."""

    def setUp(self) -> None:
        """Initial test setup."""
        super().setUp()

        # Avoid stdout output during tests.
        self.patcher = patch('sys.stdout', new=StringIO())
        self.patcher.start()

    def tearDown(self) -> None:
        """Test cleanup."""
        super().tearDown()

        # Reenable stdout output.
        self.patcher.stop()

    def assertCorrectApi2Credentials(self, token, credentials_dict) -> None:
        """Asserts that there is only one credentials belonging to API 2."""
        self.assertEqual(len(credentials_dict), 1)
        credentials = list(credentials_dict.values())[0]
        self.assertEqual(credentials.url, QE2_AUTH_URL)
        self.assertIsNone(credentials.hub)
        self.assertIsNone(credentials.group)
        self.assertIsNone(credentials.project)
        if token:
            self.assertEqual(credentials.token, token)

    def test_qe_credentials(self) -> None:
        """Test converting QE credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url=QE_URL))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertCorrectApi2Credentials('A', loaded_accounts)

    def test_qconsole_credentials(self) -> None:
        """Test converting Qconsole credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A',
                                          url=IBMQ_TEMPLATE.format('a', 'b', 'c')))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertCorrectApi2Credentials('A', loaded_accounts)

    def test_proxy_credentials(self) -> None:
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

    def test_multiple_credentials(self) -> None:
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

    def test_api2_non_auth_credentials(self) -> None:
        """Test converting api 2 non auth credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url=QE2_URL))
            _ = update_credentials(force=True)

            # Assert over the stored (updated) credentials.
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertCorrectApi2Credentials('A', loaded_accounts)

    def test_auth2_credentials(self) -> None:
        """Test converting already API 2 auth credentials."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url=QE2_AUTH_URL))
            credentials = update_credentials(force=True)

            # No credentials should be returned.
            self.assertIsNone(credentials)

    def test_unknown_credentials(self) -> None:
        """Test converting credentials with an unknown URL."""
        with custom_qiskitrc():
            store_credentials(Credentials('A', url='UNKNOWN_URL'))
            credentials = update_credentials(force=True)

            # No credentials should be returned nor updated.
            self.assertIsNone(credentials)
            loaded_accounts, _ = read_credentials_from_qiskitrc()
            self.assertEqual(list(loaded_accounts.values())[0].url,
                             'UNKNOWN_URL')
