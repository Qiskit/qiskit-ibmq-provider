# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Rest clients for accessing IBM Q."""
from functools import wraps


class RestClient:

    URL_MAP = {}

    def __init__(self, session):
        self.session = session

    def get_url(self, identifier):
        return self.URL_MAP[identifier]


class AuthClient(RestClient):

    URL_MAP = {
        'login': '/users/loginWithToken',
        'user_info': '/users/me'
    }

    def login(self, api_token):
        url = self.get_url('login')
        return self.session.post(url, json={'apiToken': api_token})

    def user_info(self):
        url = self.get_url('user_info')
        return self.session.get(url)


class ApiClient(RestClient):

    URL_MAP = {
        'backends': '/Backends/'
    }

    def backends(self):
        url = self.get_url('backends')
        return self.session.get(url)


def with_url(url_string):
    def _outer_wrapper(func):
        @wraps(func)
        def _wrapper(self, *args, **kwargs):
            kwargs.update({'url': url_string})
            return func(self, *args, **kwargs)
        return _wrapper
    return _outer_wrapper
