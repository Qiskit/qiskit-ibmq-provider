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

"""Job REST adapter for the IBM Q Api version 2."""

import json

from .base import RestAdapterBase


class Job(RestAdapterBase):
    """Rest adapter for job related endpoints."""

    URL_MAP = {
        'cancel': 'cancel',
        'self': '',
        'status': '/status',
        'properties': '/properties'
    }

    def __init__(self, session, job_id):
        """Job constructor.

        Args:
            session (Session): session to be used in the adaptor.
            job_id (str): id of the job.
        """
        self.job_id = job_id
        super().__init__(session, '/Jobs/{}'.format(job_id))

    def get(self, excluded_fields, included_fields):
        """Return a job.

        Args:
            excluded_fields (list[str]): names of the fields to explicitly
                exclude from the result.
            included_fields (list[str]): names of the fields to explicitly
                include in the result.

        Returns:
            dict: json response.
        """
        url = self.get_url('self')
        query = build_url_filter(excluded_fields, included_fields)

        response = self.session.get(
            url, params={'filter': json.dumps(query) if query else None}).json()

        if 'calibration' in response:
            response['properties'] = response.pop('calibration')

        return response

    def cancel(self):
        """Cancel a job."""
        url = self.get_url('cancel')
        return self.session.post(url).json()

    def properties(self):
        """Return the backend properties of a job."""
        url = self.get_url('properties')
        return self.session.get(url).json()

    def status(self):
        """Return the status of a job."""
        url = self.get_url('status')
        return self.session.get(url).json()


def build_url_filter(excluded_fields, included_fields):
    """Return a URL filter based on included and excluded fields.

    Args:
        excluded_fields (list[str]): names of the fields to explicitly
            exclude from the result.
        included_fields (list[str]): names of the fields to explicitly
            include in the result.

    Returns:
        dict: the query, as a dict in the format for the API.
    """
    excluded_fields = excluded_fields or []
    included_fields = included_fields or []
    fields_bool = {}
    ret = {}

    # Build a map of fields to bool.
    for field_ in excluded_fields:
        fields_bool[field_] = False
    for field_ in included_fields:
        fields_bool[field_] = True

    if 'properties' in fields_bool:
        fields_bool['calibration'] = fields_bool.pop('properties')

    if fields_bool:
        ret = {'fields': fields_bool}

    return ret
