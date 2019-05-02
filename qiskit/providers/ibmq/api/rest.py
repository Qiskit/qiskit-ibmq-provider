# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Rest clients for accessing IBM Q."""
from functools import wraps


class RestClient:

    URL_MAP = {}

    def __init__(self, session, prefix_url=''):
        self.session = session
        self.prefix_url = prefix_url

    def get_url(self, identifier):
        return '{}{}'.format(self.prefix_url, self.URL_MAP[identifier])


class AuthClient(RestClient):

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


class ApiClient(RestClient):

    URL_MAP = {
        'backends': '/Backends/v/1',
        'hubs': '/Network'
    }

    def backend(self, backend_name):
        return BackendClient(self.session, backend_name)

    def backends(self):
        url = self.get_url('backends')
        return self.session.get(url).json()

    def hubs(self):
        url = self.get_url('hubs')
        return self.session.get(url).json()


class BackendClient(RestClient):

    URL_MAP = {
        'status': '/queue/status',
        'properties': '/properties'
    }

    def __init__(self, session, backend_name):
        self.backend_name = backend_name
        super().__init__(session, '/Backends/{}'.format(backend_name))

    def status(self):
        url = self.get_url('status')
        response = self.session.get(url).json()

        # Adjust fields according to the specs (BackendStatus).
        ret = {
            'backend_name': self.backend_name,
            'backend_version': response.get('backend_version', '0.0.0'),
            'status_msg': response.get('status', ''),
            'operational': bool(response.get('state', False))
        }

        # 'pending_jobs' is required, and should be >= 0.
        if 'lengthQueue' in response:
            ret['pending_jobs'] = max(response['lengthQueue'], 0)
        else:
            ret['pending_jobs'] = 0

        # Not part of the schema.
        if 'busy' in response:
            ret['dedicated'] = response['busy']

        return ret

    def properties(self):
        url = self.get_url('properties')
        response = self.session.get(url, params={'version': 1}).json()

        # Adjust name of the backend.
        if response:
            response['backend_name'] = self.backend_name

        return response


def with_url(url_string):
    def _outer_wrapper(func):
        @wraps(func)
        def _wrapper(self, *args, **kwargs):
            kwargs.update({'url': url_string})
            return func(self, *args, **kwargs)
        return _wrapper
    return _outer_wrapper
