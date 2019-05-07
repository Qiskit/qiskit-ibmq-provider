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

"""Client for accessing IBM Q."""

from .session import RetrySession
from .rest import Api, Auth


class IBMQClient:
    """Client for programmatic access to the IBM Q API."""

    def __init__(self, api_token, auth_url):
        """IBMQClient constructor.

        Args:
            api_token (str): IBM Q api token.
            auth_url (str): URL for the authentication service.
        """
        self.api_token = api_token
        self.auth_url = auth_url

        self.auth_client = Auth(RetrySession(auth_url))
        self.api_client = self._init_api_client()

    def _init_api_client(self):
        """Initialize the client used for communicating with the API.

        Returns:
            Api: client for the api server.
        """
        # Request an access token.
        access_token = self._request_access_token()
        # Use the token for the next auth server requests.
        self.auth_client.session.access_token = access_token
        api_url = self._user_urls()['http']

        # Create the api server client, using the access token.
        api_session = Api(RetrySession(api_url, access_token))
        return api_session

    def _request_access_token(self):
        """Request a new access token from the API.

        Returns:
            str: access token.
        """
        response = self.auth_client.login(self.api_token)
        return response['id']

    def _user_urls(self):
        """Retrieve the api URLs from the auth server.

        Returns:
            dict: a dict with the base URLs for the services. Currently
                supported keys:
                * ``http``: the api URL for http communication.
        """
        response = self.auth_client.user_info()
        return response['urls']

    # Backend-related public functions.

    def list_backends(self):
        """Return a list of backends.

        Returns:
            list[dict]: a list of backends.
        """
        return self.api_client.backends()

    def backend_status(self, backend_name):
        """Return the status of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend status.
        """
        return self.api_client.backend(backend_name).status()

    def backend_properties(self, backend_name):
        """Return the properties of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend properties.
        """
        return self.api_client.backend(backend_name).properties()

    def backend_pulse_defaults(self, backend_name):
        """Return the pulse defaults of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend pulse defaults.
        """
        # pylint: disable=unused-argument
        # return self.api_client.backend(backend_name).pulse_defaults()
        return None

    # Jobs-related public functions.

    def list_jobs_statuses(self, limit=10, skip=0, extra_filter=None):
        """Return a list of statuses of jobs, with filtering and pagination.

        Args:
            limit (int): maximum number of items to return.
            skip (int): offset for the items to return.
            extra_filter (dict): additional filtering passed to the query.

        Returns:
            list[dict]: a list of job statuses.
        """
        return self.api_client.jobs(limit=limit, skip=skip,
                                    extra_filter=extra_filter)

    def job_run_qobj(self, backend_name, qobj_dict):
        """Submit a Qobj to a device.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.

        Returns:
            dict: job status.
        """
        return self.api_client.run_job(backend_name, qobj_dict)

    def job_get(self, job_id, excluded_fields=None, included_fields=None):
        """Return information about a job.

        Args:
            job_id (str): the id of the job.
            excluded_fields (list[str]): names of the fields to explicitly
                exclude from the result.
            included_fields (list[str]): names of the fields to explicitly
                include in the result.

        Returns:
            dict: job information.
        """
        return self.api_client.job(job_id).get(excluded_fields,
                                               included_fields)

    def job_status(self, job_id):
        """Return the status of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.
        """
        return self.api_client.job(job_id).status()

    def job_properties(self, job_id):
        """Return the backend properties of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: backend properties.
        """
        return self.api_client.job(job_id).properties()

    def job_cancel(self, job_id):
        """Submit a request for cancelling a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job cancellation response.
        """
        return self.api_client.job(job_id).cancel()

    # Miscellaneous public functions.

    def api_version(self):
        """Return the version of the API.

        Returns:
            dict: versions of the api components.
        """
        return self.api_client.version()

    def circuit_run(self, name, **kwargs):
        """Execute a Circuit.

        Args:
            name (str): name of the Circuit.
            **kwargs (dict): arguments for the Circuit.

        Returns:
            dict: json response.
        """
        return self.api_client.circuit(name, **kwargs)

    # Endpoints for compatibility with classic IBMQConnector. These functions
    # are meant to facilitate the transition, and should be removed moving
    # forward.

    def get_status_job(self, id_job):
        # pylint: disable=missing-docstring
        return self.job_status(id_job)

    def run_job(self, qobj, backend_name):
        # pylint: disable=missing-docstring
        return self.job_run_qobj(backend_name, qobj)

    def get_jobs(self, limit=10, skip=0, backend=None, only_completed=False,
                 filter=None):
        # pylint: disable=missing-docstring,redefined-builtin
        # TODO: this function seems to be unused currently in IBMQConnector.
        raise NotImplementedError

    def get_status_jobs(self, limit=10, skip=0, backend=None, filter=None):
        # pylint: disable=missing-docstring,redefined-builtin
        if backend:
            filter = filter or {}
            filter.update({'backend.name': backend})

        return self.list_jobs_statuses(limit, skip, filter)

    def cancel_job(self, id_job):
        # pylint: disable=missing-docstring
        return self.job_cancel(id_job)

    def backend_defaults(self, backend):
        # pylint: disable=missing-docstring
        return self.backend_pulse_defaults(backend)

    def available_backends(self):
        # pylint: disable=missing-docstring
        return self.list_backends()

    def get_job(self, id_job, exclude_fields=None, include_fields=None):
        # pylint: disable=missing-docstring
        return self.job_get(id_job, exclude_fields, include_fields)
