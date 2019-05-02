# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Client for accessing IBM Q."""

from .session import RetrySession
from .rest import AuthClient, ApiClient


class IBMQClient:
    """Client for programmatic access to the IBM Q API."""

    def __init__(self, api_token, auth_url):
        self.api_token = api_token
        self.auth_url = auth_url

        self.login_session = RetrySession(auth_url)
        self.auth_client = AuthClient(self.login_session)

        # Get the access token and use it in the sessions.
        access_token = self._request_access_token()
        self.login_session.access_token = access_token
        api_url = self._user_urls()['http']

        self.api_session = RetrySession(api_url, access_token)
        self.api_client = ApiClient(self.api_session)

    def _request_access_token(self):
        """Request a new access token from the API."""
        response = self.auth_client.login(self.api_token)
        return response['id']

    def _user_urls(self):
        response = self.auth_client.user_info()
        return response['urls']

    # Entry points.

    def available_backends(self):
        return self.api_client.backends()

    # Backends.

    def backend_status(self, backend_name):
        return self.api_client.backend(backend_name).status()

    def backend_properties(self, backend_name):
        return self.api_client.backend(backend_name).properties()

    def backend_pulse_defaults(self, backend_name):
        # return self.api_client.backend(backend_name).pulse_defaults()
        raise NotImplementedError

    # Jobs.

    def run_job(self, backend_name, qobj_dict):
        payload = {'qObject': qobj_dict,
                   'backend': {'name': backend_name}}
        response = self.api_client.run_job(payload)

        return response

    def list_jobs(self, limit=10, skip=0, extra_filter=None):
        return self.api_client.jobs(limit=limit, skip=skip,
                                    extra_filter=extra_filter)

    def get_job(self, job_id, excluded_fields=None, included_fields=None):
        return self.api_client.job(job_id).get(excluded_fields,
                                               included_fields)

    def job_status(self, job_id):
        return self.api_client.job(job_id).status()

    def job_properties(self, job_id):
        # return self.api_client.job(job_id).properties()
        raise NotImplementedError

    def job_cancel(self, job_id):
        return self.api_client.job(job_id).cancel()
