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

from collections import OrderedDict

from .api_v2.clients import AuthClient, VersionClient
from .credentials import Credentials
from .exceptions import IBMQApiURLError, IBMQProviderError
from .accountprovider import AccountProvider


QX_AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'


class IBMQFactory:
    """Factory and credentials manager for IBM Q Experience."""

    def __init__(self):
        self._credentials = None
        self._providers = OrderedDict()

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
        """
        # TODO: check and clean kwargs (verify str, proxies)
        self._initialize_providers(Credentials(token, url, **kwargs))

        return self.providers()[0]

    def disable_account(self):
        raise NotImplementedError

    def load_account(self):
        """Authenticate against IBM Q Experience from stored credentials.

        Returns:
            AccountProvider: the provider for the default open access project.
        """
        raise NotImplementedError

    def save_account(self):
        raise NotImplementedError

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
            raise IBMQProviderError('No providers matching the criteria')
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
            IBMQApiURLError: if the credentials do not belong to a IBM Q
                Experience authentication URL.
        """
        # TODO: add checks (overwrite, mixing old and new)
        version_info = self._check_api_version(credentials)

        if not (version_info['new_api'] and 'api-auth' in version_info):
            raise IBMQApiURLError(
                'The URL specified ({}) is not a IBM Q Experience '
                'authentication URL'.format(credentials.url))

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
