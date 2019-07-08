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

"""Job REST adapter for the IBM Q Experience v2 API."""

import json

from .base import RestAdapterBase


class Job(RestAdapterBase):
    """Rest adapter for job related endpoints."""

    URL_MAP = {
        'callback_upload': '/jobDataUploaded',
        'cancel': '/cancel',
        'download_url': '/jobDownloadUrl',
        'self': '',
        'status': '/status',
        'properties': '/properties',
        'result_url': '/resultDownloadUrl',
        'upload_url': '/jobUploadUrl'
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

    def callback_upload(self):
        """Notify the API after uploading a Qobj via object storage."""
        url = self.get_url('callback_upload')
        return self.session.post(url).json()

    def cancel(self):
        """Cancel a job."""
        url = self.get_url('cancel')
        return self.session.post(url).json()

    def download_url(self):
        """Return an object storage URL for downloading the Qobj."""
        url = self.get_url('download_url')
        return self.session.get(url).json()

    def properties(self):
        """Return the backend properties of a job."""
        url = self.get_url('properties')
        return self.session.get(url).json()

    def result_url(self):
        """Return an object storage URL for downloading results."""
        url = self.get_url('result_url')
        return self.session.get(url).json()

    def status(self):
        """Return the status of a job."""
        url = self.get_url('status')
        return self.session.get(url).json()

    def upload_url(self):
        """Return an object storage URL for uploading the Qobj."""
        url = self.get_url('upload_url')
        return self.session.get(url).json()

    def put_object_storage(self, url, qobj_dict):
        """Upload a Qobj via object storage.

        Args:
            url (str): object storage URL.
            qobj_dict (dict): the qobj to be uploaded, in dict form.

        Returns:
            str: text response, that will be empty if the request was
                successful.
        """
        response = self.session.put(url, json=qobj_dict, bare=True)
        return response.text

    def get_object_storage(self, url):
        """Get via object_storage.

        Args:
            url (str): object storage URL.

        Returns:
            dict: json response.
        """
        return self.session.get(url, bare=True).json()


def build_url_filter(excluded_fields, included_fields):
    """Return a URL filter based on included and excluded fields.

    If a field appears in both excluded_fields and included_fields, it
    is ultimately included.

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
    field_flags = {}
    ret = {}

    # Build a map of fields to bool.
    for field_ in excluded_fields:
        field_flags[field_] = False
    for field_ in included_fields:
        # Set the included fields. If a field_ here was also in
        # excluded_fields, it is overwritten here.
        field_flags[field_] = True

    if 'properties' in field_flags:
        field_flags['calibration'] = field_flags.pop('properties')

    if field_flags:
        ret = {'fields': field_flags}

    return ret
