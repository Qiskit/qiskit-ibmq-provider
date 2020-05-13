# -*- coding: utf-8 -*-

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

"""Root REST adapter."""

import json
import logging
from typing import Dict, List, Optional, Any

from qiskit.providers.ibmq.utils.utils import filter_data

from .base import RestAdapterBase
from .backend import Backend
from .job import Job
from .utils.data_mapper import map_job_response

logger = logging.getLogger(__name__)


class Api(RestAdapterBase):
    """Rest adapter for general endpoints."""

    URL_MAP = {
        'backends': '/devices/v/1',
        'hubs': '/Network',
        'jobs': '/Jobs',
        'jobs_status': '/Jobs/status/v/1',
        'circuit': '/qcircuit',
        'version': '/version'
    }

    def backend(self, backend_name: str) -> Backend:
        """Return an adapter for the backend.

        Args:
            backend_name: Name of the backend.

        Returns:
            The backend adapter.
        """
        return Backend(self.session, backend_name)

    def job(self, job_id: str) -> Job:
        """Return an adapter for the job.

        Args:
            job_id: ID of the job.

        Returns:
            The backend adapter.
        """
        return Job(self.session, job_id)

    def backends(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Return a list of backends.

        Args:
            timeout: Number of seconds to wait for the request.

        Returns:
            JSON response.
        """
        url = self.get_url('backends')
        return self.session.get(url, timeout=timeout).json()

    def hubs(self) -> List[Dict[str, Any]]:
        """Return the list of hub/group/project sets available to the user.

        Returns:
            JSON response.
        """
        url = self.get_url('hubs')
        return self.session.get(url).json()

    def jobs(
            self,
            limit: int = 10,
            skip: int = 0,
            descending: bool = True,
            extra_filter: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Return a list of job information.

        Args:
            limit: Maximum number of items to return.
            skip: Offset for the items to return.
            descending: Whether the jobs should be in descending order.
            extra_filter: Additional filtering passed to the query.

        Returns:
            JSON response.
        """
        url = self.get_url('jobs_status')

        order = 'DESC' if descending else 'ASC'

        query = {
            'order': 'creationDate ' + order,
            'limit': limit,
            'skip': skip,
        }
        if extra_filter:
            query['where'] = extra_filter

        if logger.getEffectiveLevel() is logging.DEBUG:
            logger.debug("Endpoint: %s. Method: GET. Request Data: {'filter': %s}",
                         url, filter_data(query))

        data = self.session.get(url, params={'filter': json.dumps(query)}).json()
        for job_data in data:
            map_job_response(job_data)
        return data

    def create_remote_job(
            self,
            backend_name: str,
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a job instance on the remote server.

        Args:
            backend_name: The name of the backend.
            job_name: Custom name to be assigned to the job.
            job_share_level: Level the job should be shared at.
            job_tags: Tags to be assigned to the job.

        Returns:
            JSON response.
        """
        url = self.get_url('jobs')

        payload = {
            'backend': {'name': backend_name},
            'allowObjectStorage': True
        }

        if job_name:
            payload['name'] = job_name

        if job_share_level:
            payload['shareLevel'] = job_share_level

        if job_tags:
            payload['tags'] = job_tags

        return self.session.post(url, json=payload).json()

    def circuit(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute a Circuit.

        Args:
            name: Name of the Circuit.
            **kwargs: Arguments for the Circuit.

        Returns:
            JSON response.
        """
        url = self.get_url('circuit')

        payload = {
            'name': name,
            'params': kwargs
        }

        return self.session.post(url, json=payload).json()

    def version(self) -> Dict[str, Any]:
        """Return the API versions.

        Returns:
            JSON response.
        """
        url = self.get_url('version')
        return self.session.get(url).json()
