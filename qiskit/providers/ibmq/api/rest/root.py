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

"""Root REST adapter for the IBM Q Experience API."""

import json

from typing import Dict, List, Optional, Any

from .base import RestAdapterBase
from .backend import Backend
from .job import Job


class Api(RestAdapterBase):
    """Rest adapter for general endpoints."""

    URL_MAP = {
        'backends': '/devices/v/1',
        'hubs': '/Network',
        'jobs': '/Jobs',
        'jobs_status': '/Jobs/status',
        'circuit': '/qcircuit',
        'version': '/version'
    }

    def backend(self, backend_name: str) -> Backend:
        """Return a adapter for a specific backend.

        Args:
            backend_name: name of the backend.

        Returns:
            the backend adapter.
        """
        return Backend(self.session, backend_name)

    def job(self, job_id: str) -> Job:
        """Return a adapter for a specific job.

        Args:
            job_id: id of the job.

        Returns:
            the backend adapter.
        """
        return Job(self.session, job_id)

    def backends(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Return the list of backends.

        Args:
            timeout: number of seconds to wait for the request.

        Returns:
            json response.
        """
        url = self.get_url('backends')
        return self.session.get(url, timeout=timeout).json()

    def hubs(self) -> List[Dict[str, Any]]:
        """Return the list of hubs available to the user."""
        url = self.get_url('hubs')
        return self.session.get(url).json()

    def jobs(
            self,
            limit: int = 10,
            skip: int = 0,
            extra_filter: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Return a list of jobs statuses.

        Args:
            limit: maximum number of items to return.
            skip: offset for the items to return.
            extra_filter: additional filtering passed to the query.

        Returns:
            json response.
        """
        url = self.get_url('jobs_status')

        query = {
            'order': 'creationDate DESC',
            'limit': limit,
            'skip': skip,
        }
        if extra_filter:
            query['where'] = extra_filter

        return self.session.get(
            url, params={'filter': json.dumps(query)}).json()

    def job_submit(
            self,
            backend_name: str,
            qobj_dict: Dict[str, Any],
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Submit a job for executing.

        Args:
            backend_name: the name of the backend.
            qobj_dict: the Qobj to be executed, as a dictionary.
            job_name: custom name to be assigned to the job.
            job_share_level: level the job should be shared at.
            job_tags: tags to be assigned to the job.

        Returns:
            json response.
        """
        url = self.get_url('jobs')

        payload = {
            'qObject': qobj_dict,
            'backend': {'name': backend_name},
            'shots': qobj_dict.get('config', {}).get('shots', 1)
        }

        if job_name:
            payload['name'] = job_name

        if job_share_level:
            payload['shareLevel'] = job_share_level

        if job_tags:
            payload['tags'] = job_tags

        return self.session.post(url, json=payload).json()

    def submit_job_object_storage(
            self,
            backend_name: str,
            shots: int = 1,
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Submit a job for executing, using object storage.

        Args:
            backend_name: the name of the backend.
            shots: number of shots.
            job_name: custom name to be assigned to the job.
            job_share_level: level the job should be shared at.
            job_tags: tags to be assigned to the job.

        Returns:
            json response.
        """
        url = self.get_url('jobs')

        # TODO: "shots" is currently required by the API.
        payload = {
            'backend': {'name': backend_name},
            'shots': shots,
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
            name: name of the Circuit.
            **kwargs: arguments for the Circuit.

        Returns:
            json response.
        """
        url = self.get_url('circuit')

        payload = {
            'name': name,
            'params': kwargs
        }

        return self.session.post(url, json=payload).json()

    def version(self) -> Dict[str, Any]:
        """Return the API versions."""
        url = self.get_url('version')
        return self.session.get(url).json()
