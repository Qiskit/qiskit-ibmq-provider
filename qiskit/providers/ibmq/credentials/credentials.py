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

"""Model for representing IBM Q credentials."""

import re

# Regex that matches a IBMQ URL with hub information
REGEX_IBMQ_HUBS = (
    '(?P<prefix>http[s]://.+/api)'
    '/Hubs/(?P<hub>[^/]+)/Groups/(?P<group>[^/]+)/Projects/(?P<project>[^/]+)'
)
# Template for creating an IBMQ URL with hub information
TEMPLATE_IBMQ_HUBS = '{prefix}/Hubs/{hub}/Groups/{group}/Projects/{project}'


class Credentials:
    """IBM Q account credentials.

    Note that, by convention, two credentials that have the same hub, group
    and project (regardless of other attributes) are considered equivalent.
    The `unique_id()` returns the unique identifier.
    """

    def __init__(self, token, url, hub=None, group=None, project=None,
                 websocket_url=None, proxies=None, verify=True):
        """Return new set of credentials.

        Args:
            token (str): Quantum Experience or IBMQ API token.
            url (str): URL for Quantum Experience or IBMQ.
            hub (str): the hub used for IBMQ.
            group (str): the group used for IBMQ.
            project (str): the project used for IBMQ.
            websocket_url (str): URL for websocket communication with IBM Q.
            proxies (dict): proxy configuration for the API.
            verify (bool): if False, ignores SSL certificates errors

        Note:
            `hub`, `group` and `project` are stored as attributes for
            convenience, but their usage in the API is deprecated. The new-style
            URLs (that includes these parameters as part of the url string, and
            is automatically set during instantiation) should be used when
            communicating with the API.
        """
        self.token = token
        (self.url, self.websocket_url,
         self.hub, self.group, self.project) = _unify_ibmq_url(
             url, websocket_url, hub, group, project)
        self.proxies = proxies or {}
        self.verify = verify

    def is_ibmq(self):
        """Return whether the credentials represent a IBMQ account."""
        return all([self.hub, self.group, self.project])

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def unique_id(self):
        """Return a value that uniquely identifies these credentials.

        By convention, we assume (hub, group, project) is always unique.
        """
        return self.hub, self.group, self.project


def _unify_ibmq_url(url, websocket_url=None, hub=None, group=None, project=None):
    """Return a new-style set of credential values (url and hub parameters).

    Args:
        url (str): URL for Quantum Experience or IBM Q.
        websocket_url (str): URL for websocket communication with IBM Q.
        hub (str): the hub used for IBM Q.
        group (str): the group used for IBM Q.
        project (str): the project used for IBM Q.

    Returns:
        tuple[url, websocket_url, hub, group, token]:
            * url (str): new-style Quantum Experience or IBM Q URL (the hub,
                group and project included in the URL.
            * hub (str): the hub used for IBM Q.
            * group (str): the group used for IBM Q.
            * project (str): the project used for IBM Q.
    """
    # Check if the URL is "new style", and retrieve embedded parameters from it.
    regex_match = re.match(REGEX_IBMQ_HUBS, url, re.IGNORECASE)
    if regex_match:
        _, hub, group, project = regex_match.groups()
    else:
        if hub and group and project:
            # Assume it is an IBMQ URL, and update the url.
            url = TEMPLATE_IBMQ_HUBS.format(prefix=url, hub=hub, group=group,
                                            project=project)
        else:
            # Cleanup the hub, group and project, without modifying the url.
            hub = group = project = None

    return url, websocket_url, hub, group, project
