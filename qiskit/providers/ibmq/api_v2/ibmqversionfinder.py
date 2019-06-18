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
from .rest.version_finder import VersionFinder


class IBMQVersionFinder:
    """Client for finding the API version being used."""

    def __init__(self, url, verify=True, proxies=None, ntlm_credentials=None):
        """IBMQVersionFinder constructor.

        Args:
            url (str): URL for the service.
            verify (bool): if False, ignores SSL certificates errors.
            proxies (dict): proxies used in the connection.
            ntlm_credentials (dict): NTLM proxy credentials.
        """
        self.client_version_finder = VersionFinder(
            RetrySession(url, verify=verify, proxies=proxies, ntlm_credentials=ntlm_credentials)
        )

    def version(self):
        """Return the version info.

        Returns:
            dict: a dict with information about the API version,
            with the following keys:
                * `new_api` (bool): whether the new API is being used
            And the following optional keys:
                * `api-*` (str): the versions of each individual API component
        """
        return self.client_version_finder.version()
