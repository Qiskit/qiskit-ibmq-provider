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

"""Client for accessing an individual IBM Q Experience account."""

import asyncio

from ..rest import Api
from ..session import RetrySession

from .base import BaseClient
from .websocket import WebsocketClient


class AccountClient(BaseClient):
    """Client for accessing an individual IBM Q Experience account.

    This client provides access to an individual IBM Q hub/group/project.
    """

    def __init__(self, access_token, project_url, websockets_url, **request_kwargs):
        """AccountClient constructor.

        Args:
            access_token (str): IBM Q Experience access token.
            project_url (str): IBM Q Experience URL for a specific h/g/p.
            websockets_url (str): URL for the websockets server.
            **request_kwargs (dict): arguments for the `requests` Session.
        """
        self.client_api = Api(RetrySession(project_url, access_token,
                                           **request_kwargs))
        self.client_ws = WebsocketClient(websockets_url, access_token)

    # Backend-related public functions.

    def list_backends(self):
        """Return the list of backends.

        Returns:
            list[dict]: a list of backends.
        """
        return self.client_api.backends()

    def backend_status(self, backend_name):
        """Return the status of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend status.
        """
        return self.client_api.backend(backend_name).status()

    def backend_properties(self, backend_name):
        """Return the properties of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend properties.
        """
        return self.client_api.backend(backend_name).properties()

    def backend_pulse_defaults(self, backend_name):
        """Return the pulse defaults of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend pulse defaults.
        """
        return self.client_api.backend(backend_name).pulse_defaults()

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
        return self.client_api.jobs(limit=limit, skip=skip,
                                    extra_filter=extra_filter)

    def job_submit(self, backend_name, qobj_dict):
        """Submit a Qobj to a device.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.

        Returns:
            dict: job status.
        """
        return self.client_api.submit_job(backend_name, qobj_dict)

    def job_submit_object_storage(self, backend_name, qobj_dict):
        """Submit a Qobj to a device using object storage.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.

        Returns:
            dict: job status.
        """
        # Get the job via object storage.
        job_info = self.client_api.submit_job_object_storage(backend_name)

        # Get the upload URL.
        job_id = job_info['id']
        job_api = self.client_api.job(job_id)
        upload_url = job_api.upload_url()['url']

        # Upload the Qobj to object storage.
        _ = job_api.put_object_storage(upload_url, qobj_dict)

        # Notify the API via the callback.
        response = job_api.callback_upload()

        return response['job']

    def job_download_qobj_object_storage(self, job_id):
        """Retrieve and return a Qobj using object storage.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: Qobj, in dict form.
        """
        job_api = self.client_api.job(job_id)

        # Get the download URL.
        download_url = job_api.download_url()['url']

        # Download the result from object storage.
        return job_api.get_object_storage(download_url)

    def job_result_object_storage(self, job_id):
        """Retrieve and return a result using object storage.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job information.
        """
        job_api = self.client_api.job(job_id)

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
        """
        return self.client_api.job(job_id).get(excluded_fields,
                                               included_fields)

    def job_status(self, job_id):
        """Return the status of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.
        """
        return self.client_api.job(job_id).status()

    def job_final_status_websocket(self, job_id, timeout=None):
        """Return the final status of a job via websocket.

        Args:
            job_id (str): the id of the job.
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.

        Returns:
            dict: job status.

        Raises:
            RuntimeError: if an unexpected error occurred while getting the event loop.
        """
        # As mentioned in `websocket.py`, in jupyter we need to use
        # `nest_asyncio` to allow nested event loops.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError as ex:
            # Event loop may not be set in a child thread.
            if 'There is no current event loop' in str(ex):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            else:
                raise
        return loop.run_until_complete(
            self.client_ws.get_job_status(job_id, timeout=timeout))

    def job_properties(self, job_id):
        """Return the backend properties of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: backend properties.
        """
        return self.client_api.job(job_id).properties()

    def job_cancel(self, job_id):
        """Submit a request for cancelling a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job cancellation response.
        """
        return self.client_api.job(job_id).cancel()

    # Circuits-related public functions.

    def circuit_run(self, name, **kwargs):
        """Execute a Circuit.

        Args:
            name (str): name of the Circuit.
            **kwargs (dict): arguments for the Circuit.

        Returns:
            dict: json response.
        """
        return self.client_api.circuit(name, **kwargs)

    def circuit_job_get(self, job_id):
        """Return information about a Circuit job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job information.
        """
        return self.client_api.job(job_id).get([], [])

    def circuit_job_status(self, job_id):
        """Return the status of a Circuits job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.
        """
        return self.job_status(job_id)

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
