# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Auth REST adapter for the IBM Q Api version 2."""

from .base import RestAdapterBase


class Auth(RestAdapterBase):
    """Rest adapter for authentication endpoints."""

    URL_MAP = {
        'login': '/users/loginWithToken',
        'user_info': '/users/me',
    }

    def login(self, api_token):
        """Login with token.

        Args:
            api_token (str): API token.

        Returns:
            dict: json response.
        """
        url = self.get_url('login')
        return self.session.post(url, json={'apiToken': api_token}).json()

    def user_info(self):
        """Return user information."""
        url = self.get_url('user_info')
        response = self.session.get(url).json()

        # Revise the URL.
        try:
            api_url = response['urls']['http']
            if api_url.endswith('.com?private=true'):
                response['urls']['http'] = '{}/api'.format(
                    api_url.split('?')[0])
        except KeyError:
            pass

        return response
