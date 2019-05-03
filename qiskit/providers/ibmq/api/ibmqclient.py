# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Client for accessing IBM Q."""

from .session import RetrySession
from .rest import Api, Auth


class IBMQClient:
    """Client for programmatic access to the IBM Q API."""

    def __init__(self, api_token, auth_url):
        self.api_token = api_token
        self.auth_url = auth_url

        self.login_session = RetrySession(auth_url)
        self.auth_client = Auth(self.login_session)

        # Get the access token and use it in the sessions.
        access_token = self._request_access_token()
        self.login_session.access_token = access_token
        api_url = self._user_urls()['http']

        self.api_session = RetrySession(api_url, access_token)
        self.api_client = Api(self.api_session)

    def _request_access_token(self):
        """Request a new access token from the API."""
        response = self.auth_client.login(self.api_token)
        return response['id']

    def _user_urls(self):
        response = self.auth_client.user_info()
        return response['urls']

    # Entry points.


    # Backends.

    def list_backends(self):
        return self.api_client.backends()

    def backend_status(self, backend_name):
        return self.api_client.backend(backend_name).status()

    def backend_properties(self, backend_name):
        return self.api_client.backend(backend_name).properties()

    def backend_pulse_defaults(self, backend_name):
        # return self.api_client.backend(backend_name).pulse_defaults()
        raise NotImplementedError

    # Jobs.

    def list_jobs_statuses(self, limit=10, skip=0, extra_filter=None):
        return self.api_client.jobs(limit=limit, skip=skip,
                                    extra_filter=extra_filter)

    def job_run(self, backend_name, qobj_dict):
        return self.api_client.run_job(backend_name, qobj_dict)

    def job_get(self, job_id, excluded_fields=None, included_fields=None):
        return self.api_client.job(job_id).get(excluded_fields,
                                               included_fields)

    def job_status(self, job_id):
        return self.api_client.job(job_id).status()

    def job_properties(self, job_id):
        # return self.api_client.job(job_id).properties()
        raise NotImplementedError

    def job_cancel(self, job_id):
        return self.api_client.job(job_id).cancel()

    # Endpoints for compatibility with classic IBMQConnector.

    def get_status_job(self, id_job):
        return self.job_status(id_job)

    def run_job(self, qobj, backend_name):
        return self.job_run(backend_name, qobj)

    def get_jobs(self, limit=10, skip=0, backend=None, only_completed=False,
                 filter=None):
        # TODO: this function seems to be unused currently in IBMQConnector.
        raise NotImplementedError

    def get_status_jobs(self, limit=10, skip=0, backend=None, filter=None):
        if backend:
            filter = filter or {}
            filter.update({'backend.name': backend})

        return self.list_jobs_statuses(limit, skip, filter)

    def cancel_job(self, id_job):
        return self.job_cancel(id_job)

    def backend_defaults(self, backend):
        return self.backend_pulse_defaults(backend)

    def available_backends(self):
        return self.list_backends()

    def get_job(self, id_job, exclude_fields=None, include_fields=None):
        return self.job_get(id_job, exclude_fields, include_fields)

    def api_version(self):
        pass
