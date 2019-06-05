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

"""Client for accessing IBM Q's version finder."""

from .session import RetrySession
from .rest import Auth
from .rest.version_finder import VersionFinder


class IBMQVersionFinder:
    """Client for programmatic access to the IBM Q API."""

    def __init__(self, auth_url):
        """IBMQVersionFinder constructor.

        Args:
            auth_url (str): URL for the authentication service.
        """
        self.auth_url = auth_url
        self.client_auth = Auth(RetrySession(auth_url))
        self.client_version_finder = VersionFinder(RetrySession(auth_url))

    def version_info(self):
        """Return the version info of the API.

        Returns:
            dict: a dict of the API versions with a key conveying whether
                the new API is being used.
        """
        return self.client_version_finder.version_info()
