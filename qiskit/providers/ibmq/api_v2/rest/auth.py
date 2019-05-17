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

        return response
