# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Root REST adaptor for the IBM Q Api version 2."""

import json

from .base import RestAdaptorBase
from .backend import Backend
from .job import Job


class Api(RestAdaptorBase):

    URL_MAP = {
        'backends': '/Backends/v/1',
        'hubs': '/Network',
        'jobs': '/Jobs',
        'jobs_status': '/Jobs/status'
    }

    def backend(self, backend_name):
        return Backend(self.session, backend_name)

    def job(self, job_id):
        return Job(self.session, job_id)

    def backends(self):
        url = self.get_url('backends')
        return self.session.get(url).json()

    def hubs(self):
        url = self.get_url('hubs')
        return self.session.get(url).json()

    def jobs(self, limit=10, skip=0, extra_filter=None):
        url = self.get_url('jobs_status')

        query = {
            'order': 'creationDate DESC',
            'limit': limit,
            'skip': skip,
        }
        if extra_filter:
            query['where'] = extra_filter

        return self.session.get(
            url, params={'filter': json.dumps(query) if query else None}).json()

    def run_job(self, backend_name, qobj_dict):
        url = self.get_url('jobs')

        payload = {'qObject': qobj_dict,
                   'backend': {'name': backend_name},
                   'shots': qobj_dict.get('config', {}).get('shots', 1)}

        return self.session.post(url, json=payload).json()
