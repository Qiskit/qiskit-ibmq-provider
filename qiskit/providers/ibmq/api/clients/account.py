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
import logging
import time
import pprint

from typing import List, Dict, Any, Optional
# Disabled unused-import because datetime is used only for type hints.
from datetime import datetime  # pylint: disable=unused-import
from marshmallow.exceptions import ValidationError

from qiskit.providers.ibmq.apiconstants import API_JOB_FINAL_STATES, ApiJobStatus

from ..exceptions import (RequestsApiError, WebsocketError,
                          WebsocketTimeoutError, UserTimeoutExceededError)
from ..rest import Api
from ..session import RetrySession
from .base import BaseClient
from .websocket import WebsocketClient
from ..rest.schemas.job import JobStatusResponseSchema

logger = logging.getLogger(__name__)


class AccountClient(BaseClient):
    """Client for accessing an individual IBM Q Experience account.

    This client provides access to an individual IBM Q hub/group/project.
    """

    def __init__(
            self,
            access_token: str,
            project_url: str,
            websockets_url: str,
            **request_kwargs: Any
    ) -> None:
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
        self._use_object_storage = True
        self._use_websockets = True

    # Backend-related public functions.

    def list_backends(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Return the list of backends.

        Args:
            timeout (float or None): number of seconds to wait for the request.

        Returns:
            list[dict]: a list of backends.
        """
        return self.client_api.backends(timeout=timeout)

    def backend_status(self, backend_name: str) -> Dict[str, Any]:
        """Return the status of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend status.
        """
        return self.client_api.backend(backend_name).status()

    def backend_properties(
            self,
            backend_name: str,
            datetime: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Return the properties of a backend.

        Args:
            backend_name (str): the name of the backend.
            datetime (datetime.datetime): datetime for
                additional filtering of backend properties.

        Returns:
            dict: backend properties.
        """
        # pylint: disable=redefined-outer-name
        return self.client_api.backend(backend_name).properties(datetime=datetime)

    def backend_pulse_defaults(self, backend_name: str) -> Dict:
        """Return the pulse defaults of a backend.

        Args:
            backend_name (str): the name of the backend.

        Returns:
            dict: backend pulse defaults.
        """
        return self.client_api.backend(backend_name).pulse_defaults()

    # Jobs-related public functions.

    def list_jobs_statuses(
            self,
            limit: int = 10,
            skip: int = 0,
            extra_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
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

    def job_submit(self, backend_name: str, qobj_dict: Dict[str, Any],
                   job_name: Optional[str] = None):
        """Submit a Qobj to a device.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.
            job_name (str): custom name to be assigned to the job.

        Returns:
            dict: job status.
        """
        submit_info = None
        if self._use_object_storage:
            # Attempt to use object storage.
            try:
                submit_info = self._job_submit_object_storage(
                    backend_name=backend_name,
                    qobj_dict=qobj_dict,
                    job_name=job_name)
            except Exception as err:  # pylint: disable=broad-except
                # Fall back to submitting the Qobj via POST if object storage
                # failed.
                logger.info('Submitting the job via object storage failed: '
                            'retrying via regular POST upload.')
                logger.debug(err)
                # Disable object storage for this job.
                self._use_object_storage = False

        if not submit_info:
            submit_info = self._job_submit_post(backend_name, qobj_dict, job_name)

        return submit_info

    def _job_submit_post(self, backend_name: str, qobj_dict: Dict[str, Any],
                         job_name: Optional[str] = None) -> Dict[str, Any]:
        """Submit a Qobj to a device using HTTP POST.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.
            job_name (str): custom name to be assigned to the job.

        Returns:
            dict: job status.
        """
        return self.client_api.job_submit(backend_name, qobj_dict, job_name)

    def _job_submit_object_storage(
            self, backend_name: str, qobj_dict: Dict[str, Any],
            job_name: Optional[str] = None) -> Dict:
        """Submit a Qobj to a device using object storage.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.
            job_name (str): custom name to be assigned to the job.

        Returns:
            dict: job status.
        """
        # Get the job via object storage.
        job_info = self.client_api.submit_job_object_storage(backend_name, job_name=job_name)

        # Get the upload URL.
        job_id = job_info['id']
        job_api = self.client_api.job(job_id)
        upload_url = job_api.upload_url()['url']

        # Upload the Qobj to object storage.
        _ = job_api.put_object_storage(upload_url, qobj_dict)

        # Notify the API via the callback.
        response = job_api.callback_upload()

        return response['job']

    def job_download_qobj(self, job_id: str) -> Dict:
        """Retrieve and return a Qobj.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: Qobj, in dict form.
        """
        if self._use_object_storage:
            return self._job_download_qobj_object_storage(job_id)
        else:
            return self.job_get(job_id).get('qObject', {})

    def _job_download_qobj_object_storage(self, job_id: str) -> Dict:
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

    def job_result(self, job_id: str) -> Dict:
        """Retrieve and return a job result using object storage.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job information.
        """
        if self._use_object_storage:
            return self._job_result_object_storage(job_id)
        else:
            return self.job_get(job_id)['qObjectResult']

    def _job_result_object_storage(self, job_id: str) -> Dict:
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
        result_response = job_api.get_object_storage(download_url)

        # Notify the API via the callback
        try:
            _ = job_api.callback_download()
        except (RequestsApiError, ValueError) as ex:
            logger.warning("An error occurred while sending download completion acknowledgement: "
                           "%s", ex)
        return result_response

    def job_get(
            self,
            job_id: str,
            excluded_fields: Optional[List[str]] = None,
            included_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
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

    def job_status(self, job_id: str) -> Dict[str, Any]:
        """Return the status of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.
        Raises:
            RequestsApiError: if an unexpected result is received from the server.
        """
        api_response = self.client_api.job(job_id).status()
        try:
            # Validate the response
            JobStatusResponseSchema().validate(api_response)
        except ValidationError as err:
            raise RequestsApiError('Unrecognized answer from server: \n{}'.format(
                pprint.pformat(api_response))) from err
        return api_response

    def job_final_status(self, job_id: str, timeout: Optional[float] = None,
                         wait: float = 5):
        """Wait until the job progress to a final state.

        Args:
            job_id (str): the id of the job
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.
            wait (float): seconds between queries.

        Returns:
            dict: job status.

        Raises:
            UserTimeoutExceededError: if the job does not return results
                before a specified timeout.
        """
        # Attempt to use websocket if available.
        if self._use_websockets:
            start_time = time.time()
            try:
                status_response = self._job_final_status_websocket(job_id, timeout)
                return status_response
            except WebsocketTimeoutError as ex:
                logger.warning('Timeout checking job status using websocket, '
                               'retrying using HTTP')
                logger.debug(ex)
            except (RuntimeError, WebsocketError) as ex:
                logger.warning('Error checking job status using websocket, '
                               'retrying using HTTP.')
                logger.debug(ex)

            # Adjust timeout for HTTP retry.
            if timeout is not None:
                timeout -= (time.time() - start_time)

        # Use traditional http requests if websocket not available or failed.
        start_time = time.time()
        status_response = self.job_status(job_id)
        while ApiJobStatus(status_response['status']) not in API_JOB_FINAL_STATES:
            elapsed_time = time.time() - start_time
            if timeout is not None and elapsed_time >= timeout:
                raise UserTimeoutExceededError(
                    'Timeout while waiting for job {}'.format(job_id))

            logger.info('API job status = %s (%d seconds)',
                        status_response['status'], elapsed_time)
            time.sleep(wait)
            status_response = self.job_status(job_id)

        return status_response

    def _job_final_status_websocket(
            self,
            job_id: str,
            timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Return the final status of a job via websocket.

        Args:
            job_id (str): the id of the job.
            timeout (float or None): seconds to wait for job. If None, wait
                indefinitely.

        Returns:
            dict: job status.

        Raises:
            RuntimeError: if an unexpected error occurred while getting the event loop.
            WebsocketError: if the websocket connection ended unexpectedly.
            WebsocketTimeoutError: if the timeout has been reached.
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

    def job_properties(self, job_id: str) -> Dict:
        """Return the backend properties of a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: backend properties.
        """
        return self.client_api.job(job_id).properties()

    def job_cancel(self, job_id: str) -> Dict[str, Any]:
        """Submit a request for cancelling a job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job cancellation response.
        """
        return self.client_api.job(job_id).cancel()

    # Circuits-related public functions.

    def circuit_run(self, name: str, **kwargs: Any) -> Dict:
        """Execute a Circuit.

        Args:
            name (str): name of the Circuit.
            **kwargs (dict): arguments for the Circuit.

        Returns:
            dict: json response.
        """
        return self.client_api.circuit(name, **kwargs)

    def circuit_job_get(self, job_id: str) -> Dict:
        """Return information about a Circuit job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job information.
        """
        return self.client_api.job(job_id).get([], [])

    def circuit_job_status(self, job_id: str) -> Dict:
        """Return the status of a Circuits job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.
        """
        return self.job_status(job_id)
