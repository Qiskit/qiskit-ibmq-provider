# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Auth REST adaptor for the IBM Q Api version 2."""

from qiskit.providers.ibmq.api.rest.base import RestAdaptorBase


class Auth(RestAdaptorBase):

    URL_MAP = {
        'login': '/users/loginWithToken',
        'user_info': '/users/me',
    }

    def login(self, api_token):
        url = self.get_url('login')
        return self.session.post(url, json={'apiToken': api_token}).json()

    def user_info(self):
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
