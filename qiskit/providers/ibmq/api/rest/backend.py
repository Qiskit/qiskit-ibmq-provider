# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Backend REST adapter for the IBM Q Experience API."""

import json
from typing import Dict, Optional, Any
from datetime import datetime  # pylint: disable=unused-import
from .base import RestAdapterBase
from ..session import RetrySession


class Backend(RestAdapterBase):
    """Rest adapter for backend related endpoints."""

    URL_MAP = {
        'properties': '/properties',
        'pulse_defaults': '/defaults',
        'status': '/queue/status',
        'jobs_limit': '/jobsLimit'
    }

    def __init__(self, session: RetrySession, backend_name: str) -> None:
        """Backend constructor.

        Args:
            session: session to be used in the adaptor.
            backend_name: name of the backend.
        """
        self.backend_name = backend_name
        super().__init__(session, '/devices/{}'.format(backend_name))

    def properties(self, datetime: Optional[datetime] = None) -> Dict[str, Any]:
        """Return backend properties.

        Args:
            datetime: datetime used for additional filtering passed to the query.

        Returns:
            json response of backend properties.
        """
        # pylint: disable=redefined-outer-name
        url = self.get_url('properties')

        params = {
            'version': 1
        }

        query = {}
        if datetime:
            extra_filter = {'last_update_date': {'lt': datetime.isoformat()}}
            query['where'] = extra_filter
            params['filter'] = json.dumps(query)  # type: ignore[assignment]

        response = self.session.get(url, params=params).json()

        # Adjust name of the backend.
        if response:
            response['backend_name'] = self.backend_name

        return response

    def pulse_defaults(self) -> Dict[str, Any]:
        """Return backend pulse defaults."""
        url = self.get_url('pulse_defaults')
        return self.session.get(url).json()

    def status(self) -> Dict[str, Any]:
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

    def job_limit(self) -> Dict[str, Any]:
        """Return backend job limit."""
        url = self.get_url('jobs_limit')
        return self.session.get(url).json()
