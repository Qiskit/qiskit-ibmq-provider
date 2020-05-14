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

"""Job REST adapter."""

import logging
import json
from json.decoder import JSONDecodeError

from typing import Union, Dict, List, Any

from qiskit.providers.ibmq.utils import json_encoder

from .base import RestAdapterBase
from ..session import RetrySession
from ..exceptions import ApiIBMQProtocolError
from .utils.data_mapper import map_job_response, map_job_status_response

logger = logging.getLogger(__name__)


class Job(RestAdapterBase):
    """Rest adapter for job related endpoints."""

    URL_MAP = {
        'callback_upload': '/jobDataUploaded',
        'callback_download': '/resultDownloaded',
        'cancel': '/cancel',
        'download_url': '/jobDownloadUrl',
        'self': '/v/1',
        'self_update': '',
        'status': '/status/v/1',
        'properties': '/properties',
        'result_url': '/resultDownloadUrl',
        'upload_url': '/jobUploadUrl'
    }

    def __init__(self, session: RetrySession, job_id: str) -> None:
        """Job constructor.

        Args:
            session: Session to be used in the adapter.
            job_id: ID of the job.
        """
        self.job_id = job_id
        super().__init__(session, '/Jobs/{}'.format(job_id))

    def get(self) -> Dict[str, Any]:
        """Return job information.

        Returns:
            JSON response of job information.
        """
        url = self.get_url('self')

        response = self.session.get(url).json()

        if 'calibration' in response:
            response['_properties'] = response.pop('calibration')
        response = map_job_response(response)

        return response

    def update_attribute(
            self,
            job_attribute_info: Dict[str, Union[str, List[str]]]
    ) -> Dict[str, Any]:
        """Edit the specified attribute for the job.

        Args:
            job_attribute_info: A dictionary containing the name of the attribute to
                update and the new value it should be associated with. The format is
                {`attribute_name_to_update`: `new_attribute_value`}.

        Returns:
            JSON response containing the name of the updated attribute and its
            corresponding value.
        """
        url = self.get_url('self_update')
        return self.session.put(url, data=json.dumps(job_attribute_info)).json()

    def callback_upload(self) -> Dict[str, Any]:
        """Notify the API after uploading a ``Qobj`` via object storage.

        Returns:
            JSON response.
        """
        url = self.get_url('callback_upload')
        data = self.session.post(url).json()
        mapped_response = {'job': map_job_response(data['job'])}
        return mapped_response

    def callback_download(self) -> Dict[str, Any]:
        """Notify the API after downloading a ``Qobj`` via object storage.

        Returns:
            JSON response.
        """
        url = self.get_url('callback_download')
        return self.session.post(url).json()

    def cancel(self) -> Dict[str, Any]:
        """Cancel a job.

        Returns:
            JSON response.
        """
        url = self.get_url('cancel')
        return self.session.post(url).json()

    def download_url(self) -> Dict[str, Any]:
        """Return an object storage URL for downloading the ``Qobj``.

        Returns:
            JSON response.
        """
        url = self.get_url('download_url')
        return self.session.get(url).json()

    def properties(self) -> Dict[str, Any]:
        """Return the backend properties of a job.

        Returns:
            JSON response.
        """
        url = self.get_url('properties')
        return self.session.get(url).json()

    def result_url(self) -> Dict[str, Any]:
        """Return an object storage URL for downloading results.

        Returns:
            JSON response.
        """
        url = self.get_url('result_url')
        return self.session.get(url).json()

    def status(self) -> Dict[str, Any]:
        """Return the status of a job.

        Returns:
            JSON response of job status.

        Raises:
            ApiIBMQProtocolError: If an unexpected result is received from the server.
        """
        url = self.get_url('status')
        raw_response = self.session.get(url)
        try:
            api_response = raw_response.json()
        except JSONDecodeError as err:
            raise ApiIBMQProtocolError(
                'Unrecognized return value received from the server: {!r}. This could be caused'
                ' by too many requests.'.format(raw_response.content)) from err
        return map_job_status_response(api_response)

    def upload_url(self) -> Dict[str, Any]:
        """Return an object storage URL for uploading the ``Qobj``.

        Returns:
            JSON response.
        """
        url = self.get_url('upload_url')
        return self.session.get(url).json()

    def put_object_storage(self, url: str, qobj_dict: Dict[str, Any]) -> str:
        """Upload a ``Qobj`` via object storage.

        Args:
            url: Object storage URL.
            qobj_dict: The ``Qobj`` to be uploaded, in dictionary form.

        Returns:
            Text response, which is empty if the request was successful.
        """
        data = json.dumps(qobj_dict, cls=json_encoder.IQXJsonEconder)
        logger.debug('Uploading to object storage.')
        response = self.session.put(url, data=data, bare=True, timeout=600)
        return response.text

    def get_object_storage(self, url: str) -> Dict[str, Any]:
        """Get via object_storage.

        Args:
            url: Object storage URL.

        Returns:
            JSON response.
        """
        logger.debug('Downloading from object storage.')
        response = self.session.get(url, bare=True, timeout=600).json()
        return response
