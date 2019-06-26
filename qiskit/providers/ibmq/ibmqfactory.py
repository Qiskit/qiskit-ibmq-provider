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

from .accountprovider import AccountProvider
from .api_v2.clients import AuthClient, VersionClient
from .credentials import Credentials
from .exceptions import IBMQAccountError, IBMQApiUrlError, IBMQProviderError
from .ibmqprovider import IBMQProvider, QE_URL

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

        Args:
            token (str): IBM Q Experience API token.
            url (str): URL for the IBM Q Experience auth server.
            **kwargs (dict): additional settings for the connection:
                * proxies (dict): proxy configuration.
                * verify (bool): verify the server's TLS certificate.

        Returns:
            AccountProvider: the provider for the default open access project.

        Raises:
            IBMQAccountError: if an IBM Q Experience 2 account is already in
                use, or if attempting using both classic API and new API
                accounts.
            IBMQApiUrlError: if the credentials are from IBM Q Experience 2,
                but do not belong to the authentication URL.
        """
        # Check if an IBM Q Experience 2 account is already in use.
        if self._credentials:
            raise IBMQAccountError('An IBM Q Experience 2 account is already '
                                   'enabled.')

        # Check the version used by these credentials.
        credentials = Credentials(token, url, **kwargs)
        version_info = self._check_api_version(credentials)

        # For API 1, delegate onto the IBMQProvider.
        if not version_info['new_api']:
            self._v1_provider.enable_account(token, url, **kwargs)
            return self._v1_provider

        # Prevent using credentials not from the auth server.
        if 'api-auth' not in version_info:
            raise IBMQApiUrlError(
                'The URL specified ({}) is not a IBM Q Experience '
                'authentication URL'.format(credentials.url))

        # Prevent mixing API 1 and API 2 credentials.
        if self._v1_provider.active_accounts():
            raise IBMQAccountError('An IBM Q Experience 1 account is '
                                   'already enabled.')

        # Initialize the API 2 providers.
        self._initialize_providers(credentials)

        return self.providers()[0]

    def disable_account(self):
        """Disable the account in the current session.

        Raises:
            IBMQAccountError: if no account is in use in the session.
        """
        raise NotImplementedError

    def load_account(self):
        """Authenticate against IBM Q Experience from stored credentials.

        Returns:
            AccountProvider: the provider for the default open access project.
        """
        raise NotImplementedError

    def save_account(self, token=None, url=QE_URL, overwrite=False, **kwargs):
        """Save an account to disk for future use.

        Args:
            token (str): Quantum Experience or IBM Q API token. This parameter is deprecated.
            url (str): URL for Quantum Experience or IBM Q (for IBM Q,
                including the hub, group and project in the URL).
                This parameter is deprecated.
            overwrite (bool): overwrite existing credentials. This parameter is deprecated.
            **kwargs (dict): This parameter is deprecated.
                * proxies (dict): Proxy configuration for the API.
                * verify (bool): If False, ignores SSL certificates errors
        """
        if token is not None:
            extra_msg = "" if self._credentials is not None else \
                " Please use IBM Q Experience 2, which offers a single account, instead."
            warnings.warn('save_account() will no longer take token, url, '
                          'and other account related parameters.' + extra_msg,
                          DeprecationWarning)
        if self._credentials is not None:
            raise NotImplementedError
        else:
            self._v1_provider.save_account(token, url=url, overwrite=overwrite, **kwargs)

    def delete_account(self):
        """Delete saved account from disk"""
        raise NotImplementedError

    def stored_account(self):
        """List the account stored on disk"""
        raise NotImplementedError

    # Deprecated account management functions for backward compatibility.

    def active_accounts(self):
        """List all accounts currently in the session.

        Returns:
            list[dict]: a list with information about the accounts currently
                in the session.
        """
        warnings.warn('active_accounts() is being deprecated. '
                      'Please use IBM Q Experience 2, which offers a single account, instead.',
                      DeprecationWarning)

        if self._credentials is not None:
            return [{
                'token': self._credentials.token,
                'url': self._credentials.url,
            }]
        else:
            return self._v1_provider.active_accounts()

    def disable_accounts(self, **kwargs):
        """Disable accounts in the current session, subject to optional filtering.

        The filter kwargs can be `token`, `url`, `hub`, `group`, `project`.
        If no filter is passed, all accounts in the current session will be disabled.

        Raises:
            IBMQAccountError: if no account matched the filter.
        """
        warnings.warn('disable_accounts() is being deprecated. '
                      'Please use IBM Q Experience 2 and disable_account() instead.',
                      DeprecationWarning)

        if self._credentials is not None:
            self.disable_account()
        else:
            self._v1_provider.disable_accounts(**kwargs)

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
        warnings.warn('load_accounts() is being deprecated. '
                      'Please use IBM Q Experience 2 and load_account() instead.',
                      DeprecationWarning)

        if self._credentials is not None:
            self.load_account()
        else:
            self._v1_provider.load_accounts(**kwargs)

    def delete_accounts(self, **kwargs):
        """Delete saved accounts from disk, subject to optional filtering.

        The filter kwargs can be `token`, `url`, `hub`, `group`, `project`.
        If no filter is passed, all accounts will be deleted from disk.

        Raises:
            IBMQAccountError: if no account matched the filter.
        """
        warnings.warn('delete_accounts() is being deprecated. '
                      'Please use IBM Q Experience 2 and delete_account() instead.',
                      DeprecationWarning)
        if self._credentials is not None:
            self.delete_account()
        else:
            self._v1_provider.delete_accounts(**kwargs)

    def stored_accounts(self):
        """List all accounts stored to disk.

        Returns:
            list[dict]: a list with information about the accounts stored
                on disk.
        """
        warnings.warn('stored_accounts() is being deprecated. '
                      'Please use IBM Q Experience 2 and stored_account() instead.',
                      DeprecationWarning)

        return self._v1_provider.stored_accounts()

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
        warnings.warn('IBMQ.backends() is being deprecated. '
                      'Please use providers() to find the desired AccountProvider and '
                      'AccountProvider.backends() to find its backends',
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
                                 credentials.base_url)

        service_urls = auth_client.user_urls()
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
