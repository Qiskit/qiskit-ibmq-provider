# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""REST clients for accessing IBM Q."""


class RestAdapterBase:
    """Base class for REST adaptors."""

    URL_MAP = {}
    """Mapping between the internal name of an endpoint and the actual URL"""

    def __init__(self, session, prefix_url=''):
        """RestAdapterBase constructor.

        Args:
            session (Session): session to be used in the adaptor.
            prefix_url (str): string to be prefixed to all urls.
        """
        self.session = session
        self.prefix_url = prefix_url

    def get_url(self, identifier):
        """Return the resolved URL for the specified identifier.

        Args:
            identifier (str): internal identifier of the endpoint.

        Returns:
            str: the resolved URL of the endpoint (relative to the session
                base url).
        """
        return '{}{}'.format(self.prefix_url, self.URL_MAP[identifier])
