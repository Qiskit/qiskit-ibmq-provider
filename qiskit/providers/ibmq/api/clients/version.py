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

"""Client for determining the version of an IBM Quantum Experience service."""

from typing import Dict, Union, Any

from ..session import RetrySession
from ..rest.version_finder import VersionFinder

from .base import BaseClient


class VersionClient(BaseClient):
    """Client for determining the version of an IBM Quantum Experience service."""

    def __init__(self, url: str, **request_kwargs: Any) -> None:
        """VersionClient constructor.

        Args:
            url: URL of the service.
            **request_kwargs: Arguments for the request ``Session``.
        """
        self.client_version_finder = VersionFinder(
            RetrySession(url, **request_kwargs))

    def version(self) -> Dict[str, Union[bool, str]]:
        """Return the version information.

        Returns:
            A dictionary with information about the API version,
            with the following keys:

                * ``new_api`` (bool): Whether the new API is being used

            And the following optional keys:

                * ``api-*`` (str): The versions of each individual API component
        """
        return self.client_version_finder.version()
