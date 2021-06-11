# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Local proxy server for testing."""

import subprocess
from contextlib import contextmanager


class MockProxyServer:
    """Local proxy server for testing."""

    PROXY_IP_ADDRESS = '127.0.0.1'
    PROXY_PORT = 8085
    INVALID_PROXY_PORT = 6666
    VALID_PROXIES = {'https': 'http://{}:{}'.format(PROXY_IP_ADDRESS, PROXY_PORT)}

    def __init__(self, test_case, logger):
        self._test_case = test_case
        self._logger = logger
        self.proxy_process = None

    def start(self):
        """Start the server."""
        self._logger.debug("Starting proxy server at port %s", self.PROXY_PORT)
        command = ['pproxy', '-v', '-l', 'http://{}:{}'.format(
            self.PROXY_IP_ADDRESS, self.PROXY_PORT)]
        self.proxy_process = subprocess.Popen(command, stdout=subprocess.PIPE)
        self._test_case.addCleanup(self.stop)

    def stop(self):
        """Stop the server."""
        if self.proxy_process is not None and self.proxy_process.returncode is None:
            self._logger.debug("Shutting down proxy server.")
            self.proxy_process.stdout.close()  # close the IO buffer
            self.proxy_process.terminate()  # initiate process termination
            self.proxy_process.wait()  # wait for the process to terminate
            self.proxy_process = None


@contextmanager
def use_proxies(provider, proxies):
    """Context manager to set and restore proxies setting."""
    try:
        provider.credentials.proxies = {'urls': proxies}
        yield
    finally:
        provider.credentials.proxies = None
