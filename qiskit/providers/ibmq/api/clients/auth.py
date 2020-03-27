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

"""Client for accessing IBM Quantum Experience authentication services."""

import logging
from typing import Dict, List, Optional, Any
from requests.exceptions import RequestException

from qiskit.providers.ibmq.credentials import Credentials
from qiskit.providers.ibmq.credentials.utils import get_provider_as_str
from ..exceptions import AuthenticationLicenseError, RequestsApiError
from ..rest import Api, Auth
from ..session import RetrySession

from .base import BaseClient

logger = logging.getLogger(__name__)


class AuthClient(BaseClient):
    """Client for accessing IBM Quantum Experience authentication services."""

    def __init__(self, api_token: str, auth_url: str, **request_kwargs: Any) -> None:
        """AuthClient constructor.

        Args:
            api_token: IBM Quantum Experience API token.
            auth_url: URL for the authentication service.
            **request_kwargs: Arguments for the request ``Session``.
        """
        self.api_token = api_token
        self.auth_url = auth_url
        self._service_urls = {}  # type: ignore[var-annotated]

        self.client_auth = Auth(RetrySession(auth_url, **request_kwargs))
        self.client_api = self._init_service_clients(**request_kwargs)

    def _init_service_clients(self, **request_kwargs: Any) -> Api:
        """Initialize the clients used for communicating with the API.

        Args:
            **request_kwargs: Arguments for the request ``Session``.

        Returns:
            Client for the API server.
        """
        # Request an access token.
        access_token = self._request_access_token()
        # Use the token for the next auth server requests.
        self.client_auth.session.access_token = access_token
        self._service_urls = self.user_urls()

        # Create the api server client, using the access token.
        client_api = Api(RetrySession(self._service_urls['http'], access_token,
                                      **request_kwargs))

        return client_api

    def _request_access_token(self) -> str:
        """Request a new access token from the API authentication service.

        Returns:
            A new access token.

        Raises:
            AuthenticationLicenseError: If the user hasn't accepted the license agreement.
            RequestsApiError: If the request failed.
        """
        try:
            response = self.client_auth.login(self.api_token)
            return response['id']
        except RequestsApiError as ex:
            # Get the original exception that raised.
            original_exception = ex.__cause__

            if isinstance(original_exception, RequestException):
                # Get the response from the original request exception.
                error_response = original_exception.response    # pylint: disable=no-member
                if error_response is not None and error_response.status_code == 401:
                    try:
                        error_code = error_response.json()['error']['name']
                        if error_code == 'ACCEPT_LICENSE_REQUIRED':
                            message = error_response.json()['error']['message']
                            raise AuthenticationLicenseError(message)
                    except (ValueError, KeyError):
                        # the response did not contain the expected json.
                        pass
            raise

    # User account-related public functions.

    def user_urls(self) -> Dict[str, str]:
        """Retrieve the API URLs from the authentication service.

        Returns:
            A dict with the base URLs for the services. Currently
            supported keys are:

                * ``http``: The API URL for HTTP communication.
                * ``ws``: The API URL for websocket communication.
        """
        response = self.client_auth.user_info()
        return response['urls']

    def user_hubs(self, credentials: Credentials) -> List[Dict[str, str]]:
        """Retrieve the hub/group/project sets available to the user.

        The first entry in the list will be the default provider that is set.
        If `credentials` specifies a provider, given by its `hub`, `group`,
        and `project` fields, an attempt will be made to set it as the default.
        However, if the specified provider cannot be found as an entry in the
        user hubs, the default one, indicated by the ``isDefault`` field from
        the API, will be set.

        Args:
            credentials: The `Credentials` used to determine if a specific provider
                should be set as the default.

        Returns:
            A list of dictionaries with the hub, group, and project values keyed by
            ``hub``, ``group``, and ``project``, respectively.
        """
        response = self.client_api.hubs()

        hubs = []  # type: ignore[var-annotated]
        for hub in response:
            hub_name = hub['name']
            for group_name, group in hub['groups'].items():
                for project_name, project in group['projects'].items():
                    entry = {'hub': hub_name,
                             'group': group_name,
                             'project': project_name}

                    # Move to the top if it is the default h/g/p.
                    if project.get('isDefault'):
                        hubs.insert(0, entry)
                    else:
                        hubs.append(entry)

        # Check to see if a default hub/group/project should be set as the default provider,
        # as specified by `hub`, `group`, `project` attributes of `credentials`.
        default_hgp_index = self._get_default_hgp_index(credentials, hubs)
        if isinstance(default_hgp_index, int):
            # Move the default hub/group/project to the front.
            hubs[0], hubs[default_hgp_index] = hubs[default_hgp_index], hubs[0]

        return hubs

    def _get_default_hgp_index(
            self,
            credentials: Credentials,
            user_hubs: List[Dict[str, str]]
    ) -> Optional[int]:
        """Returns the index of the hub/group/project, specified by `credentials`, in `user_hubs`.

        Args:
            credentials: The `Credentials` containing the hub/group/project information of
                the provider to set as the default.
            user_hubs: A list of dictionaries with the hub, group, and project values keyed
                by ``hub``, ``group``, and ``project``, respectively.

        Returns:
            The index of the hub/group/project, specified by `credentials`, in `user_hubs`,
            else ``None``.
        """
        # The default provider, as a dictionary, specified within `credentials`.
        default_hgp_entry = {'hub': credentials.hub,
                             'group': credentials.group,
                             'project': credentials.project}

        if all(default_hgp_entry.values()):
            try:
                # If `default_hgp_entry` is found, return its index in the list.
                return user_hubs.index(default_hgp_entry)
            except ValueError:
                # `default_hgp_entry` was not found.
                provider_as_str = get_provider_as_str(default_hgp_entry)
                logger.warning('The specified hub/group/project "%s" was not found in '
                               'the hubs you have access to %s. The default hub/group/project '
                               'you have access to "%s" will be used.',
                               provider_as_str, str(user_hubs), str(user_hubs[0]))
        return None

    # Miscellaneous public functions.

    def api_version(self) -> Dict[str, str]:
        """Return the version of the API.

        Returns:
            API version.
        """
        return self.client_api.version()

    def current_access_token(self) -> Optional[str]:
        """Return the current access token.

        Returns:
            The access token in use.
        """
        return self.client_auth.session.access_token

    def current_service_urls(self) -> Dict[str, str]:
        """Return the current service URLs.

        Returns:
            A dict with the base URLs for the services, in the same
            format as :meth:`user_urls()`.
        """
        return self._service_urls
