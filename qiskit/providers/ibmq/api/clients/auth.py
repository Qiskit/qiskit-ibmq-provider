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

"""Client for accessing authentication features of IBM Q Experience."""
from typing import Dict, List, Optional, Any

from ..exceptions import AuthenticationLicenseError, RequestsApiError
from ..rest import Api, Auth
from ..session import RetrySession

from .base import BaseClient


class AuthClient(BaseClient):
    """Client for accessing authentication features of IBM Q Experience."""

    def __init__(self, api_token: str, auth_url: str, **request_kwargs: Any) -> None:
        """AuthClient constructor.

        Args:
            api_token: IBM Q Experience API token.
            auth_url: URL for the authentication service.
            **request_kwargs: arguments for the `requests` Session.
        """
        self.api_token = api_token
        self.auth_url = auth_url
        self._service_urls = {}  # type: ignore[var-annotated]

        self.client_auth = Auth(RetrySession(auth_url, **request_kwargs))
        self.client_api = self._init_service_clients(**request_kwargs)

    def _init_service_clients(self, **request_kwargs: Any) -> Api:
        """Initialize the clients used for communicating with the API and ws.

        Args:
            **request_kwargs: arguments for the `requests` Session.

        Returns:
            client for the api server.
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
        """Request a new access token from the API authentication server.

        Returns:
            access token.

        Raises:
            AuthenticationLicenseError: if the user hasn't accepted the license agreement.
            RequestsApiError: if the request failed.
        """
        try:
            response = self.client_auth.login(self.api_token)
            return response['id']
        except RequestsApiError as ex:
            response_obj = ex.original_exception.response
            if response_obj is not None and response_obj.status_code == 401:
                try:
                    error_code = response_obj.json()['error']['name']
                    if error_code == 'ACCEPT_LICENSE_REQUIRED':
                        message = response_obj.json()['error']['message']
                        raise AuthenticationLicenseError(message)
                except (ValueError, KeyError):
                    # the response did not contain the expected json.
                    pass
            raise

    # User account-related public functions.

    def user_urls(self) -> Dict[str, str]:
        """Retrieve the API URLs from the authentication server.

        Returns:
            a dict with the base URLs for the services. Currently
                supported keys:
                    * ``http``: the API URL for http communication.
                    * ``ws``: the API URL for websocket communication.
        """
        response = self.client_auth.user_info()
        return response['urls']

    def user_hubs(self) -> List[Dict[str, str]]:
        """Retrieve the hubs available to the user.

        The first entry in the list will be the default one, as indicated by
        the API (by having `isDefault` in all hub, group, project fields).

        Returns:
            a list of dicts with the hubs, which contains the keys
                `hub`, `group`, `project`.
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

        return hubs

    # Miscellaneous public functions.

    def api_version(self) -> Dict[str, str]:
        """Return the version of the API.

        Returns:
            versions of the API components.
        """
        return self.client_api.version()

    def current_access_token(self) -> Optional[str]:
        """Return the current access token.

        Returns:
            the access token in use.
        """
        return self.client_auth.session.access_token

    def current_service_urls(self) -> Dict[str, str]:
        """Return the current service URLs.

        Returns:
            a dict with the base URLs for the services, in the same
                format as `.user_urls()`.
        """
        return self._service_urls
