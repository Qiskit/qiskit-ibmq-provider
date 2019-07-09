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

"""Root REST adapter for the IBM Q Experience v2 API."""

import json

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

    def backend(self, backend_name):
        """Return a adapter for a specific backend.

        Args:
            backend_name (str): name of the backend.

        Returns:
            Backend: the backend adapter.
        """
        return Backend(self.session, backend_name)

    def job(self, job_id):
        """Return a adapter for a specific job.

        Args:
            job_id (str): id of the job.

        Returns:
            Job: the backend adapter.
        """
        return Job(self.session, job_id)

    def backends(self):
        """Return the list of backends."""
        url = self.get_url('backends')
        return self.session.get(url).json()

    def hubs(self):
        """Return the list of hubs available to the user."""
        url = self.get_url('hubs')
        return self.session.get(url).json()

    def jobs(self, limit=10, skip=0, extra_filter=None):
        """Return a list of jobs statuses.

        Args:
            limit (int): maximum number of items to return.
            skip (int): offset for the items to return.
            extra_filter (dict): additional filtering passed to the query.

        Returns:
            list[dict]: json response.
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

    def submit_job(self, backend_name, qobj_dict):
        """Submit a job for executing.

        Args:
            backend_name (str): the name of the backend.
            qobj_dict (dict): the Qobj to be executed, as a dictionary.

        Returns:
            dict: json response.
        """
        url = self.get_url('jobs')

        payload = {
            'qObject': qobj_dict,
            'backend': {'name': backend_name},
            'shots': qobj_dict.get('config', {}).get('shots', 1)
        }

        return self.session.post(url, json=payload).json()

    def submit_job_object_storage(self, backend_name, shots=1):
        """Submit a job for executing, using object storage.

        Args:
            backend_name (str): the name of the backend.
            shots (int): number of shots.

        Returns:
            dict: json response.
        """
        url = self.get_url('jobs')

        # TODO: "shots" is currently required by the API.
        payload = {
            'backend': {'name': backend_name},
            'shots': shots,
            'allowObjectStorage': True
        }

        return self.session.post(url, json=payload).json()

    def circuit(self, name, **kwargs):
        """Execute a Circuit.

        Args:
            name (str): name of the Circuit.
            **kwargs (dict): arguments for the Circuit.

        Returns:
            dict: json response.
        """
        url = self.get_url('circuit')

        payload = {
            'name': name,
            'params': kwargs
        }

        return self.session.post(url, json=payload).json()

    def version(self):
        """Return the API versions."""
        url = self.get_url('version')
        return self.session.get(url).json()
