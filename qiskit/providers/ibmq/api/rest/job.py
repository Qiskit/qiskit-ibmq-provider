# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Job REST adaptor for the IBM Q Api version 2."""

import json

from qiskit.providers.ibmq.api.rest.base import RestAdaptorBase
from .util import build_url_filter


class Job(RestAdaptorBase):

    URL_MAP = {
        'cancel': 'cancel',
        'self': '',
        'status': '/status'
    }

    def __init__(self, session, job_id):
        self.job_id = job_id
        super().__init__(session, '/Jobs/{}'.format(job_id))

    def get(self, excluded_fields, included_fields):
        url = self.get_url('self')
        query = build_url_filter(excluded_fields, included_fields)

        return self.session.get(
            url, params={'filter': json.dumps(query) if query else None}).json()

    def cancel(self):
        url = self.get_url('cancel')
        return self.session.post(url).json()

    def status(self):
        url = self.get_url('status')
        return self.session.get(url).json()

