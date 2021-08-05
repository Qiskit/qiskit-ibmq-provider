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

"""Factory and Account manager for IBM Quantum Experience."""

import logging
from typing import Dict, List, Union, Callable, Optional, Any
from collections import OrderedDict
import traceback

from .accountprovider import AccountProvider
from .api.clients import AuthClient, VersionClient
from .credentials import Credentials, discover_credentials
from .credentials.hubgroupproject import HubGroupProject
from .credentials.configrc import (read_credentials_from_qiskitrc,
                                   remove_credentials,
                                   store_credentials)
from .credentials.exceptions import HubGroupProjectInvalidStateError
from .credentials.updater import update_credentials
from .exceptions import (IBMQAccountError, IBMQAccountValueError, IBMQProviderError,
                         IBMQAccountCredentialsInvalidFormat, IBMQAccountCredentialsNotFound,
                         IBMQAccountCredentialsInvalidUrl, IBMQAccountCredentialsInvalidToken,
                         IBMQAccountMultipleCredentialsFound)

logger = logging.getLogger(__name__)

QX_AUTH_URL = 'https://auth.quantum-computing.ibm.com/api'
UPDATE_ACCOUNT_TEXT = "Please update your accounts and programs by following the " \
                      "instructions here: https://github.com/Qiskit/qiskit-ibmq-provider#" \
                      "updating-to-the-new-ibm-q-experience "


class IBMQFactory:
    """Factory and account manager for IBM Quantum Experience."""

    def __init__(self) -> None:
        """IBMQFactory constructor."""
        self._credentials = None  # type: Optional[Credentials]
        self._providers = OrderedDict()  # type: Dict[HubGroupProject, AccountProvider]

    # Account management functions.

    def enable_account(
            self,
            token: str,
            url: str = QX_AUTH_URL,
            hub: Optional[str] = None,
            group: Optional[str] = None,
            project: Optional[str] = None,
            **kwargs: Any
    ) -> Optional[AccountProvider]:
        """Authenticate against IBM Quantum Experience for use during the session.

        Note:
            With version 0.4 of this ``qiskit-ibmq-provider`` package, use of
            the legacy Quantum Experience and Qconsole (also known as the
            IBM Quantum Experience v1) credentials is no longer supported.

        Args:
            token: IBM Quantum Experience token.
            url: URL for the IBM Quantum Experience authentication server.
            hub: Name of the hub to use.
            group: Name of the group to use.
            project: Name of the project to use.
            **kwargs: Additional settings for the connection:

                * proxies (dict): proxy configuration.
                * verify (bool): verify the server's TLS certificate.

        Returns:
            If `hub`, `group`, and `project` are specified, the corresponding provider
            is returned. Otherwise the provider for the open access project is returned.

        Raises:
            IBMQAccountError: If an IBM Quantum Experience account is already in
                use for the session.
            IBMQAccountCredentialsInvalidUrl: If the URL specified is not
                a valid IBM Quantum Experience authentication URL.
            IBMQProviderError: If no provider matches the specified criteria,
                or more than one provider matches the specified criteria.
        """
        # Check if an IBM Quantum Experience account is already in use.
        if self._credentials:
            raise IBMQAccountError(
                'An IBM Quantum Experience account is already in use for the session.')

        # Check the version used by these credentials.
        credentials = Credentials(token, url, **kwargs)
        version_info = self._check_api_version(credentials)

        # Check the URL is a valid authentication URL.
        if not version_info['new_api'] or 'api-auth' not in version_info:
            raise IBMQAccountCredentialsInvalidUrl(
                'The URL specified ({}) is not an IBM Quantum Experience authentication '
                'URL. Valid authentication URL: {}.'.format(credentials.url, QX_AUTH_URL))

        # Initialize the providers.
        self._initialize_providers(credentials)

        # Prevent edge case where no hubs are available.
        providers = self.providers()
        if not providers:
            logger.warning('No Hub/Group/Projects could be found for this '
                           'account.')
            return None

        # The provider for the default open access project.
        default_provider = providers[0]

        # If any `hub`, `group`, or `project` is specified, return the corresponding provider.
        if any([hub, group, project]):
            default_provider = self.get_provider(hub=hub, group=group, project=project)

        return default_provider

    def disable_account(self) -> None:
        """Disable the account currently in use for the session.

        Raises:
            IBMQAccountCredentialsNotFound: If no account is in use for the session.
        """
        if not self._credentials:
            raise IBMQAccountCredentialsNotFound(
                'No IBM Quantum Experience account is in use for the session.')

        self._credentials = None
        self._providers = OrderedDict()

    def load_account(self) -> Optional[AccountProvider]:
        """Authenticate against IBM Quantum Experience from stored credentials.

        Returns:
            If the configuration file specifies a default provider, it is returned.
            Otherwise the provider for the open access project is returned.

        Raises:
            IBMQAccountCredentialsInvalidFormat: If the default provider stored on
                disk could not be parsed.
            IBMQAccountCredentialsNotFound: If no IBM Quantum Experience credentials
                can be found.
            IBMQAccountMultipleCredentialsFound: If multiple IBM Quantum Experience
                credentials are found.
            IBMQAccountCredentialsInvalidUrl: If invalid IBM Quantum Experience
                credentials are found.
            IBMQProviderError: If the default provider stored on disk could not
                be found.
        """
        # Check for valid credentials.
        try:
            stored_credentials, preferences = discover_credentials()
        except HubGroupProjectInvalidStateError as ex:
            raise IBMQAccountCredentialsInvalidFormat(
                'Invalid provider (hub/group/project) data found {}'.format(str(ex))) from ex

        credentials_list = list(stored_credentials.values())

        if not credentials_list:
            raise IBMQAccountCredentialsNotFound(
                'No IBM Quantum Experience credentials found.')

        if len(credentials_list) > 1:
            raise IBMQAccountMultipleCredentialsFound(
                'Multiple IBM Quantum Experience credentials found. ' + UPDATE_ACCOUNT_TEXT)

        credentials = credentials_list[0]
        # Explicitly check via a server call, to allow environment auth URLs
        # contain IBM Quantum Experience v2 URL (but not auth) slipping through.
        version_info = self._check_api_version(credentials)

        # Check the URL is a valid authentication URL.
        if not version_info['new_api'] or 'api-auth' not in version_info:
            raise IBMQAccountCredentialsInvalidUrl(
                'Invalid IBM Quantum Experience credentials found. ' + UPDATE_ACCOUNT_TEXT)

        # Initialize the providers.
        if self._credentials:
            # For convention, emit a warning instead of raising.
            logger.warning('Credentials are already in use. The existing '
                           'account in the session will be replaced.')
            self.disable_account()

        self._initialize_providers(credentials, preferences)

        # Prevent edge case where no hubs are available.
        providers = self.providers()
        if not providers:
            logger.warning('No Hub/Group/Projects could be found for this account.')
            return None

        # The provider for the default open access project.
        default_provider = providers[0]

        # If specified, attempt to get the provider stored for the account.
        if credentials.default_provider:
            hub, group, project = credentials.default_provider.to_tuple()
            try:
                default_provider = self.get_provider(hub=hub, group=group, project=project)
            except IBMQProviderError as ex:
                raise IBMQProviderError('The default provider (hub/group/project) stored on '
                                        'disk could not be found: {}.'
                                        'To overwrite the default provider stored on disk, use '
                                        'the save_account(overwrite=True) method and specify the '
                                        'default provider you would like to save.'
                                        .format(str(ex))) from None

        return default_provider

    @staticmethod
    def save_account(
            token: str,
            url: str = QX_AUTH_URL,
            hub: Optional[str] = None,
            group: Optional[str] = None,
            project: Optional[str] = None,
            overwrite: bool = False,
            **kwargs: Any
    ) -> None:
        """Save the account to disk for future use.

        Note:
            If storing a default provider to disk, all three parameters
            `hub`, `group`, `project` must be specified.

        Args:
            token: IBM Quantum Experience token.
            url: URL for the IBM Quantum Experience authentication server.
            hub: Name of the hub for the default provider to store on disk.
            group: Name of the group for the default provider to store on disk.
            project: Name of the project for the default provider to store on disk.
            overwrite: Overwrite existing credentials.
            **kwargs:
                * proxies (dict): Proxy configuration for the server.
                * verify (bool): If False, ignores SSL certificates errors

        Raises:
            IBMQAccountCredentialsInvalidUrl: If the `url` is not a valid
                IBM Quantum Experience authentication URL.
            IBMQAccountCredentialsInvalidToken: If the `token` is not a valid
                IBM Quantum Experience token.
            IBMQAccountValueError: If only one or two parameters from `hub`, `group`,
                `project` are specified.
        """
        if url != QX_AUTH_URL:
            raise IBMQAccountCredentialsInvalidUrl(
                'Invalid IBM Q Experience credentials found. ' + UPDATE_ACCOUNT_TEXT)

        if not token or not isinstance(token, str):
            raise IBMQAccountCredentialsInvalidToken(
                'Invalid IBM Quantum Experience token '
                'found: "{}" of type {}.'.format(token, type(token)))

        # If any `hub`, `group`, or `project` is specified, make sure all parameters are set.
        if any([hub, group, project]) and not all([hub, group, project]):
            raise IBMQAccountValueError('The hub, group, and project parameters must all be '
                                        'specified when storing a default provider to disk: '
                                        'hub = "{}", group = "{}", project = "{}"'
                                        .format(hub, group, project))

        # If specified, get the provider to store.
        default_provider_hgp = HubGroupProject(hub, group, project) \
            if all([hub, group, project]) else None

        credentials = Credentials(token=token, url=url,
                                  default_provider=default_provider_hgp, **kwargs)

        store_credentials(credentials,
                          overwrite=overwrite)

    @staticmethod
    def delete_account() -> None:
        """Delete the saved account from disk.

        Raises:
            IBMQAccountCredentialsNotFound: If no valid IBM Quantum Experience
                credentials can be found on disk.
            IBMQAccountMultipleCredentialsFound: If multiple IBM Quantum Experience
                credentials are found on disk.
            IBMQAccountCredentialsInvalidUrl: If invalid IBM Quantum Experience
                credentials are found on disk.
        """
        stored_credentials, _ = read_credentials_from_qiskitrc()
        if not stored_credentials:
            raise IBMQAccountCredentialsNotFound(
                'No IBM Quantum Experience credentials found on disk.')

        if len(stored_credentials) != 1:
            raise IBMQAccountMultipleCredentialsFound(
                'Multiple IBM Quantum Experience credentials found on disk. ' + UPDATE_ACCOUNT_TEXT)

        credentials = list(stored_credentials.values())[0]

        if credentials.url != QX_AUTH_URL:
            raise IBMQAccountCredentialsInvalidUrl(
                'Invalid IBM Quantum Experience credentials found on disk. ' + UPDATE_ACCOUNT_TEXT)

        remove_credentials(credentials)

    @staticmethod
    def stored_account() -> Dict[str, str]:
        """List the account stored on disk.

        Returns:
            A dictionary with information about the account stored on disk.

        Raises:
            IBMQAccountMultipleCredentialsFound: If multiple IBM Quantum Experience
                credentials are found on disk.
            IBMQAccountCredentialsInvalidUrl: If invalid IBM Quantum Experience
                credentials are found on disk.
        """
        stored_credentials, _ = read_credentials_from_qiskitrc()
        if not stored_credentials:
            return {}

        if len(stored_credentials) > 1:
            raise IBMQAccountMultipleCredentialsFound(
                'Multiple IBM Quantum Experience credentials found on disk. ' + UPDATE_ACCOUNT_TEXT)

        credentials = list(stored_credentials.values())[0]

        if credentials.url != QX_AUTH_URL:
            raise IBMQAccountCredentialsInvalidUrl(
                'Invalid IBM Quantum Experience credentials found on disk. ' + UPDATE_ACCOUNT_TEXT)

        return {
            'token': credentials.token,
            'url': credentials.url
        }

    def active_account(self) -> Optional[Dict[str, str]]:
        """Return the IBM Quantum Experience account currently in use for the session.

        Returns:
            Information about the account currently in the session.
        """
        if not self._credentials:
            # Return None instead of raising, maintaining the same behavior
            # of the classic active_accounts() method.
            return None

        return {
            'token': self._credentials.token,
            'url': self._credentials.url,
        }

    @staticmethod
    def update_account(force: bool = False) -> Optional[Credentials]:
        """Interactive helper for migrating stored credentials to IBM Quantum Experience v2.

        Args:
            force: If ``True``, disable interactive prompts and perform the changes.

        Returns:
            The credentials for IBM Quantum Experience v2 if updating is successful
            or ``None`` otherwise.
        """
        return update_credentials(force)

    # Provider management functions.

    def providers(
            self,
            hub: Optional[str] = None,
            group: Optional[str] = None,
            project: Optional[str] = None
    ) -> List[AccountProvider]:
        """Return a list of providers, subject to optional filtering.

        Args:
            hub: Name of the hub.
            group: Name of the group.
            project: Name of the project.

        Returns:
            A list of providers that match the specified criteria.
        """
        filters = []  # type: List[Callable[[HubGroupProject], bool]]

        if hub:
            filters.append(lambda hgp: hgp.hub == hub)
        if group:
            filters.append(lambda hgp: hgp.group == group)
        if project:
            filters.append(lambda hgp: hgp.project == project)

        providers = [provider for key, provider in self._providers.items()
                     if all(f(key) for f in filters)]

        return providers

    def get_provider(
            self,
            hub: Optional[str] = None,
            group: Optional[str] = None,
            project: Optional[str] = None
    ) -> AccountProvider:
        """Return a provider for a single hub/group/project combination.

        Args:
            hub: Name of the hub.
            group: Name of the group.
            project: Name of the project.

        Returns:
            A provider that matches the specified criteria.

        Raises:
            IBMQProviderError: If no provider matches the specified criteria,
                or more than one provider matches the specified criteria.
        """
        providers = self.providers(hub, group, project)

        if not providers:
            raise IBMQProviderError('No provider matches the specified criteria: '
                                    'hub = {}, group = {}, project = {}'
                                    .format(hub, group, project))
        if len(providers) > 1:
            raise IBMQProviderError('More than one provider matches the specified criteria.'
                                    'hub = {}, group = {}, project = {}'
                                    .format(hub, group, project))

        return providers[0]

    # Private functions.

    @staticmethod
    def _check_api_version(credentials: Credentials) -> Dict[str, Union[bool, str]]:
        """Check the version of the remote server in a set of credentials.

        Returns:
            A dictionary with version information.
        """
        version_finder = VersionClient(credentials.base_url,
                                       **credentials.connection_parameters())
        return version_finder.version()

    def _initialize_providers(
            self, credentials: Credentials,
            preferences: Optional[Dict] = None
    ) -> None:
        """Authenticate against IBM Quantum and populate the providers.

        Args:
            credentials: Credentials for IBM Quantum.
            preferences: Account preferences.
        """
        auth_client = AuthClient(credentials.token,
                                 credentials.base_url,
                                 **credentials.connection_parameters())
        service_urls = auth_client.current_service_urls()
        user_hubs = auth_client.user_hubs()
        preferences = preferences or {}

        self._credentials = credentials
        for hub_info in user_hubs:
            # Build credentials.
            provider_credentials = Credentials(
                credentials.token,
                access_token=auth_client.current_access_token(),
                url=service_urls['http'],
                websockets_url=service_urls['ws'],
                proxies=credentials.proxies,
                verify=credentials.verify,
                services=service_urls.get('services', {}),
                default_provider=credentials.default_provider,
                **hub_info, )
            provider_credentials.preferences = \
                preferences.get(provider_credentials.unique_id(), {})

            # Build the provider.
            try:
                provider = AccountProvider(provider_credentials, self)
                self._providers[provider_credentials.unique_id()] = provider
            except Exception:  # pylint: disable=broad-except
                # Catch-all for errors instantiating the provider.
                logger.warning('Unable to instantiate provider for %s: %s',
                               hub_info, traceback.format_exc())
