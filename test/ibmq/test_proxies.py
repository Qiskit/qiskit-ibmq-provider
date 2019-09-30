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

"""Tests for the AuthClient and VersionClient proxy support."""


from unittest import skipIf
import urllib
import subprocess
import sys

from requests.exceptions import ProxyError

from qiskit.providers.ibmq import IBMQFactory
from qiskit.providers.ibmq.api_v2.clients import (AuthClient,
                                                  VersionClient)
from qiskit.providers.ibmq.api_v2.exceptions import RequestsApiError
from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_qe_access, requires_new_api_auth


ADDRESS = '127.0.0.1'
PORT = 8080
VALID_PROXIES = {'https': 'http://{}:{}'.format(ADDRESS, PORT)}
INVALID_PORT_PROXIES = {'https': '{}:{}'.format(ADDRESS, '6666')}
INVALID_ADDRESS_PROXIES = {'https': '{}:{}'.format('invalid', PORT)}


@skipIf(sys.version_info >= (3, 7), 'pproxy version not supported in 3.7')
class TestProxies(IBMQTestCase):
    """Tests for proxy capabilities."""

    def setUp(self):
        super().setUp()

        # launch a mock server.
        command = ['pproxy', '-v', '-i', 'http://{}:{}'.format(ADDRESS, PORT)]
        self.proxy_process = subprocess.Popen(command, stdout=subprocess.PIPE)

    def tearDown(self):
        super().tearDown()

        # terminate the mock server.
        if self.proxy_process.returncode is None:
            self.proxy_process.stdout.close()  # close the IO buffer
            self.proxy_process.terminate()  # initiate process termination

            # wait for the process to terminate
            self.proxy_process.wait()

    @requires_qe_access
    def test_proxies_factory(self, qe_token, qe_url):
        """Should reach the proxy using factory.enable_account."""
        factory = IBMQFactory()
        provider = factory.enable_account(qe_token, qe_url,
                                          proxies={'urls': VALID_PROXIES})

        self.proxy_process.terminate()  # kill to be able of reading the output

        auth_line = pproxy_desired_access_log_line(qe_url)
        api_line = pproxy_desired_access_log_line(provider.credentials.url)
        proxy_output = self.proxy_process.stdout.read().decode('utf-8')

        # Check if the authentication call went through proxy.
        self.assertIn(auth_line, proxy_output)
        # Check if the API call (querying providers list) went through proxy.
        self.assertIn(api_line, proxy_output)

    @requires_qe_access
    @requires_new_api_auth
    def test_proxies_authclient(self, qe_token, qe_url):
        """Should reach the proxy using AuthClient."""
        pproxy_desired_access_log_line_ = pproxy_desired_access_log_line(qe_url)

        _ = AuthClient(qe_token, qe_url, proxies=VALID_PROXIES)

        self.proxy_process.terminate()  # kill to be able of reading the output
        self.assertIn(pproxy_desired_access_log_line_,
                      self.proxy_process.stdout.read().decode('utf-8'))

    # pylint: disable=unused-argument
    @requires_qe_access
    @requires_new_api_auth
    def test_proxies_versionclient(self, qe_token, qe_url):
        """Should reach the proxy using IBMQVersionFinder."""
        pproxy_desired_access_log_line_ = pproxy_desired_access_log_line(qe_url)

        version_finder = VersionClient(qe_url, proxies=VALID_PROXIES)
        version_finder.version()

        self.proxy_process.terminate()  # kill to be able of reading the output
        self.assertIn(pproxy_desired_access_log_line_,
                      self.proxy_process.stdout.read().decode('utf-8'))

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_port_authclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using AuthClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            _ = AuthClient(qe_token, qe_url, proxies=INVALID_PORT_PROXIES)

        self.assertIsInstance(context_manager.exception.original_exception,
                              ProxyError)

    # pylint: disable=unused-argument
    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_port_versionclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using VersionClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            version_finder = VersionClient(qe_url, proxies=INVALID_PORT_PROXIES)
            version_finder.version()

        self.assertIsInstance(context_manager.exception.original_exception,
                              ProxyError)

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_address_authclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using AuthClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            _ = AuthClient(qe_token, qe_url, proxies=INVALID_ADDRESS_PROXIES)

        self.assertIsInstance(context_manager.exception.original_exception,
                              ProxyError)

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_address_versionclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using VersionClient."""
        # pylint: disable=unused-argument
        with self.assertRaises(RequestsApiError) as context_manager:
            version_finder = VersionClient(qe_url,
                                           proxies=INVALID_ADDRESS_PROXIES)
            version_finder.version()

        self.assertIsInstance(context_manager.exception.original_exception,
                              ProxyError)


def pproxy_desired_access_log_line(url):
    """Return a desired pproxy log entry given a url."""
    qe_url_parts = urllib.parse.urlparse(url)
    protocol_port = '443' if qe_url_parts.scheme == 'https' else '80'
    return 'http {}:{}'.format(qe_url_parts.hostname, protocol_port)
