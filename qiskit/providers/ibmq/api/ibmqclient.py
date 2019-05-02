# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Client for accessing IBM Q."""

from .session import RetrySession
from .rest import AuthClient, ApiClient


class IBMQClient:
    """Client for programmatic access to the IBM Q API."""

    def __init__(self, api_token, auth_url):
        self.api_token = api_token
        self.auth_url = auth_url

        self.login_session = RetrySession(auth_url)
        self.auth_client = AuthClient(self.login_session)

        # Get the access token and use it in the sessions.
        access_token = self.request_access_token()
        self.login_session.access_token = access_token
        api_url = self.user_urls()['http']

        if api_url.endswith('.com?private=true'):
            api_url = '{}/api'.format(api_url.split('?')[0])

        self.api_session = RetrySession(api_url, access_token)
        self.api_client = ApiClient(self.api_session)

    def request_access_token(self):
        """Request a new access token from the API."""
        response = self.auth_client.login(self.api_token)
        return response.json()['id']

    def user_urls(self):
        response = self.auth_client.user_info()
        return response.json()['urls']
