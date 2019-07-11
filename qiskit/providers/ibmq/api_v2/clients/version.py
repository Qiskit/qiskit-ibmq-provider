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

"""Client for determining the version of an IBM Q Experience service."""

from ..session import RetrySession
from ..rest.version_finder import VersionFinder

from .base import BaseClient


class VersionClient(BaseClient):
    """Client for determining the version of an IBM Q Experience service."""

    def __init__(self, url, **request_kwargs):
        """VersionClient constructor.

        Args:
            url (str): URL for the service.
            **request_kwargs (dict): arguments for the `requests` Session.
        """
        self.client_version_finder = VersionFinder(
            RetrySession(url, **request_kwargs))

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
