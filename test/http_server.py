# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""HTTP server for testing purposes."""

import threading
import json
from typing import Dict
from http.server import BaseHTTPRequestHandler, HTTPServer


class BaseHandler(BaseHTTPRequestHandler):
    """Base request handler for testing."""

    good_response = {}
    error_response = {}

    def _get_code(self):
        """Get the status code to be returned."""
        return 200

    def _get_response_data(self):
        """Get the response data to be returned."""
        return self.good_response

    def _get_error_data(self):
        """Get the error data to be returned."""
        return self.error_response

    def _respond(self):
        """Respond to the client."""
        code = self._get_code()
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        data = self._get_response_data() if code == 200 else self._get_error_data()
        self.wfile.write(json.dumps(data).encode(encoding='utf_8'))

    def do_GET(self):
        """Process a GET request."""
        # pylint: disable=invalid-name
        self._respond()

    def do_POST(self):
        """Process a POST request."""
        # pylint: disable=invalid-name
        self._respond()

    def do_PUT(self):
        """Process a PUT request."""
        # pylint: disable=invalid-name
        self._respond()


class ServerErrorOnceHandler(BaseHandler):
    """Request handler that returns a server error once then a good response."""

    bad_status_given = {}

    def _get_code(self):
        """Return 200 if the path was seen before, otherwise 504."""
        if self.bad_status_given.get(self.path):
            return 200
        self.bad_status_given[self.path] = True
        return 504


class ClientErrorHandler(BaseHandler):
    """Request handler that returns a client error."""

    def _get_code(self):
        """Return 400."""
        return 400


class SimpleServer:
    """A simple test HTTP server."""

    IP_ADDRESS = '127.0.0.1'
    PORT = 8123
    URL = "http://{}:{}".format(IP_ADDRESS, PORT)

    def __init__(self, handler_class: BaseHandler):
        """SimpleServer constructor.

        Args:
            handler_class: Request handler class.
        """
        self.httpd = HTTPServer((self.IP_ADDRESS, self.PORT), handler_class)
        self.server = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        """Start the server."""
        self.server.start()

    def stop(self):
        """Stop the server."""
        self.httpd.shutdown()
        self.server.join(3)
        self.httpd.server_close()

    def set_error_response(self, error_response: Dict):
        """Set the error response."""
        setattr(self.httpd.RequestHandlerClass, 'error_response', error_response)

    def set_good_response(self, response: Dict):
        """Set good response."""
        setattr(self.httpd.RequestHandlerClass, 'good_response', response)
