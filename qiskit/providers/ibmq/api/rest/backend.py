# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Backend REST adaptor for the IBM Q Api version 2."""

from qiskit.providers.ibmq.api.rest.base import RestAdaptorBase


class Backend(RestAdaptorBase):

    URL_MAP = {
        'status': '/queue/status',
        'properties': '/properties'
    }

    def __init__(self, session, backend_name):
        self.backend_name = backend_name
        super().__init__(session, '/Backends/{}'.format(backend_name))

    def status(self):
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
        url = self.get_url('properties')
        response = self.session.get(url, params={'version': 1}).json()

        # Adjust name of the backend.
        if response:
            response['backend_name'] = self.backend_name

        return response
