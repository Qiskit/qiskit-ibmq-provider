# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Q API connector."""

import json
import logging
import re

from ..apiconstants import ApiJobStatus
from .exceptions import CredentialsError, BadBackendError
from .utils import Request

logger = logging.getLogger(__name__)


def get_job_url(config):
    """Return the URL for a job."""
    hub = config.get('hub', None)
    group = config.get('group', None)
    project = config.get('project', None)

    if hub and group and project:
        return '/Network/{}/Groups/{}/Projects/{}/jobs'.format(hub, group,
                                                               project)
    return '/Jobs'


def get_backend_properties_url(config, backend_type):
    """Return the URL for a backend's properties."""
    hub = config.get('hub', None)

    if hub:
        return '/Network/{}/devices/{}/properties'.format(hub, backend_type)
    return '/Backends/{}/properties'.format(backend_type)


def get_backend_defaults_url(config, backend_type):
    """Return the URL for a backend's pulse defaults."""
    hub = config.get('hub', None)
    group = config.get('group', None)
    project = config.get('project', None)

    if hub and group and project:
        return '/Network/{}/Groups/{}/Projects/{}/devices/{}/defaults'.format(
            hub, group, project, backend_type)

    return '/Backends/{}/defaults'.format(backend_type)


def get_backends_url(config):
    """Return the URL for a backend."""
    hub = config.get('hub', None)
    group = config.get('group', None)
    project = config.get('project', None)

    if hub and group and project:
        return '/Network/{}/Groups/{}/Projects/{}/devices/v/1'.format(hub, group,
                                                                      project)
    return '/Backends/v/1'


class IBMQConnector:
    """Connector class that handles the requests to the IBMQ platform.

    This class exposes a Python API for making requests to the IBMQ platform.
    """

    def __init__(self, token=None, config=None, verify=True):
        """ If verify is set to false, ignore SSL certificate errors """
        self.config = config

        if self.config and ('url' in self.config):
            url_parsed = re.compile(r'(?<!\/)\/api').split(self.config['url'])
            if len(url_parsed) == 2:
                hub = group = project = None
                project_parse = url_parsed[1].split('/Projects/')
                if len(project_parse) == 2:
                    project = project_parse[1]
                    group_parse = project_parse[0].split('/Groups/')
                    if len(group_parse) == 2:
                        group = group_parse[1]
                        hub_parse = group_parse[0].split('/Hubs/')
                        if len(hub_parse) == 2:
                            hub = hub_parse[1]
                if hub and group and project:
                    self.config['project'] = project
                    self.config['group'] = group
                    self.config['hub'] = hub
                    self.config['url'] = url_parsed[0] + '/api'

        self.req = Request(token, config=config, verify=verify)

    def _check_backend(self, backend_name):
        """Check if the name of a backend is valid to run in QX Platform."""
        backends = self.available_backends()
        for backend_ in backends:
            if backend_.get('backend_name', '') == backend_name:
                return backend_name

        # backend unrecognized
        return None

    def check_credentials(self):
        """Check if the user has permission in QX platform."""
        return bool(self.req.credential.get_token())

    def submit_job(self, qobj_dict, backend_name):
        """Run a Qobj in a IBMQ backend.

        Args:
            qobj_dict (dict): Qobj to be run, in dictionary form.
            backend_name (str): backend name.

        Raises:
            BadBackendError: if the backend name is not valid.

        Returns:
            dict: API response.
        """
        if not self.check_credentials():
            return {"error": "Not credentials valid"}

        backend_type = self._check_backend(backend_name)

        if not backend_type:
            raise BadBackendError(backend_name)

        data = {'qObject': qobj_dict,
                'backend': {'name': backend_type}}

        url = get_job_url(self.config)
        job = self.req.post(url, data=json.dumps(data))

        return job

    def get_job(self, id_job, exclude_fields=None, include_fields=None):
        """Get the information about a job, by its id."""

        def build_url_filter(excluded_fields, included_fields):
            """Return a URL filter based on included and excluded fields."""
            excluded_fields = excluded_fields or []
            included_fields = included_fields or []
            fields_bool = {}

            # Build a map of fields to bool.
            for field_ in excluded_fields:
                fields_bool[field_] = False
            for field_ in included_fields:
                fields_bool[field_] = True

            if 'properties' in fields_bool:
                fields_bool['calibration'] = fields_bool.pop('properties')

            if fields_bool:
                return '&filter=' + json.dumps({'fields': fields_bool})
            return ''

        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not id_job:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        url = get_job_url(self.config)

        url += '/' + id_job

        job = self.req.get(url, params=build_url_filter(exclude_fields,
                                                        include_fields))

        if 'calibration' in job:
            job['properties'] = job.pop('calibration')

        # The "kind" field indicates the type of the job (empty for qasm jobs)
        job_type = job.get('kind', '')

        if (not job_type) and ('qasms' in job):
            # Fallback for pre-Qobj jobs.
            for qasm in job['qasms']:
                if ('result' in qasm) and ('data' in qasm['result']):
                    qasm['data'] = qasm['result']['data']
                    del qasm['result']['data']
                    for key in qasm['result']:
                        qasm['data'][key] = qasm['result'][key]
                    del qasm['result']

        return job

    def get_jobs(self, limit=10, skip=0, backend=None, only_completed=False,
                 filter=None):
        """Get the information about the user jobs."""
        # pylint: disable=redefined-builtin

        if not self.check_credentials():
            return {"error": "Not credentials valid"}

        url = get_job_url(self.config)
        url_filter = '&filter='
        query = {
            "order": "creationDate DESC",
            "limit": limit,
            "skip": skip,
            "where": {}
        }
        if filter is not None:
            query['where'] = filter
        else:
            if backend is not None:
                query['where']['backend.name'] = backend
            if only_completed:
                query['where']['status'] = ApiJobStatus.COMPLETED.value

        url_filter = url_filter + json.dumps(query)
        jobs = self.req.get(url, url_filter)
        for job in jobs:
            if 'calibration' in job:
                job['properties'] = job.pop('calibration')

        return jobs

    def get_status_job(self, id_job):
        """Get the status about a job, by its id."""
        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not id_job:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        url = get_job_url(self.config)

        url += '/' + id_job + '/status'

        status = self.req.get(url)

        return status

    def get_status_jobs(self, limit=10, skip=0, backend=None, filter=None):
        """Get the information about the user jobs."""
        # pylint: disable=redefined-builtin
        if not self.check_credentials():
            return {"error": "Not credentials valid"}

        url = get_job_url(self.config)
        url_filter = '&filter='
        query = {
            "order": "creationDate DESC",
            "limit": limit,
            "skip": skip,
            "where": {}
        }
        if filter is not None:
            query['where'] = filter
        else:
            if backend is not None:
                query['where']['backend.name'] = backend

        url += '/status'

        url_filter = url_filter + json.dumps(query)

        jobs = self.req.get(url, url_filter)

        return jobs

    def cancel_job(self, id_job):
        """Cancel the information about a job, by its id."""
        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not id_job:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        url = get_job_url(self.config)

        url += '/{}/cancel'.format(id_job)

        res = self.req.post(url)

        return res

    def job_properties(self, job_id):
        """Get the backend properties of a job."""
        if not self.check_credentials():
            raise CredentialsError('credentials invalid')

        url = get_job_url(self.config)
        url += '/{}/properties'.format(job_id)

        response = self.req.get(url)

        return response

    def backend_status(self, backend):
        """Get the status of a backend."""
        backend_type = self._check_backend(backend)
        if not backend_type:
            raise BadBackendError(backend)

        status = self.req.get('/Backends/' + backend_type + '/queue/status')
        ret = {}

        # Adjust fields according to the specs (BackendStatus).

        # 'pending_jobs' is required, and should be >= 0.
        if 'lengthQueue' in status:
            ret['pending_jobs'] = max(status['lengthQueue'], 0)
        else:
            ret['pending_jobs'] = 0

        ret['backend_name'] = backend_type
        ret['backend_version'] = status.get('backend_version', '0.0.0')
        ret['status_msg'] = status.get('status', '')
        ret['operational'] = bool(status.get('state', False))

        # Not part of the schema.
        if 'busy' in status:
            ret['dedicated'] = status['busy']

        return ret

    def backend_properties(self, backend):
        """Get the properties of a backend."""
        if not self.check_credentials():
            raise CredentialsError('credentials invalid')

        backend_type = self._check_backend(backend)

        if not backend_type:
            raise BadBackendError(backend)

        url = get_backend_properties_url(self.config, backend_type)

        ret = self.req.get(url, params="&version=1")
        if not bool(ret):
            ret = {}
        else:
            ret["backend_name"] = backend_type
        return ret

    def backend_defaults(self, backend):
        """Get the pulse defaults of a backend."""
        if not self.check_credentials():
            raise CredentialsError('credentials invalid')

        backend_name = self._check_backend(backend)

        if not backend_name:
            raise BadBackendError(backend)

        url = get_backend_defaults_url(self.config, backend_name)

        ret = self.req.get(url)
        if not bool(ret):
            ret = {}
        return ret

    def available_backends(self):
        """Get the backends available to use in the IBMQ Platform."""
        if not self.check_credentials():
            raise CredentialsError('credentials invalid')

        url = get_backends_url(self.config)

        response = self.req.get(url)
        if (response is not None) and (isinstance(response, dict)):
            return []

        return response

    def circuit_run(self, name, **kwargs):
        """Execute a Circuit.

        Args:
            name (str): name of the Circuit.
            **kwargs (dict): arguments for the Circuit.

        Returns:
            dict: json response.

        Raises:
            CredentialsError: if the user was not authenticated.
        """
        if not self.check_credentials():
            raise CredentialsError('credentials invalid')

        url = '/QCircuitApiModels'

        payload = {
            'name': name,
            'params': kwargs
        }

        response = self.req.post(url, data=json.dumps(payload))

        return response

    def circuit_job_get(self, job_id):
        """Return information about a Circuit job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job information.
        """
        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not job_id:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        # TODO: by API constraints, always use the URL without h/g/p.
        url = '/Jobs/{}'.format(job_id)

        job = self.req.get(url)

        if 'calibration' in job:
            job['properties'] = job.pop('calibration')

        if 'qObjectResult' in job:
            # If the job is using Qobj, return the qObjectResult directly,
            # which should contain a valid Result.
            return job
        elif 'qasms' in job:
            # Fallback for pre-Qobj jobs.
            for qasm in job['qasms']:
                if ('result' in qasm) and ('data' in qasm['result']):
                    qasm['data'] = qasm['result']['data']
                    del qasm['result']['data']
                    for key in qasm['result']:
                        qasm['data'][key] = qasm['result'][key]
                    del qasm['result']

        return job

    def circuit_job_status(self, job_id):
        """Return the status of a Circuits job.

        Args:
            job_id (str): the id of the job.

        Returns:
            dict: job status.
        """
        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not job_id:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        # TODO: by API constraints, always use the URL without h/g/p.
        url = '/Jobs/{}/status'.format(job_id)

        status = self.req.get(url)

        return status

    def api_version(self):
        """Get the API Version of the QX Platform."""
        response = self.req.get('/version')

        # Parse the response, making sure a dict is returned in all cases.
        if isinstance(response, str):
            response = {'new_api': False,
                        'api': response}
        elif isinstance(response, dict):
            response['new_api'] = True

        return response
