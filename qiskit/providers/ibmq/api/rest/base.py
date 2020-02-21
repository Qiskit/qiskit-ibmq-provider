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

"""Base REST adapter."""

from ..session import RetrySession


class RestAdapterBase:
    """Base class for REST adapters."""

    URL_MAP = {}  # type: ignore[var-annotated]
    """Mapping between the internal name of an endpoint and the actual URL."""

    def __init__(self, session: RetrySession, prefix_url: str = '') -> None:
        """RestAdapterBase constructor.

        Args:
            session: Session to be used in the adapter.
            prefix_url: String to be prepend to all URLs.
        """
        self.session = session
        self.prefix_url = prefix_url

    def get_url(self, identifier: str) -> str:
        """Return the resolved URL for the specified identifier.

        Args:
            identifier: Internal identifier of the endpoint.

        Returns:
            The resolved URL of the endpoint (relative to the session base URL).
        """
        return '{}{}'.format(self.prefix_url, self.URL_MAP[identifier])
