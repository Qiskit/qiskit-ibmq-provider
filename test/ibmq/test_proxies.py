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
from qiskit.providers.ibmq.api.clients import (AuthClient,
                                               VersionClient)
from qiskit.providers.ibmq.api.exceptions import RequestsApiError
from qiskit.providers.ibmq.credentials import Credentials
from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_qe_access

# Fallback mechanism. Version variable is stored under __doc__ in new pproxy versions
try:
    from pproxy.__doc__ import __version__ as pproxy_version
except ImportError:
    from pproxy import __version__ as pproxy_version

ADDRESS = '127.0.0.1'
PORT = 8085
VALID_PROXIES = {'https': 'http://{}:{}'.format(ADDRESS, PORT)}
INVALID_PORT_PROXIES = {'https': 'http://{}:{}'.format(ADDRESS, '6666')}
INVALID_ADDRESS_PROXIES = {'https': 'http://{}:{}'.format('invalid', PORT)}


@skipIf((sys.version_info > (3, 5) and pproxy_version == '1.2.2') or
        (sys.version_info == (3, 5) and pproxy_version > '1.2.2'),
        'pproxy version is not supported')
class TestProxies(IBMQTestCase):
    """Tests for proxy capabilities."""

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        listen_flag = '-l' if pproxy_version >= '1.7.2' else '-i'
        # launch a mock server.
        command = ['pproxy', '-v', listen_flag, 'http://{}:{}'.format(ADDRESS, PORT)]
        self.proxy_process = subprocess.Popen(command, stdout=subprocess.PIPE)

    def tearDown(self):
        """Test cleanup."""
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
    def test_proxies_authclient(self, qe_token, qe_url):
        """Should reach the proxy using AuthClient."""
        pproxy_desired_access_log_line_ = pproxy_desired_access_log_line(qe_url)

        _ = AuthClient(qe_token, qe_url, proxies=VALID_PROXIES)

        self.proxy_process.terminate()  # kill to be able of reading the output
        self.assertIn(pproxy_desired_access_log_line_,
                      self.proxy_process.stdout.read().decode('utf-8'))

    # pylint: disable=unused-argument
    @requires_qe_access
    def test_proxies_versionclient(self, qe_token, qe_url):
        """Should reach the proxy using IBMQVersionFinder."""
        pproxy_desired_access_log_line_ = pproxy_desired_access_log_line(qe_url)

        version_finder = VersionClient(qe_url, proxies=VALID_PROXIES)
        version_finder.version()

        self.proxy_process.terminate()  # kill to be able of reading the output
        self.assertIn(pproxy_desired_access_log_line_,
                      self.proxy_process.stdout.read().decode('utf-8'))

    @requires_qe_access
    def test_invalid_proxy_port_authclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using AuthClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            _ = AuthClient(qe_token, qe_url, proxies=INVALID_PORT_PROXIES)

        self.assertIsInstance(context_manager.exception.__cause__, ProxyError)

    # pylint: disable=unused-argument
    @requires_qe_access
    def test_invalid_proxy_port_versionclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using VersionClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            version_finder = VersionClient(qe_url, proxies=INVALID_PORT_PROXIES)
            version_finder.version()

        self.assertIsInstance(context_manager.exception.__cause__, ProxyError)

    @requires_qe_access
    def test_invalid_proxy_address_authclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using AuthClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            _ = AuthClient(qe_token, qe_url, proxies=INVALID_ADDRESS_PROXIES)

        self.assertIsInstance(context_manager.exception.__cause__, ProxyError)

    @requires_qe_access
    def test_invalid_proxy_address_versionclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError using VersionClient."""
        # pylint: disable=unused-argument
        with self.assertRaises(RequestsApiError) as context_manager:
            version_finder = VersionClient(qe_url,
                                           proxies=INVALID_ADDRESS_PROXIES)
            version_finder.version()

        self.assertIsInstance(context_manager.exception.__cause__, ProxyError)

    @requires_qe_access
    def test_proxy_urls(self, qe_token, qe_url):
        """Test different forms of the proxy urls."""
        test_urls = [
            '{}:{}'.format(ADDRESS, PORT),
            'http://{}:{}'.format(ADDRESS, PORT),
            '//{}:{}'.format(ADDRESS, PORT),
            'http:{}:{}'.format(ADDRESS, PORT),
            'http://user:123@{}:{}'.format(ADDRESS, PORT)
        ]
        for proxy_url in test_urls:
            with self.subTest(proxy_url=proxy_url):
                credentials = Credentials(
                    qe_token, qe_url, proxies={'urls': {'https': proxy_url}})
                version_finder = VersionClient(credentials.base_url,
                                               **credentials.connection_parameters())
                version_finder.version()


def pproxy_desired_access_log_line(url):
    """Return a desired pproxy log entry given a url."""
    qe_url_parts = urllib.parse.urlparse(url)
    protocol_port = '443' if qe_url_parts.scheme == 'https' else '80'
    return '{}:{}'.format(qe_url_parts.hostname, protocol_port)
