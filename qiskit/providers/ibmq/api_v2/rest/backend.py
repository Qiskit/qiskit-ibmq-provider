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

"""Backend REST adapter for the IBM Q Api version 2."""

from .base import RestAdapterBase


class Backend(RestAdapterBase):
    """Rest adapter for backend related endpoints."""

    URL_MAP = {
        'status': '/queue/status',
        'properties': '/properties'
    }

    def __init__(self, session, backend_name):
        """Backend constructor.

        Args:
            session (Session): session to be used in the adaptor.
            backend_name (str): name of the backend.
        """
        self.backend_name = backend_name
        super().__init__(session, '/Backends/{}'.format(backend_name))

    def status(self):
        """Return backend status."""
        url = self.get_url('status')
        response = self.session.get(url).json()

        # Adjust fields according to the specs (BackendStatus).
        ret = {
            'backend_name': self.backend_name,
            'backend_version': response.get('backend_version', '0.0.0'),
            'status_msg': response.get('status', ''),
            'operational': bool(response.get('state', False))
        }

        # 'pending_jobs' is required, and should be >= 0.
        if 'lengthQueue' in response:
            ret['pending_jobs'] = max(response['lengthQueue'], 0)
        else:
            ret['pending_jobs'] = 0

        # Not part of the schema.
        if 'busy' in response:
            ret['dedicated'] = response['busy']

        return ret

    def properties(self):
        """Return backend properties."""
        url = self.get_url('properties')
        response = self.session.get(url, params={'version': 1}).json()

        # Adjust name of the backend.
        if response:
            response['backend_name'] = self.backend_name

        return response
