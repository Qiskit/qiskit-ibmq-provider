# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utilities for IBM Q API connector."""

import json
import logging
import re
import time
from urllib import parse

import requests
from requests_ntlm import HttpNtlmAuth

from .exceptions import (ApiError, CredentialsError, RegisterSizeError)


logger = logging.getLogger(__name__)

CLIENT_APPLICATION = 'qiskit-api-py'


class Credentials:
    """Credentials class that manages the tokens."""

    config_base = {'url': 'https://quantumexperience.ng.bluemix.net/api'}

    def __init__(self, token, config=None, verify=True, proxy_urls=None,
                 ntlm_credentials=None):
        self.token_unique = token
        self.verify = verify
        self.config = config
        self.proxy_urls = proxy_urls
        self.ntlm_credentials = ntlm_credentials

        # Set the extra arguments to requests (proxy and auth).
        self.extra_args = {}
        if self.proxy_urls:
            self.extra_args['proxies'] = self.proxy_urls
        if self.ntlm_credentials:
            self.extra_args['auth'] = HttpNtlmAuth(
                self.ntlm_credentials['username'],
                self.ntlm_credentials['password'])

        if not verify:
            # pylint: disable=import-error
            import requests.packages.urllib3 as urllib3
            urllib3.disable_warnings()
            print('-- Ignoring SSL errors.  This is not recommended --')
        if self.config and ("url" not in self.config):
            self.config["url"] = self.config_base["url"]
        elif not self.config:
            self.config = self.config_base

        self.data_credentials = {}
        if token:
            self.obtain_token(config=self.config)
        else:
            access_token = self.config.get('access_token', None)
            if access_token:
                user_id = self.config.get('user_id', None)
                if access_token:
                    self.set_token(access_token)
                if user_id:
                    self.set_user_id(user_id)
            else:
                self.obtain_token(config=self.config)

    def obtain_token(self, config=None):
        """Obtain the token to access to QX Platform.

        Raises:
            CredentialsError: when token is invalid or the user has not
                accepted the license.
            ApiError: when the response from the server couldn't be parsed.
        """
        client_application = CLIENT_APPLICATION
        if self.config and ("client_application" in self.config):
            client_application += ':' + self.config["client_application"]
        headers = {'x-qx-client-application': client_application}

        if self.token_unique:
            try:
                response = requests.post(str(self.config.get('url') +
                                             "/users/loginWithToken"),
                                         data={'apiToken': self.token_unique},
                                         verify=self.verify,
                                         headers=headers,
                                         **self.extra_args)
            except requests.RequestException as ex:
                raise ApiError('error during login: %s' % str(ex))
        elif config and ("email" in config) and ("password" in config):
            email = config.get('email', None)
            password = config.get('password', None)
            credentials = {
                'email': email,
                'password': password
            }
            try:
                response = requests.post(str(self.config.get('url') +
                                             "/users/login"),
                                         data=credentials,
                                         verify=self.verify,
                                         headers=headers,
                                         **self.extra_args)
            except requests.RequestException as ex:
                raise ApiError('error during login: %s' % str(ex))
        else:
            raise CredentialsError('invalid token')

        if response.status_code == 401:
            error_message = None
            try:
                # For 401: ACCEPT_LICENSE_REQUIRED, a detailed message is
                # present in the response and passed to the exception.
                error_message = response.json()['error']['message']
            except Exception:  # pylint: disable=broad-except
                pass

            if error_message:
                raise CredentialsError('error during login: %s' % error_message)
            raise CredentialsError('invalid token')
        try:
            response.raise_for_status()
            self.data_credentials = response.json()
        except (requests.HTTPError, ValueError) as ex:
            raise ApiError('error during login: %s' % str(ex))

        if self.get_token() is None:
            raise CredentialsError('invalid token')

    def get_token(self):
        """Return the Authenticated Token to connect with QX Platform."""
        return self.data_credentials.get('id', None)

    def get_user_id(self):
        """Return the user id in QX platform."""
        return self.data_credentials.get('userId', None)

    def get_config(self):
        """Return the configuration that was set for this Credentials."""
        return self.config

    def set_token(self, access_token):
        """Set the Access Token to connect with QX Platform API."""
        self.data_credentials['id'] = access_token

    def set_user_id(self, user_id):
        """Set the user id to connect with QX Platform API."""
        self.data_credentials['userId'] = user_id


class Request:
    """Request class that performs the HTTP calls.

    Note:
        Set the proxy information, if present, from the configuration,
        with the following format::

        config = {
            'proxies': {
                # If using 'urls', assume basic auth or no auth.
                'urls': {
                    'http': 'http://user:password@1.2.3.4:5678',
                    'https': 'http://user:password@1.2.3.4:5678',
                }
                # If using 'ntlm', assume NTLM authentication.
                'username_ntlm': 'domain\\username',
                'password_ntlm': 'password'
            }
        }
    """

    def __init__(self, token, config=None, verify=True, retries=5,
                 timeout_interval=1.0):
        self.verify = verify
        self.client_application = CLIENT_APPLICATION
        self.config = config
        self.errors_not_retry = [401, 403, 413]

        # Set the basic proxy settings, if present.
        self.proxy_urls = None
        self.ntlm_credentials = None
        if config and 'proxies' in config:
            if 'urls' in config['proxies']:
                self.proxy_urls = self.config['proxies']['urls']
            if 'username_ntlm' and 'password_ntlm' in config['proxies']:
                self.ntlm_credentials = {
                    'username': self.config['proxies']['username_ntlm'],
                    'password': self.config['proxies']['password_ntlm']
                }

        # Set the extra arguments to requests (proxy and auth).
        self.extra_args = {}
        if self.proxy_urls:
            self.extra_args['proxies'] = self.proxy_urls
        if self.ntlm_credentials:
            self.extra_args['auth'] = HttpNtlmAuth(
                self.ntlm_credentials['username'],
                self.ntlm_credentials['password'])

        if self.config and ("client_application" in self.config):
            self.client_application += ':' + self.config["client_application"]
        self.credential = Credentials(token, self.config, verify,
                                      proxy_urls=self.proxy_urls,
                                      ntlm_credentials=self.ntlm_credentials)

        if not isinstance(retries, int):
            raise TypeError('post retries must be positive integer')
        self.retries = retries
        self.timeout_interval = timeout_interval
        self.result = None
        self._max_qubit_error_re = re.compile(
            r".*registers exceed the number of qubits, "
            r"it can\'t be greater than (\d+).*")

    def check_token(self, response):
        """Check is the user's token is valid."""
        if response.status_code == 401:
            self.credential.obtain_token(config=self.config)
            return False
        return True

    def post(self, path, params='', data=None):
        """POST Method Wrapper of the REST API."""
        self.result = None
        data = data or {}
        headers = {'Content-Type': 'application/json',
                   'x-qx-client-application': self.client_application}
        url = str(self.credential.config['url'] + path + '?access_token=' +
                  self.credential.get_token() + params)
        retries = self.retries
        while retries > 0:
            response = requests.post(url, data=data, headers=headers,
                                     verify=self.verify, **self.extra_args)
            if not self.check_token(response):
                response = requests.post(url, data=data, headers=headers,
                                         verify=self.verify,
                                         **self.extra_args)

            if self._response_good(response):
                if self.result:
                    return self.result
                elif retries < 2:
                    return response.json()
                else:
                    retries -= 1
            else:
                retries -= 1
                time.sleep(self.timeout_interval)

        # timed out
        raise ApiError(usr_msg='Failed to get proper ' +
                       'response from backend.')

    def put(self, path, params='', data=None):
        """PUT Method Wrapper of the REST API."""
        self.result = None
        data = data or {}
        headers = {'Content-Type': 'application/json',
                   'x-qx-client-application': self.client_application}
        url = str(self.credential.config['url'] + path + '?access_token=' +
                  self.credential.get_token() + params)
        retries = self.retries
        while retries > 0:
            response = requests.put(url, data=data, headers=headers,
                                    verify=self.verify, **self.extra_args)
            if not self.check_token(response):
                response = requests.put(url, data=data, headers=headers,
                                        verify=self.verify,
                                        **self.extra_args)
            if self._response_good(response):
                if self.result:
                    return self.result
                elif retries < 2:
                    return response.json()
                else:
                    retries -= 1
            else:
                retries -= 1
                time.sleep(self.timeout_interval)
        # timed out
        raise ApiError(usr_msg='Failed to get proper ' +
                       'response from backend.')

    def get(self, path, params='', with_token=True):
        """GET Method Wrapper of the REST API."""
        self.result = None
        access_token = ''
        if with_token:
            access_token = self.credential.get_token() or ''
            if access_token:
                access_token = '?access_token=' + str(access_token)
        url = self.credential.config['url'] + path + access_token + params
        retries = self.retries
        headers = {'x-qx-client-application': self.client_application}
        while retries > 0:  # Repeat until no error
            response = requests.get(url, verify=self.verify, headers=headers,
                                    **self.extra_args)
            if not self.check_token(response):
                response = requests.get(url, verify=self.verify,
                                        headers=headers, **self.extra_args)
            if self._response_good(response):
                if self.result:
                    return self.result
                elif retries < 2:
                    return response.json()
                else:
                    retries -= 1
            else:
                retries -= 1
                time.sleep(self.timeout_interval)
        # timed out
        raise ApiError(usr_msg='Failed to get proper ' +
                       'response from backend.')

    def _sanitize_url(self, url):
        """Strip any tokens or actual paths from url.

        Args:
            url (str): The url to sanitize

        Returns:
           str: The sanitized url
        """
        return parse.urlparse(url).path

    def _response_good(self, response):
        """check response.

        Args:
            response (requests.Response): HTTP response.

        Returns:
            bool: True if the response is good, else False.

        Raises:
            ApiError: response isn't formatted properly.
        """

        url = self._sanitize_url(response.url)

        if response.status_code != requests.codes.ok:
            if 'QCircuitApiModels' in url:
                # Reduce verbosity for Circuits invocation.
                # TODO: reenable once the API is more stable.
                logger.debug('Got a %s code response to %s: %s',
                             response.status_code,
                             url,
                             response.text)
            else:
                logger.warning('Got a %s code response to %s: %s',
                               response.status_code,
                               url,
                               response.text)
            if response.status_code in self.errors_not_retry:
                raise ApiError(usr_msg='Got a {} code response to {}: {}'.format(
                    response.status_code,
                    url,
                    response.text))
            return self._parse_response(response)
        try:
            if str(response.headers['content-type']).startswith("text/html;"):
                self.result = response.text
                return True
            else:
                self.result = response.json()
        except (json.JSONDecodeError, ValueError):
            usr_msg = 'device server returned unexpected http response'
            dev_msg = usr_msg + ': ' + response.text
            raise ApiError(usr_msg=usr_msg, dev_msg=dev_msg)
        if not isinstance(self.result, (list, dict)):
            msg = ('JSON not a list or dict: url: {0},'
                   'status: {1}, reason: {2}, text: {3}')
            raise ApiError(
                usr_msg=msg.format(url,
                                   response.status_code,
                                   response.reason, response.text))
        if ('error' not in self.result or
                ('status' not in self.result['error'] or
                 self.result['error']['status'] != 400)):
            return True

        logger.warning("Got a 400 code JSON response to %s", url)
        return False

    def _parse_response(self, response):
        """parse text of response for HTTP errors.

        This parses the text of the response to decide whether to
        retry request or raise exception. At the moment this only
        detects an exception condition.

        Args:
            response (Response): requests.Response object

        Returns:
            bool: False if the request should be retried, True
                if not.

        Raises:
            RegisterSizeError: if invalid device register size.
        """
        # convert error messages into exceptions
        mobj = self._max_qubit_error_re.match(response.text)
        if mobj:
            raise RegisterSizeError(
                'device register size must be <= {}'.format(mobj.group(1)))
        return True
