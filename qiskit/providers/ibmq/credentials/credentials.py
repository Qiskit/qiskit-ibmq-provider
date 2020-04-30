# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Represent IBM Quantum Experience account credentials."""

import re
import warnings

from typing import Dict, Tuple, Optional, Any
from requests_ntlm import HttpNtlmAuth

from .hubgroupproject import HubGroupProject


REGEX_IBMQ_HUBS = (
    '(?P<prefix>http[s]://.+/api)'
    '/Hubs/(?P<hub>[^/]+)/Groups/(?P<group>[^/]+)/Projects/(?P<project>[^/]+)'
)
"""str: Regex that matches an IBM Quantum Experience URL with hub information."""

TEMPLATE_IBMQ_HUBS = '{prefix}/Network/{hub}/Groups/{group}/Projects/{project}'
"""str: Template for creating an IBM Quantum Experience URL with hub/group/project information."""


class Credentials:
    """IBM Quantum Experience account credentials.

    Note:
        By convention, two credentials that have the same hub, group,
        and project are considered equivalent, regardless of other attributes.
    """

    def __init__(
            self,
            token: str,
            url: str,
            websockets_url: Optional[str] = None,
            hub: Optional[str] = None,
            group: Optional[str] = None,
            project: Optional[str] = None,
            proxies: Optional[Dict] = None,
            verify: bool = True
    ) -> None:
        """Credentials constructor.

        Args:
            token: IBM Quantum Experience API token.
            url: IBM Quantum Experience URL.
            websockets_url: URL for websocket server.
            hub: The hub to use.
            group: The group to use.
            project: The project to use.
            proxies: Proxy configuration.
            verify: If ``False``, ignores SSL certificates errors.
        """
        self.token = token
        (self.url, self.base_url,
         self.hub, self.group, self.project) = _unify_ibmq_url(
             url, hub, group, project)
        self.websockets_url = websockets_url
        self.proxies = proxies or {}
        self.verify = verify

        # Normalize proxy urls.
        self._prepend_protocol_if_needed()

    def is_ibmq(self) -> bool:
        """Return whether the credentials represent an IBM Quantum Experience account."""
        return all([self.hub, self.group, self.project])

    def __eq__(self, other: object) -> bool:
        return self.__dict__ == other.__dict__

    def unique_id(self) -> HubGroupProject:
        """Return a value that uniquely identifies these credentials.

        By convention, two credentials that have the same hub, group,
        and project are considered equivalent.

        Returns:
            A ``HubGroupProject`` instance.
        """
        return HubGroupProject(self.hub, self.group, self.project)

    def connection_parameters(self) -> Dict[str, Any]:
        """Construct connection related parameters.

        Returns:
            A dictionary with connection-related parameters in the format
            expected by ``requests``. The following keys can be present:
            ``proxies``, ``verify``, and ``auth``.
        """
        request_kwargs = {
            'verify': self.verify
        }

        if self.proxies:
            if 'urls' in self.proxies:
                request_kwargs['proxies'] = self.proxies['urls']

            if 'username_ntlm' in self.proxies and 'password_ntlm' in self.proxies:
                request_kwargs['auth'] = HttpNtlmAuth(
                    self.proxies['username_ntlm'],
                    self.proxies['password_ntlm']
                )

        return request_kwargs

    def _prepend_protocol_if_needed(self) -> None:
        """Prepend the proxy URLs with protocol if needed."""
        if 'urls' not in self.proxies:
            return

        warning_issued = False
        for key, url in self.proxies['urls'].items():
            colon_pos = url.find(':')
            if colon_pos < 0 or re.match(r'[0-9]*$', url[colon_pos+1:]):
                # If colon not found OR everything after colon are digits (i.e. port number).
                if not warning_issued:
                    warnings.warn("Proxy URLs without protocols (e.g. 'http://') "
                                  "will no longer be supported in the future release.",
                                  DeprecationWarning, stacklevel=4)
                    warning_issued = True
                prepend_str = 'http:'
                if url[:2] != '//':
                    prepend_str += '//'
                self.proxies['urls'][key] = prepend_str + url


def _unify_ibmq_url(
        url: str,
        hub: Optional[str] = None,
        group: Optional[str] = None,
        project: Optional[str] = None
) -> Tuple[str, str, Optional[str], Optional[str], Optional[str]]:
    """Return a new-style set of credential values (url and hub parameters).

    Args:
        url: URL for IBM Quantum Experience.
        hub: The hub to use.
        group: The group to use.
        project: The project to use.

    Returns:
        A tuple that consists of ``url``, ``base_url``, ``hub``, ``group``,
        and ``project``, where

            * url: The new-style IBM Quantum Experience URL that contains
              the hub, group, and project names.
            * base_url: Base URL that does not contain the hub, group, and
              project names.
            * hub: The hub to use.
            * group: The group to use.
            * project: The project to use.
    """
    # Check if the URL is "new style", and retrieve embedded parameters from it.
    regex_match = re.match(REGEX_IBMQ_HUBS, url, re.IGNORECASE)
    base_url = url
    if regex_match:
        base_url, hub, group, project = regex_match.groups()
    else:
        if hub and group and project:
            # Assume it is an IBMQ URL, and update the url.
            url = TEMPLATE_IBMQ_HUBS.format(prefix=url, hub=hub, group=group,
                                            project=project)
        else:
            # Cleanup the hub, group and project, without modifying the url.
            hub = group = project = None

    return url, base_url, hub, group, project
