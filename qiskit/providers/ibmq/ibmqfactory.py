# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Factory and credentials manager for IBM Q Experience."""

import logging
import warnings
from collections import OrderedDict

from qiskit.providers.exceptions import QiskitBackendNotFoundError

from .accountprovider import AccountProvider
from .api_v2.clients import AuthClient, VersionClient
from .credentials import Credentials, discover_credentials
from .credentials.configrc import (read_credentials_from_qiskitrc,
                                   remove_credentials,
                                   store_credentials)
from .credentials.updater import update_credentials
from .exceptions import IBMQAccountError, IBMQApiUrlError, IBMQProviderError
from .ibmqprovider import IBMQProvider
from .utils.deprecation import deprecated, UPDATE_ACCOUNT_TEXT


logger = logging.getLogger(__name__)

QX_AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'


class IBMQFactory:
    """Factory and credentials manager for IBM Q Experience."""

    def __init__(self):
        self._credentials = None
        self._providers = OrderedDict()
        self._v1_provider = IBMQProvider()

    # Account management functions.

    def enable_account(self, token, url=QX_AUTH_URL, **kwargs):
        """Authenticate against IBM Q Experience for use during this session.

        Note: with version 0.3 of this qiskit-ibmq-provider package, use of
            the legacy Quantum Experience and Qconsole (also known
            as the IBM Q Experience v1) credentials is deprecated. The new
            default is to use the IBM Q Experience v2 credentials.

        Args:
            token (str): IBM Q Experience API token.
            url (str): URL for the IBM Q Experience authentication server.
            **kwargs (dict): additional settings for the connection:
                * proxies (dict): proxy configuration.
                * verify (bool): verify the server's TLS certificate.

        Returns:
            AccountProvider: the provider for the default open access project.

        Raises:
            IBMQAccountError: if an IBM Q Experience v2 account is already in
                use, or if attempting using both IBM Q Experience v1 and v2
                accounts.
            IBMQApiUrlError: if the input token and url are for an IBM Q
                Experience v2 account, but the url is not a valid
                authentication URL.
        """
        # Check if an IBM Q Experience 2 account is already in use.
        if self._credentials:
            raise IBMQAccountError('An IBM Q Experience v2 account is already '
                                   'enabled.')

        # Check the version used by these credentials.
        credentials = Credentials(token, url, **kwargs)
        version_info = self._check_api_version(credentials)

        # For API 1, delegate onto the IBMQProvider.
        if not version_info['new_api']:
            warnings.warn(
                'Using IBM Q Experience v1 credentials is being deprecated. '
                'Please use IBM Q Experience v2 credentials instead. '
                'You can find the instructions to make the updates here:\n'
                'https://github.com/Qiskit/qiskit-ibmq-provider#'
                'updating-to-the-new-ibm-q-experience',
                DeprecationWarning)
            self._v1_provider.enable_account(token, url, **kwargs)
            return self._v1_provider

        # Prevent using credentials not from the auth server.
        if 'api-auth' not in version_info:
            raise IBMQApiUrlError(
                'The URL specified ({}) is not an IBM Q Experience '
                'authentication URL'.format(credentials.url))

        # Prevent mixing API 1 and API 2 credentials.
        if self._v1_provider.active_accounts():
            raise IBMQAccountError('An IBM Q Experience v1 account is '
                                   'already enabled.')

        # Initialize the API 2 providers.
        self._initialize_providers(credentials)

        # Prevent edge case where no hubs are available.
        providers = self.providers()
        if not providers:
            warnings.warn('No Hub/Group/Projects could be found for this '
                          'account.')
            return None

        return providers[0]

    def disable_account(self):
        """Disable the account in the current session.

        Raises:
            IBMQAccountError: if IBM Q Experience API v1 credentials are found,
                or if no account is in use in the session.
        """
        if self._v1_provider.active_accounts():
            raise IBMQAccountError(
                'IBM Q Experience v1 accounts are enabled. Please use '
                'IBMQ.disable_accounts() to disable them.')

        if not self._credentials:
            raise IBMQAccountError('No account is in use for this session.')

        self._credentials = None
        self._providers = OrderedDict()

    def load_account(self):
        """Authenticate against IBM Q Experience from stored credentials.

        Returns:
            AccountProvider: the provider for the default open access project.

        Raises:
            IBMQAccountError: if an IBM Q Experience v1 account is already in
                use, or no IBM Q Experience v2 accounts can be found.
        """
        # Prevent mixing API 1 and API 2 credentials.
        if self._v1_provider.active_accounts():
            raise IBMQAccountError('An IBM Q Experience v1 account is '
                                   'already enabled.')

        # Check for valid credentials.
        credentials_list = list(discover_credentials().values())

        if not credentials_list:
            raise IBMQAccountError(
                'No IBM Q Experience credentials found on disk.')

        if len(credentials_list) > 1:
            raise IBMQAccountError('Multiple IBM Q Experience credentials '
                                   'found. ' + UPDATE_ACCOUNT_TEXT)

        credentials = credentials_list[0]
        # Explicitly check via an API call, to allow environment auth URLs.
        # contain API 2 URL (but not auth) slipping through.
        version_info = self._check_api_version(credentials)

        # For API 1, delegate onto the IBMQProvider.
        if not version_info['new_api']:
            raise IBMQAccountError('IBM Q Experience v1 credentials found. ' +
                                   UPDATE_ACCOUNT_TEXT)

        if 'api-auth' not in version_info:
            raise IBMQAccountError('Invalid IBM Q Experience v2 credentials '
                                   'found. ' + UPDATE_ACCOUNT_TEXT)

        # Initialize the API 2 providers.
        if self._credentials:
            # For convention, emit a warning instead of raising.
            warnings.warn('Credentials are already in use. The existing '
                          'account in the session will be replaced.')
            self.disable_account()

        self._initialize_providers(credentials)

        # Prevent edge case where no hubs are available.
        providers = self.providers()
        if not providers:
            warnings.warn('No Hub/Group/Projects could be found for this '
                          'account.')
            return None

        return providers[0]

    @staticmethod
    def save_account(token, url=QX_AUTH_URL, overwrite=False, **kwargs):
        """Save the account to disk for future use.

        Note: IBM Q Experience v1 credentials are being deprecated. Please
            use IBM Q Experience v2 credentials instead.

        Args:
            token (str): IBM Q Experience API token.
            url (str): URL for the IBM Q Experience authentication server.
            overwrite (bool): overwrite existing credentials.
            **kwargs (dict):
                * proxies (dict): Proxy configuration for the API.
                * verify (bool): If False, ignores SSL certificates errors
        """
        if url != QX_AUTH_URL:
            warnings.warn(
                'IBM Q Experience v1 credentials are being deprecated. Please '
                'use IBM Q Experience v2 credentials instead. '
                'You can find the instructions to make the updates here:\n'
                'https://github.com/Qiskit/qiskit-ibmq-provider#'
                'updating-to-the-new-ibm-q-experience',
                DeprecationWarning)

        credentials = Credentials(token, url, **kwargs)

        store_credentials(credentials, overwrite=overwrite)

    @staticmethod
    def delete_account():
        """Delete the saved account from disk.

        Raises:
            IBMQAccountError: if no valid IBM Q Experience v2 credentials found.
        """
        stored_credentials = read_credentials_from_qiskitrc()
        if not stored_credentials:
            raise IBMQAccountError('No credentials found.')

        if len(stored_credentials) != 1:
            raise IBMQAccountError('Multiple credentials found. ' +
                                   UPDATE_ACCOUNT_TEXT)

        credentials = list(stored_credentials.values())[0]

        if credentials.url != QX_AUTH_URL:
            raise IBMQAccountError('IBM Q Experience v1 credentials found. ' +
                                   UPDATE_ACCOUNT_TEXT)

        remove_credentials(credentials)

    @staticmethod
    def stored_account():
        """List the account stored on disk.

        Returns:
            dict: dictionary with information about the account stored on disk.

        Raises:
            IBMQAccountError: if no valid IBM Q Experience v2 credentials found.
        """
        stored_credentials = read_credentials_from_qiskitrc()
        if not stored_credentials:
            return {}

        if (len(stored_credentials) > 1 or
                list(stored_credentials.values())[0].url != QX_AUTH_URL):
            raise IBMQAccountError('IBM Q Experience v1 credentials found. ' +
                                   UPDATE_ACCOUNT_TEXT)

        credentials = list(stored_credentials.values())[0]
        return {
            'token': credentials.token,
            'url': credentials.url
        }

    def active_account(self):
        """List the IBM Q Experience v2 account currently in the session.

        Returns:
            dict: information about the account currently in the session.

        Raises:
            IBMQAccountError: if an IBM Q Experience v1 account is already in
                use.
        """
        if self._v1_provider.active_accounts():
            raise IBMQAccountError(
                'IBM Q Experience v1 accounts are enabled. Please use '
                'IBMQ.active_accounts() to retrieve information about them.')

        if not self._credentials:
            # Return None instead of raising, for compatibility with the
            # previous active_accounts() behavior.
            return None

        return {
            'token': self._credentials.token,
            'url': self._credentials.url,
        }

    @staticmethod
    def update_account(force=False):
        """Interactive helper from migrating stored credentials to IBM Q Experience v2.

        Args:
            force (bool): if `True`, disable interactive prompts and perform
                the changes.

        Returns:
            Credentials: if the updating is possible, credentials for the API
            version 2; and `None` otherwise.
        """
        return update_credentials(force)

    # Provider management functions.

    def providers(self, hub=None, group=None, project=None):
        """Return a list of providers with optional filtering.

        Args:
            hub (str): name of the hub.
            group (str): name of the group.
            project (str): name of the project.

        Returns:
            list[AccountProvider]: list of providers that match the specified
                criteria.
        """
        filters = []

        if hub:
            filters.append(lambda hgp: hgp.hub == hub)
        if group:
            filters.append(lambda hgp: hgp.group == group)
        if project:
            filters.append(lambda hgp: hgp.project == project)

        providers = [provider for key, provider in self._providers.items()
                     if all(f(key) for f in filters)]

        return providers

    def get_provider(self, hub=None, group=None, project=None):
        """Return a provider for a single hub/group/project combination.

        Returns:
            AccountProvider: provider that match the specified criteria.

        Raises:
            IBMQProviderError: if no provider matches the specified criteria,
                or more than one provider match the specified criteria.
        """
        providers = self.providers(hub, group, project)

        if not providers:
            raise IBMQProviderError('No provider matching the criteria')
        if len(providers) > 1:
            raise IBMQProviderError('More than one provider matching the '
                                    'criteria')

        return providers[0]

    # Private functions.

    @staticmethod
    def _check_api_version(credentials):
        """Check the version of the API in a set of credentials.

        Returns:
            dict: dictionary with version information.
        """
        version_finder = VersionClient(credentials.base_url,
                                       **credentials.connection_parameters())
        return version_finder.version()

    def _initialize_providers(self, credentials):
        """Authenticate against IBM Q Experience and populate the providers.

        Args:
            credentials (Credentials): credentials for IBM Q Experience.

        Raises:
            IBMQApiUrlError: if the credentials do not belong to a IBM Q
                Experience authentication URL.
        """
        auth_client = AuthClient(credentials.token,
                                 credentials.base_url,
                                 **credentials.connection_parameters())
        service_urls = auth_client.current_service_urls()
        user_hubs = auth_client.user_hubs()

        self._credentials = credentials
        for hub_info in user_hubs:
            # Build credentials.
            provider_credentials = Credentials(
                credentials.token,
                url=service_urls['http'],
                websockets_url=service_urls['ws'],
                proxies=credentials.proxies,
                verify=credentials.verify,
                **hub_info,)

            # Build the provider.
            try:
                provider = AccountProvider(provider_credentials,
                                           auth_client.current_access_token())
                self._providers[provider_credentials.unique_id()] = provider
            except Exception as ex:  # pylint: disable=broad-except
                # Catch-all for errors instantiating the provider.
                logger.warning('Unable to instantiate provider for %s: %s',
                               hub_info, ex)

    # Deprecated account management functions for backward compatibility.

    @deprecated
    def active_accounts(self):
        """List all IBM Q Experience v1 accounts currently in the session.

        Note: this method is being deprecated, and is only available when using
            v1 accounts.

        Returns:
            list[dict]: a list with information about the accounts currently
                in the session.

        Raises:
            IBMQAccountError: if the method is used with an IBM Q Experience
                v2 account.
        """
        return self._v1_provider.active_accounts()

    @deprecated
    def disable_accounts(self, **kwargs):
        """Disable IBM Q Experience v1 accounts in the current session.

        Note: this method is being deprecated, and only available when using
            v1 accounts.

        The filter kwargs can be `token`, `url`, `hub`, `group`, `project`.
        If no filter is passed, all accounts in the current session will be disabled.

        Raises:
            IBMQAccountError: if the method is used with an IBM Q Experience v2
                account, or if no account matched the filter.
        """
        self._v1_provider.disable_accounts(**kwargs)

    @deprecated
    def load_accounts(self, **kwargs):
        """Load IBM Q Experience v1 accounts found in the system into current session.

        Will also load v2 accounts for backward compatibility, but can lead to
        issues if mixing v1 and v2 credentials in other method calls.

        Note: this method is being deprecated, and only available when using
            v1 accounts.

        Automatically load the accounts found in the system. This method
        looks for credentials in the following locations, in order, and
        returns as soon as credentials are found:

        1. in the `Qconfig.py` file in the current working directory.
        2. in the environment variables.
        3. in the `qiskitrc` configuration file

        Raises:
            IBMQAccountError: If mixing v1 and v2 account credentials
        """
        version_counter = 0
        for credentials in discover_credentials().values():
            # Explicitly check via an API call, to prevent credentials that
            # contain API 2 URL (but not auth) slipping through.
            version_info = self._check_api_version(credentials)
            version_counter += int(version_info['new_api'])

        # Check if mixing v1 and v2 credentials
        if version_counter != 0 and version_counter < len(discover_credentials().values()):
            raise IBMQAccountError('Can not mix API v1 and v2'
                                   'credentials.')

        # If calling using API v2 credentials
        if version_counter:
            warnings.warn(
                'Calling IBMQ.load_accounts() with v2 credentials. '
                'This is provided for backwards compatibility '
                'and may lead to unexpected behaviour when mixing '
                'v1 and v2 account credentials.', DeprecationWarning)
            self.load_account()
        else:
            # Old API v1 call
            self._v1_provider.load_accounts(**kwargs)

    @deprecated
    def delete_accounts(self, **kwargs):
        """Delete saved IBM Q Experience v1 accounts from disk, subject to optional filtering.

        Note: this method is being deprecated, and only available when using
            v1 accounts.

        The filter kwargs can be `token`, `url`, `hub`, `group`, `project`.
        If no filter is passed, all accounts will be deleted from disk.

        Raises:
            IBMQAccountError: if the method is used with an IBM Q Experience v2
                account, or if no account matched the filter.
        """
        self._v1_provider.delete_accounts(**kwargs)

    @deprecated
    def stored_accounts(self):
        """List all IBM Q Experience v1 accounts stored to disk.

        Note: this method is being deprecated, and only available when using
            v1 accounts.

        Returns:
            list[dict]: a list with information about the accounts stored
                on disk.

        Raises:
            IBMQAccountError: if the method is used with an IBM Q Experience v2 account.
        """
        return self._v1_provider.stored_accounts()

    # Deprecated backend-related functionality.

    def backends(self, name=None, filters=None, **kwargs):
        """Return all backends accessible via IBMQ provider, subject to optional filtering.

        Note: this method is being deprecated. Please use an IBM Q Experience v2
            account, and::

            provider = IBMQ.get_provider(...)
            provider.backends()

            instead.

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
        warnings.warn('IBMQ.backends() is being deprecated. '
                      'Please use IBMQ.get_provider() to retrieve a provider '
                      'and AccountProvider.backends() to find its backends.',
                      DeprecationWarning)

        if self._credentials:
            hgp_filter = {}

            # First filter providers by h/g/p
            for key in ['hub', 'group', 'project']:
                if key in kwargs:
                    hgp_filter[key] = kwargs.pop(key)
            providers = self.providers(**hgp_filter)

            # Aggregate the list of filtered backends.
            backends = []
            for provider in providers:
                backends = backends + provider.backends(
                    name=name, filters=filters, **kwargs)

            return backends
        else:
            return self._v1_provider.backends(name, filters, **kwargs)

    def get_backend(self, name=None, **kwargs):
        """Return a single backend matching the specified filtering.

        Note: this method is being deprecated. Please use an IBM Q Experience v2
            account, and::

            provider = IBMQ.get_provider(...)
            provider.get_backend('name')

            instead.

        Args:
            name (str): name of the backend.
            **kwargs (dict): dict used for filtering.

        Returns:
            BaseBackend: a backend matching the filtering.

        Raises:
            QiskitBackendNotFoundError: if no backend could be found or
                more than one backend matches the filtering criteria.
        """
        warnings.warn('IBMQ.get_backend() is being deprecated. '
                      'Please use IBMQ.get_provider() to retrieve a provider '
                      'and AccountProvider.get_backend("name") to retrieve a '
                      'backend.',
                      DeprecationWarning)

        # Don't issue duplicate warnings
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=DeprecationWarning)
            backends = self.backends(name, **kwargs)

        if len(backends) > 1:
            raise QiskitBackendNotFoundError('More than one backend matches the criteria')
        if not backends:
            raise QiskitBackendNotFoundError('No backend matches the criteria')

        return backends[0]
