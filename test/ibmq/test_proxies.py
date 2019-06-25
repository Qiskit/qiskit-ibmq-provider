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

"""Tests for the IBMQClient and IBMQVersionFinder proxy support."""


import urllib
import subprocess

from requests.exceptions import ProxyError

from qiskit.providers.ibmq.api_v2 import IBMQClient, IBMQVersionFinder
from qiskit.providers.ibmq.api_v2.exceptions import RequestsApiError
from qiskit.test import QiskitTestCase, requires_qe_access

from ..decorators import requires_new_api_auth

ADDRESS = '127.0.0.1'
PORT = 8080
VALID_PROXIES = {'https': 'http://{}:{}'.format(ADDRESS, PORT)}
INVALID_PORT_PROXIES = {'https': '{}:{}'.format(ADDRESS, '6666')}
INVALID_ADDRESS_PROXIES = {'https': '{}:{}'.format('invalid', PORT)}


class TestProxies(QiskitTestCase):
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
    @requires_new_api_auth
    def test_proxies_ibmqclient(self, qe_token, qe_url):
        """Should reach the proxy using IBMQClient."""
        pproxy_desired_access_log_line_ = pproxy_desired_access_log_line(qe_url)

        _ = IBMQClient(qe_token, qe_url, proxies=VALID_PROXIES)

        self.proxy_process.terminate()  # kill to be able of reading the output
        self.assertIn(pproxy_desired_access_log_line_,
                      self.proxy_process.stdout.read().decode('utf-8'))

    # pylint: disable=unused-argument
    @requires_qe_access
    @requires_new_api_auth
    def test_proxies_ibmqversionfinder(self, qe_token, qe_url):
        """Should reach the proxy using IBMQVersionFinder."""
        pproxy_desired_access_log_line_ = pproxy_desired_access_log_line(qe_url)

        version_finder = IBMQVersionFinder(qe_url, proxies=VALID_PROXIES)
        version_finder.version()  # call the version finder, sending logging to the proxy process

        self.proxy_process.terminate()  # kill to be able of reading the output
        self.assertIn(pproxy_desired_access_log_line_,
                      self.proxy_process.stdout.read().decode('utf-8'))

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_port_ibmqclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError as original exception using IBMQClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            _ = IBMQClient(qe_token, qe_url, proxies=INVALID_PORT_PROXIES)

        self.assertIsInstance(context_manager.exception.original_exception, ProxyError)

    # pylint: disable=unused-argument
    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_port_ibmqversionfinder(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError as
            original exception using IBMQVersionFinder."""
        with self.assertRaises(RequestsApiError) as context_manager:
            version_finder = IBMQVersionFinder(qe_url, proxies=INVALID_PORT_PROXIES)
            version_finder.version()

        self.assertIsInstance(context_manager.exception.original_exception, ProxyError)

    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_address_ibmqclient(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError as
            original exception using IBMQClient."""
        with self.assertRaises(RequestsApiError) as context_manager:
            _ = IBMQClient(qe_token, qe_url, proxies=INVALID_ADDRESS_PROXIES)

        self.assertIsInstance(context_manager.exception.original_exception, ProxyError)

    # pylint: disable=unused-argument
    @requires_qe_access
    @requires_new_api_auth
    def test_invalid_proxy_address_ibmqversionfinder(self, qe_token, qe_url):
        """Should raise RequestApiError with ProxyError as
            original exception using IBMQVersionFinder."""
        with self.assertRaises(RequestsApiError) as context_manager:
            version_finder = IBMQVersionFinder(qe_url, proxies=INVALID_ADDRESS_PROXIES)
            version_finder.version()

        self.assertIsInstance(context_manager.exception.original_exception, ProxyError)


def pproxy_desired_access_log_line(url):
    """Return a desired pproxy log entry given a url."""
    qe_url_parts = urllib.parse.urlparse(url)
    protocol_port = '443' if qe_url_parts.scheme == 'https' else '80'
    return 'http {}:{}'.format(qe_url_parts.hostname, protocol_port)
