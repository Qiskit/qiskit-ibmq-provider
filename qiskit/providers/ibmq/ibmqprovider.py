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

"""Provider for remote IBMQ backends with admin features."""

import warnings
from collections import OrderedDict

from qiskit.providers import BaseProvider

from .api_v2.clients import AuthClient, VersionClient
from .credentials.configrc import remove_credentials
from .credentials import (Credentials,
                          read_credentials_from_qiskitrc, store_credentials, discover_credentials)
from .exceptions import IBMQAccountError
from .accountprovider import AccountProvider
from .ibmqsingleprovider import IBMQSingleProvider


QE_URL = 'https://quantumexperience.ng.bluemix.net/api'
QX_AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'


class IBMQProvider(BaseProvider):
    """Provider for remote IBMQ backends with admin features.

    This class is the entry point for handling backends from IBMQ, allowing
    using different accounts.
    """
    def __init__(self):
        super().__init__()

        # dict[credentials_unique_id: IBMQSingleProvider]
        # This attribute stores a reference to the different accounts. The
        # keys are tuples (hub, group, project), as the convention is that
        # that tuple uniquely identifies a set of credentials.
        self._accounts = OrderedDict()

        self._credentials = None
        self._providers = OrderedDict()

    def use_token(self, token, auth_url=QX_AUTH_URL, **kwargs):
        """Authenticate against IBM Q Experience for use during this session.

        Args:
            token (str): IBM Q Experience API token.
            auth_url (str): URL for the IBM Q Experience auth server.
            **kwargs (dict): additional settings for the connection:
                * proxies (dict): proxy configuration.
                * verify (bool): verify the server's TLS certificate.

        """
        # TODO: rename function
        # TODO: check and clean kwargs (verify str, proxies)
        self._set_token(Credentials(token, auth_url, **kwargs))

    def _set_token(self, credentials):
        """Authenticate against IBM Q Experience and populate the providers.

        Args:
            credentials (Credentials): credentials for IBM Q Experience.

        Raises:
            IBMQAccountError:
        """
        # TODO: add checks (overwrite, mixing old and new)
        version_finder = VersionClient(credentials.base_url)
        version_info = version_finder.version()

        if not (version_info['new_api'] and 'api-auth' in version_info):
            raise IBMQAccountError(
                'The URL specified ({}) is not a IBM Q Experience '
                'authentication URL'.format(credentials.base_url))

        auth_client = AuthClient(credentials.token,
                                 credentials.base_url)

        service_urls = auth_client.user_urls()
        user_hubs = auth_client.user_hubs()

        for hub_info in user_hubs:
            # Build credentials.
            provider_credentials = Credentials(
                credentials.token,
                url=service_urls['http'],
                websockets_url=service_urls['ws'],
                hub=hub_info['hub'],
                group=hub_info['group'],
                project=hub_info['project'],
                proxies=credentials.proxies,
                verify=credentials.verify)

            # Build the provider.
            provider = AccountProvider(provider_credentials,
                                       auth_client.current_access_token())
            self._providers[provider_credentials.unique_id()] = provider

    def get_provider(self, hub=None, group=None, project=None):
        """Return a provider for a single hub/group/project combination.

        Returns:
            AccountProvider:

        Raises:
            IBMQAccountError:
        """
        filters = []
        for i, key in enumerate((hub, group, project)):
            if key:
                filters.append(lambda x: x[i] == key)

        providers = list(filter(lambda x: all(f(x) for f in filters),
                                self._providers.keys()))

        if not providers:
            raise IBMQAccountError('No providers matching the criteria')
        if len(providers) > 1:
            raise IBMQAccountError('More than one provider matching the '
                                   'criteria')

        return self._providers[providers[0]]

    def backends(self, name=None, filters=None, **kwargs):
        """Return all backends accessible via IBMQ provider, subject to optional filtering.

        Args:
            name (str): backend name to filter by
            filters (callable): more complex filters, such as lambda functions
                e.g. IBMQ.backends(filters=lambda b: b.configuration['n_qubits'] > 5)
            kwargs: simple filters specifying a true/false criteria in the
                backend configuration or backend status or provider credentials
                e.g. IBMQ.backends(n_qubits=5, operational=True, hub='internal')

        Returns:
            list[IBMQBackend]: list of backends available that match the filter
        """
        # pylint: disable=arguments-differ

        # Special handling of the credentials filters: match and prune from kwargs
        credentials_filter = {}
        for key in ['token', 'url', 'hub', 'group', 'project', 'proxies', 'verify']:
            if key in kwargs:
                credentials_filter[key] = kwargs.pop(key)
        providers = [provider for provider in self._accounts.values() if
                     self._credentials_match_filter(provider.credentials,
                                                    credentials_filter)]

        # Special handling of the `name` parameter, to support alias resolution.
        if name:
            aliases = self._aliased_backend_names()
            aliases.update(self._deprecated_backend_names())
            name = aliases.get(name, name)

        # Aggregate the list of filtered backends.
        backends = []
        for provider in providers:
            backends = backends + provider.backends(
                name=name, filters=filters, **kwargs)

        return backends

    @staticmethod
    def _deprecated_backend_names():
        """Returns deprecated backend names."""
        return {
            'ibmqx_qasm_simulator': 'ibmq_qasm_simulator',
            'ibmqx_hpc_qasm_simulator': 'ibmq_qasm_simulator',
            'real': 'ibmqx1'
            }

    @staticmethod
    def _aliased_backend_names():
        """Returns aliased backend names."""
        return {
            'ibmq_5_yorktown': 'ibmqx2',
            'ibmq_5_tenerife': 'ibmqx4',
            'ibmq_16_rueschlikon': 'ibmqx5',
            'ibmq_20_austin': 'QS1_1'
            }

    def enable_account(self, token, url=QE_URL, **kwargs):
        """Authenticate a new IBMQ account and add for use during this session.

        Login into Quantum Experience or IBMQ using the provided credentials,
        adding the account to the current session. The account is not stored
        in disk.

        Args:
            token (str): Quantum Experience or IBM Q API token.
            url (str): URL for Quantum Experience or IBM Q (for IBM Q,
                including the hub, group and project in the URL).
            **kwargs (dict):
                * proxies (dict): Proxy configuration for the API.
                * verify (bool): If False, ignores SSL certificates errors
        """
        credentials = Credentials(token, url, **kwargs)

        self._append_account(credentials)

    def save_account(self, token, url=QE_URL, overwrite=False, **kwargs):
        """Save the account to disk for future use.

        Login into Quantum Experience or IBMQ using the provided credentials,
        adding the account to the current session. The account is stored in
        disk for future use.

        Args:
            token (str): Quantum Experience or IBM Q API token.
            url (str): URL for Quantum Experience or IBM Q (for IBM Q,
                including the hub, group and project in the URL).
            overwrite (bool): overwrite existing credentials.
            **kwargs (dict):
                * proxies (dict): Proxy configuration for the API.
                * verify (bool): If False, ignores SSL certificates errors
        """
        credentials = Credentials(token, url, **kwargs)
        store_credentials(credentials, overwrite=overwrite)

    def active_accounts(self):
        """List all accounts currently in the session.

        Returns:
            list[dict]: a list with information about the accounts currently
                in the session.
        """
        information = []
        for provider in self._accounts.values():
            information.append({
                'token': provider.credentials.token,
                'url': provider.credentials.url,
            })

        return information

    def stored_accounts(self):
        """List all accounts stored to disk.

        Returns:
            list[dict]: a list with information about the accounts stored
                on disk.
        """
        information = []
        stored_creds = read_credentials_from_qiskitrc()
        for creds in stored_creds:
            information.append({
                'token': stored_creds[creds].token,
                'url': stored_creds[creds].url
            })

        return information

    def load_accounts(self, **kwargs):
        """Load IBMQ accounts found in the system into current session,
        subject to optional filtering.

        Automatically load the accounts found in the system. This method
        looks for credentials in the following locations, in order, and
        returns as soon as credentials are found:

        1. in the `Qconfig.py` file in the current working directory.
        2. in the environment variables.
        3. in the `qiskitrc` configuration file

        Raises:
            IBMQAccountError: if no credentials are found.
        """
        for credentials in discover_credentials().values():
            if self._credentials_match_filter(credentials, kwargs):
                self._append_account(credentials)

        if not self._accounts:
            raise IBMQAccountError('No IBMQ credentials found on disk.')

    def disable_accounts(self, **kwargs):
        """Disable accounts in the current session, subject to optional filtering.

        The filter kwargs can be `token`, `url`, `hub`, `group`, `project`.
        If no filter is passed, all accounts in the current session will be disabled.

        Raises:
            IBMQAccountError: if no account matched the filter.
        """
        disabled = False

        # Try to remove from session.
        current_creds = self._accounts.copy()
        for creds in current_creds:
            credentials = Credentials(current_creds[creds].credentials.token,
                                      current_creds[creds].credentials.url)
            if self._credentials_match_filter(credentials, kwargs):
                del self._accounts[credentials.unique_id()]
                disabled = True

        if not disabled:
            raise IBMQAccountError('No matching account to disable in current session.')

    def delete_accounts(self, **kwargs):
        """Delete saved accounts from disk, subject to optional filtering.

        The filter kwargs can be `token`, `url`, `hub`, `group`, `project`.
        If no filter is passed, all accounts will be deleted from disk.

        Raises:
            IBMQAccountError: if no account matched the filter.
        """
        deleted = False

        # Try to delete from disk.
        stored_creds = read_credentials_from_qiskitrc()
        for creds in stored_creds:
            credentials = Credentials(stored_creds[creds].token,
                                      stored_creds[creds].url)
            if self._credentials_match_filter(credentials, kwargs):
                remove_credentials(credentials)
                deleted = True

        if not deleted:
            raise IBMQAccountError('No matching account to delete from disk.')

    def _append_account(self, credentials):
        """Append an account with the specified credentials to the session.

        Args:
            credentials (Credentials): set of credentials.

        Returns:
            IBMQSingleProvider: new single-account provider.
        """
        # Check if duplicated credentials are already in use. By convention,
        # we assume (hub, group, project) is always unique.
        if credentials.unique_id() in self._accounts.keys():
            warnings.warn('Credentials are already in use.')

        single_provider = IBMQSingleProvider(credentials, self)

        self._accounts[credentials.unique_id()] = single_provider

        return single_provider

    def _credentials_match_filter(self, credentials, filter_dict):
        """Return True if the credentials match a filter.

        These filters apply on properties of a Credentials object:
        token, url, hub, group, project, proxies, verify
        Any other filter has no effect.

        Args:
            credentials (Credentials): IBMQ credentials object
            filter_dict (dict): dictionary of filter conditions

        Returns:
            bool: True if the credentials meet all the filter conditions
        """
        return all(getattr(credentials, key_, None) == value_ for
                   key_, value_ in filter_dict.items())
