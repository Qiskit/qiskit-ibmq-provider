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

import asyncio

from .session import RetrySession
from .rest import Api, Auth
from .websocket import WebsocketClient
from .exceptions import RequestsApiError, AuthenticationLicenseError


class IBMQClient:
    """Client for programmatic access to the IBM Q API."""

    def __init__(self, api_token, auth_url, **request_kwargs):
        """IBMQClient constructor.

        Args:
            api_token (str): IBM Q api token.
            auth_url (str): URL for the authentication service.
            **request_kwargs (dict): arguments for the `requests` Session.
        """
        self.api_token = api_token
        self.auth_url = auth_url

        self.client_auth = Auth(RetrySession(auth_url, **request_kwargs))
        self.client_api, self.client_ws = self._init_service_clients(
            **request_kwargs)

    def _init_service_clients(self, **request_kwargs):
        """Initialize the clients used for communicating with the API and ws.

        Args:
            **request_kwargs (dict): arguments for the `requests` Session.

        Returns:
            tuple(Api, WebsocketClient):
                Api: client for the api server.
                WebsocketClient: client for the websocket server.
        """
        # Request an access token.
        access_token = self._request_access_token()
        # Use the token for the next auth server requests.
        self.client_auth.session.access_token = access_token
        service_urls = self._user_urls()

        # Create the api server client, using the access token.
        client_api = Api(RetrySession(service_urls['http'], access_token,
                                      **request_kwargs))

        # Create the websocket server client, using the access token.
        client_ws = WebsocketClient(service_urls['ws'], access_token)

        return client_api, client_ws

    def _request_access_token(self):
        """Request a new access token from the API.

        Returns:
            str: access token.

        Raises:
            AuthenticationLicenseError: if the user hasn't accepted the license agreement.
            RequestsApiError: if the request failed.
        """
        try:
            response = self.client_auth.login(self.api_token)
            return response['id']
        except RequestsApiError as ex:
            response = ex.original_exception.response
            if response is not None and response.status_code == 401:
                try:
                    error_code = response.json()['error']['name']
                    if error_code == 'ACCEPT_LICENSE_REQUIRED':
                        message = response.json()['error']['message']
                        raise AuthenticationLicenseError(message)
                except (ValueError, KeyError):
                    # the response did not contain the expected json.
                    pass
            raise

    def _check_token(self, response):
        """Generate a new access token if a 401 response was received."""
        if response.status_code == 401:
            new_access_token = self._request_access_token()
            self.client_api.session.access_token = new_access_token
            self.client_ws.access_token = new_access_token
            return False
        return True

    def _user_urls(self):
        """Retrieve the api URLs from the auth server.

        Returns:
            dict: a dict with the base URLs for the services. Currently
                supported keys:
                * ``http``: the api URL for http communication.
                * ``ws``: the api URL for websocket communication.
        """
        response = self.client_auth.user_info()
        return response['urls']

    def _user_hubs(self):
        """Retrieve the hubs available to the user.

        The first entry in the list will be the default one, as indicated by
        the API (by having `isDefault` in all hub, group, project fields).

        Returns:
            list[dict]: a list of dicts with the hubs, which contains the keys
                `hub`, `group`, `project`.

        Raises:
            RequestsApiError: if the request to the API session
                failed despite a new access token being generated.
        """
        try:
            response = self.client_api.hubs()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                response = self.client_api.hubs()
            else:
                raise

        hubs = []
        for hub in response:
            hub_name = hub['name']
            for group_name, group in hub['groups'].items():
                for project_name, project in group['projects'].items():
                    entry = {'hub': hub_name,
                             'group': group_name,
                             'project': project_name}

                    # If
                    if project.get('isDefault'):
                        hubs.insert(0, entry)
                    else:
                        hubs.append(entry)

        return hubs

    # Backend-related public functions.

    def list_backends(self):
        """Return a list of backends.

        Returns:
            list[dict]: a list of backends.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.backends()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.backends()
            else:
                raise

    def backend_status(self, backend_name):
        """Return the status of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend status.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.backend(backend_name).status()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.backend(backend_name).status()
            else:
                raise

    def backend_properties(self, backend_name):
        """Return the properties of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend properties.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.backend(backend_name).properties()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.backend(backend_name).properties()
            else:
                raise

    def backend_pulse_defaults(self, backend_name):
        """Return the pulse defaults of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend pulse defaults.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.backend(backend_name).pulse_defaults()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.backend(backend_name).pulse_defaults()
            else:
                raise

    # Jobs-related public functions.

    def list_jobs_statuses(self, limit=10, skip=0, extra_filter=None):
        """Return a list of statuses of jobs, with filtering and pagination.

        Args:
            limit (int): maximum number of items to return.
            skip (int): offset for the items to return.
            extra_filter (dict): additional filtering passed to the query.

        Returns:
            list[dict]: a list of job statuses.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.jobs(limit=limit, skip=skip,
                                        extra_filter=extra_filter)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.jobs(limit=limit, skip=skip,
                                            extra_filter=extra_filter)
            else:
                raise

    def job_submit(self, backend_name, qobj_dict):
        """Submit a Qobj to a device.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.

        Returns:
            dict: job status.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.submit_job(backend_name, qobj_dict)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.submit_job(backend_name, qobj_dict)
            else:
                raise

    def job_submit_object_storage(self, backend_name, qobj_dict):
        """Submit a Qobj to a device using object storage.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.

        Returns:
            dict: job status.

        Raises:
            RequestsApiError: if a request to the API session
                failed despite a new access token being generated.
        """
        # Get the job via object storage.
        try:
            job_info = self.client_api.submit_job_object_storage(backend_name)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                job_info = self.client_api.submit_job_object_storage(backend_name)
            else:
                raise

        # Get the upload URL.
        job_id = job_info['id']

        try:
            job_api = self.client_api.job(job_id)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                job_api = self.client_api.job(job_id)
            else:
                raise

        upload_url = job_api.upload_url()['url']

        # Upload the Qobj to object storage.
        _ = job_api.put_object_storage(upload_url, qobj_dict)

        # Notify the API via the callback.
        response = job_api.callback_upload()

        return response['job']

    def job_download_qobj_object_storage(self, job_id):
        """Return a Qobj from object storage.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: Qobj, in dict form.

        Raises:
            RequestsApiError: if the request to the API session
                failed despite a new access token being generated.
        """
        try:
            job_api = self.client_api.job(job_id)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                job_api = self.client_api.job(job_id)
            else:
                raise

        # Get the download URL.
        download_url = job_api.download_url()['url']

        # Download the result from object storage.
        return job_api.get_object_storage(download_url)

    def job_result_object_storage(self, job_id):
        """Return a result using object storage.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job information.

        Raises:
            RequestsApiError: if the request to the API session
                failed despite a new access token being generated.
        """
        try:
            job_api = self.client_api.job(job_id)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                job_api = self.client_api.job(job_id)
            else:
                raise

        # Get the download URL.
        download_url = job_api.result_url()['url']

        # Download the result from object storage.
        return job_api.get_object_storage(download_url)

    def job_get(self, job_id, excluded_fields=None, included_fields=None):
        """Return information about a job.

        Args:
            job_id (str): the id of the job.
            excluded_fields (list[str]): names of the fields to explicitly
                exclude from the result.
            included_fields (list[str]): names of the fields, if present, to explicitly
                include in the result. All the other fields will not be included in the result.

        Returns:
            dict: job information.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.job(job_id).get(excluded_fields, included_fields)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.job(job_id).get(excluded_fields, included_fields)
            else:
                raise

    def job_status(self, job_id):
        """Return the status of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.job(job_id).status()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.job(job_id).status()
            else:
                raise

    def job_final_status_websocket(self, job_id, timeout=None):
        """Return the final status of a job via websocket.

        Args:
            job_id (str): the id of the job.
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.

        Returns:
            dict: job status.
        """
        # As mentioned in `websocket.py`, in jupyter we need to use
        # `nest_asyncio` to allow nested event loops.
        return asyncio.get_event_loop().run_until_complete(
            self.client_ws.get_job_status(job_id, timeout=timeout))

    def job_properties(self, job_id):
        """Return the backend properties of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: backend properties.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.job(job_id).properties()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.job(job_id).properties()
            else:
                raise

    def job_cancel(self, job_id):
        """Submit a request for cancelling a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job cancellation response.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.job(job_id).cancel()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.job(job_id).cancel()
            else:
                raise

    # Circuits-related public functions.

    def circuit_run(self, name, **kwargs):
        """Execute a Circuit.

        Args:
            name (str): name of the Circuit.
            **kwargs (dict): arguments for the Circuit.

        Returns:
            dict: json response.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.circuit(name, **kwargs)
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.circuit(name, **kwargs)
            else:
                raise

    def circuit_job_get(self, job_id):
        """Return information about a Circuit job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job information.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.job(job_id).get([], [])
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.job(job_id).get([], [])
            else:
                raise

    def circuit_job_status(self, job_id):
        """Return the status of a Circuits job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.

        """
        return self.job_status(job_id)

    # Miscellaneous public functions.

    def api_version(self):
        """Return the version of the API.

        Returns:
            dict: versions of the api components.

        Raises:
            RequestsApiError: if the request failed despite a new access token being generated.
        """
        try:
            return self.client_api.version()
        except RequestsApiError as ex:
            # check the user's access token is valid, generating a new one if needed
            if not self._check_token(ex.original_exception.response):
                return self.client_api.version()
            else:
                raise

    # Endpoints for compatibility with classic IBMQConnector. These functions
    # are meant to facilitate the transition, and should be removed moving
    # forward.

    def get_status_job(self, id_job):
        # pylint: disable=missing-docstring
        return self.job_status(id_job)

    def submit_job(self, qobj_dict, backend_name):
        # pylint: disable=missing-docstring
        return self.job_submit(backend_name, qobj_dict)

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
