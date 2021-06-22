# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Client for accessing an individual IBM Quantum Experience account."""

import logging
import time
from threading import Timer

from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from qiskit.providers.ibmq.apiconstants import API_JOB_FINAL_STATES, ApiJobStatus
from qiskit.providers.ibmq.utils.utils import RefreshQueue
from qiskit.providers.ibmq.credentials import Credentials

from ..exceptions import (RequestsApiError, WebsocketError,
                          WebsocketTimeoutError, UserTimeoutExceededError)
from ..rest import Api, Account
from ..rest.backend import Backend
from ..session import RetrySession
from ..exceptions import ApiIBMQProtocolError
from .base import BaseClient
from .websocket import WebsocketClient, WebsocketClientCloseCode

logger = logging.getLogger(__name__)


class AccountClient(BaseClient):
    """Client for accessing an individual IBM Quantum Experience account."""

    def __init__(
            self,
            credentials: Credentials,
            **request_kwargs: Any
    ) -> None:
        """AccountClient constructor.

        Args:
            credentials: Account credentials.
            **request_kwargs: Arguments for the request ``Session``.
        """
        self._session = RetrySession(
            credentials.base_url, credentials.access_token, **request_kwargs)
        # base_api is used to handle endpoints that don't include h/g/p.
        # account_api is for h/g/p.
        self.base_api = Api(self._session)
        self.account_api = Account(session=self._session, hub=credentials.hub,
                                   group=credentials.group, project=credentials.project)
        self._credentials = credentials

    # Backend-related public functions.

    def list_backends(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Return backends available for this provider.

        Args:
            timeout: Number of seconds to wait for the request.

        Returns:
            Backends available for this provider.
        """
        return self.account_api.backends(timeout=timeout)

    def backend_status(self, backend_name: str) -> Dict[str, Any]:
        """Return the status of the backend.

        Args:
            backend_name: The name of the backend.

        Returns:
            Backend status.
        """
        return self.account_api.backend(backend_name).status()

    def backend_properties(
            self,
            backend_name: str,
            datetime: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Return the properties of the backend.

        Args:
            backend_name: The name of the backend.
            datetime: Date and time for additional filtering of backend properties.

        Returns:
            Backend properties.
        """
        # pylint: disable=redefined-outer-name
        return self.account_api.backend(backend_name).properties(datetime=datetime)

    def backend_pulse_defaults(self, backend_name: str) -> Dict:
        """Return the pulse defaults of the backend.

        Args:
            backend_name: The name of the backend.

        Returns:
            Backend pulse defaults.
        """
        return self.account_api.backend(backend_name).pulse_defaults()

    def backend_job_limit(self, backend_name: str) -> Dict[str, Any]:
        """Return the job limit for the backend.

        Args:
            backend_name: The name of the backend.

        Returns:
            Backend job limit.
        """
        return self.account_api.backend(backend_name).job_limit()

    def backend_reservations(
            self,
            backend_name: str,
            start_datetime: Optional[datetime] = None,
            end_datetime: Optional[datetime] = None
    ) -> List:
        """Return backend reservation information.

        Args:
            backend_name: Name of the backend.
            start_datetime: Starting datetime in UTC.
            end_datetime: Ending datetime in UTC.

        Returns:
            Backend reservation information.
        """
        backend_api = Backend(self._session, backend_name, '/Network')
        return backend_api.reservations(start_datetime, end_datetime)

    def my_reservations(self) -> List:
        """Return backend reservations made by the caller.

        Returns:
            Backend reservation information.
        """
        return self.base_api.reservations()

    # Jobs-related public functions.

    def list_jobs_statuses(
            self,
            limit: int = 10,
            skip: int = 0,
            descending: bool = True,
            extra_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Return a list of job data, with filtering and pagination.

        In order to reduce the amount of data transferred, the server only
        sends back a subset of the total information for each job.

        Args:
            limit: Maximum number of items to return.
            skip: Offset for the items to return.
            descending: Whether the jobs should be in descending order.
            extra_filter: Additional filtering passed to the query.

        Returns:
            A list of job data.
        """
        return self.account_api.jobs(limit=limit, skip=skip, descending=descending,
                                     extra_filter=extra_filter)

    def job_submit(
            self,
            backend_name: str,
            qobj_dict: Dict[str, Any],
            job_name: Optional[str] = None,
            job_tags: Optional[List[str]] = None,
            experiment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a ``Qobj`` to the backend.

        Args:
            backend_name: The name of the backend.
            qobj_dict: The ``Qobj`` to be executed, as a dictionary.
            job_name: Custom name to be assigned to the job.
            job_tags: Tags to be assigned to the job.
            experiment_id: Used to add a job to an experiment.

        Returns:
            Job data.

        Raises:
            RequestsApiError: If an error occurred communicating with the server.
        """
        # pylint: disable=missing-raises-doc

        # Create a remote job instance on the server.
        job_info = self.account_api.create_remote_job(
            backend_name,
            job_name=job_name,
            job_tags=job_tags,
            experiment_id=experiment_id)

        # Get the upload URL.
        job_id = job_info['id']
        upload_url = job_info['objectStorageInfo']['uploadUrl']
        job_api = self.account_api.job(job_id)

        try:
            # Upload the Qobj to object storage.
            _ = job_api.put_object_storage(upload_url, qobj_dict)
            # Notify the API via the callback.
            response = job_api.callback_upload()
            return response['job']
        except Exception:  # pylint: disable=broad-except
            try:
                job_api.cancel()    # Cancel the job so it doesn't become a phantom job.
            except Exception:  # pylint: disable=broad-except
                pass
            raise

    def job_download_qobj(self, job_id: str, use_object_storage: bool) -> Dict:
        """Retrieve and return a ``Qobj``.

        Args:
            job_id: The ID of the job.
            use_object_storage: ``True`` if object storage should be used.

        Returns:
            ``Qobj`` in dictionary form.
        """
        if use_object_storage:
            return self._job_download_qobj_object_storage(job_id)
        else:
            return self.job_get(job_id).get('qObject', {})

    def _job_download_qobj_object_storage(self, job_id: str) -> Dict:
        """Retrieve and return a ``Qobj`` using object storage.

        Args:
            job_id: The ID of the job.

        Returns:
            ``Qobj`` in dictionary form.
        """
        job_api = self.account_api.job(job_id)

        # Get the download URL.
        download_url = job_api.download_url()['url']

        # Download the result from object storage.
        return job_api.get_object_storage(download_url)

    def job_result(self, job_id: str, use_object_storage: bool) -> Dict:
        """Retrieve and return the job result.

        Args:
            job_id: The ID of the job.
            use_object_storage: ``True`` if object storage should be used.

        Returns:
            Job result.

        Raises:
            ApiIBMQProtocolError: If unexpected data is received from the server.
        """
        if use_object_storage:
            return self._job_result_object_storage(job_id)

        try:
            return self.job_get(job_id)['qObjectResult']
        except KeyError as err:
            raise ApiIBMQProtocolError(
                'Unexpected return value received from the server: {}'.format(str(err))) from err

    def _job_result_object_storage(self, job_id: str) -> Dict:
        """Retrieve and return the job result using object storage.

        Args:
            job_id: The ID of the job.

        Returns:
            Job result.
        """
        job_api = self.account_api.job(job_id)

        # Get the download URL.
        download_url = job_api.result_url()['url']

        # Download the result from object storage.
        result_response = job_api.get_object_storage(download_url)

        # Notify the API via the callback
        try:
            _ = job_api.callback_download()
        except (RequestsApiError, ValueError) as ex:
            logger.warning('An error occurred while sending download completion acknowledgement: '
                           '%s', ex)
        return result_response

    def job_get(
            self,
            job_id: str
    ) -> Dict[str, Any]:
        """Return information about the job.

        Args:
            job_id: The ID of the job.

        Returns:
            Job information.
        """
        return self.account_api.job(job_id).get()

    def job_status(self, job_id: str) -> Dict[str, Any]:
        """Return the status of the job.

        Args:
            job_id: The ID of the job.

        Returns:
            Job status.

        Raises:
            ApiIBMQProtocolError: If unexpected data is received from the server.
        """
        return self.account_api.job(job_id).status()

    def job_final_status(
            self,
            job_id: str,
            timeout: Optional[float] = None,
            wait: float = 5,
            status_queue: Optional[RefreshQueue] = None
    ) -> Dict[str, Any]:
        """Wait until the job progresses to a final state.

        Args:
            job_id: The ID of the job.
            timeout: Time to wait for job, in seconds. If ``None``, wait indefinitely.
            wait: Seconds between queries.
            status_queue: Queue used to share the latest status.

        Returns:
            Job status.

        Raises:
            UserTimeoutExceededError: If the job does not return results
                before the specified timeout.
            ApiIBMQProtocolError: If unexpected data is received from the server.
        """
        status_response = None
        # Attempt to use websocket if available.
        start_time = time.time()
        try:
            status_response = self._job_final_status_websocket(
                job_id=job_id, timeout=timeout, status_queue=status_queue)
        except WebsocketTimeoutError as ex:
            logger.info('Timeout checking job status using websocket, '
                        'retrying using HTTP: %s', ex)
        except (RuntimeError, WebsocketError) as ex:
            logger.info('Error checking job status using websocket, '
                        'retrying using HTTP: %s', ex)

        # Adjust timeout for HTTP retry.
        if timeout is not None:
            timeout -= (time.time() - start_time)

        if not status_response:
            # Use traditional http requests if websocket not available or failed.
            status_response = self._job_final_status_polling(
                job_id, timeout, wait, status_queue)

        return status_response

    def _job_final_status_websocket(
            self,
            job_id: str,
            timeout: Optional[float] = None,
            status_queue: Optional[RefreshQueue] = None
    ) -> Dict[str, Any]:
        """Return the final status of the job via websocket.

        Args:
            job_id: The ID of the job.
            timeout: Time to wait for job, in seconds. If ``None``, wait indefinitely.
            status_queue: Queue used to share the latest status.

        Returns:
            Job status.

        Raises:
            WebsocketError: If the websocket connection ended unexpectedly.
            WebsocketTimeoutError: If the timeout has been reached.
        """
        ws_client = WebsocketClient(
            websocket_url=self._credentials.websockets_url.rstrip('/'),
            credentials=self._credentials,
            job_id=job_id,
            message_queue=status_queue
        )
        timer = None
        if timeout:
            timer = Timer(timeout, ws_client.disconnect,
                          kwargs={'close_code': WebsocketClientCloseCode.TIMEOUT})
            timer.start()

        try:
            return ws_client.get_job_status()
        finally:
            if timer:
                timer.cancel()

    def _job_final_status_polling(
            self,
            job_id: str,
            timeout: Optional[float] = None,
            wait: float = 5,
            status_queue: Optional[RefreshQueue] = None
    ) -> Dict[str, Any]:
        """Return the final status of the job via polling.

        Args:
            job_id: The ID of the job.
            timeout: Time to wait for job, in seconds. If ``None``, wait indefinitely.
            wait: Seconds between queries.
            status_queue: Queue used to share the latest status.

        Returns:
            Job status.

        Raises:
            UserTimeoutExceededError: If the user specified timeout has been exceeded.
        """
        start_time = time.time()
        status_response = self.job_status(job_id)
        while ApiJobStatus(status_response['status']) not in API_JOB_FINAL_STATES:
            # Share the new status.
            if status_queue is not None:
                status_queue.put(status_response)

            elapsed_time = time.time() - start_time
            if timeout is not None and elapsed_time >= timeout:
                raise UserTimeoutExceededError(
                    'Timeout while waiting for job {}.'.format(job_id))

            logger.info('API job status = %s (%d seconds)',
                        status_response['status'], elapsed_time)
            time.sleep(wait)
            status_response = self.job_status(job_id)

        return status_response

    def job_properties(self, job_id: str) -> Dict:
        """Return the backend properties of the job.

        Args:
            job_id: The ID of the job.

        Returns:
            Backend properties.
        """
        return self.account_api.job(job_id).properties()

    def job_cancel(self, job_id: str) -> Dict[str, Any]:
        """Submit a request for cancelling the job.

        Args:
            job_id: The ID of the job.

        Returns:
            Job cancellation response.
        """
        return self.account_api.job(job_id).cancel()

    def job_update_attribute(
            self,
            job_id: str,
            attr_name: str,
            attr_value: Union[str, List[str]]
    ) -> Dict[str, Any]:
        """Update the specified job attribute with the given value.

        Note:
            The current job attributes that could be edited are ``name``
            and ``tags``.

        Args:
            job_id: The ID of the job to update.
            attr_name: The name of the attribute to update.
            attr_value: The new value to associate the job attribute with.

        Returns:
            A dictionary containing the name of the updated attribute and the new value
            it is associated with.
        """
        return self.account_api.job(job_id).update_attribute({attr_name: attr_value})

    def job_delete(self, job_id: str) -> None:
        """Mark the job for deletion.

        Args:
            job_id: ID of the job to be deleted.
        """
        self.account_api.job(job_id).delete()
