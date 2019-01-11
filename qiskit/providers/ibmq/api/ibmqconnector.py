# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""IBM Q API connector."""

import json
import logging

from .exceptions import CredentialsError, BadBackendError
from .utils import Request

logger = logging.getLogger(__name__)


def get_job_url(config, hub=None, group=None, project=None):
    """Return the URL for a job."""
    hub = config.get('hub', hub)
    group = config.get('group', group)
    project = config.get('project', project)

    if hub and group and project:
        return '/Network/{}/Groups/{}/Projects/{}/jobs'.format(hub, group,
                                                               project)
    return '/Jobs'


def get_backend_properties_url(config, backend_type, hub=None):
    """Return the URL for a backend's properties."""
    hub = config.get('hub', hub)

    if hub:
        return '/Network/{}/devices/{}/properties'.format(hub, backend_type)
    return '/Backends/{}/properties'.format(backend_type)


def get_backends_url(config, hub, group, project):
    """Return the URL for a backend."""
    hub = config.get('hub', hub)
    group = config.get('group', group)
    project = config.get('project', project)

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
            url_parsed = self.config['url'].split('/api')
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
        backend_name = backend_name.lower()

        # Check for new-style backends
        backends = self.available_backends()
        for backend_ in backends:
            if backend_.get('backend_name', '') == backend_name:
                return backend_name
        # backend unrecognized
        return None

    def check_credentials(self):
        """Check if the user has permission in QX platform."""
        return bool(self.req.credential.get_token())

    def run_job(self, job, backend, shots=1,
                max_credits=None, seed=None, hub=None, group=None,
                project=None, hpc=None, access_token=None, user_id=None):
        """Execute a job."""
        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            return {"error": "Not credentials valid"}

        backend_type = self._check_backend(backend)

        if not backend_type:
            raise BadBackendError(backend)

        if isinstance(job, (list, tuple)):
            qasms = job
            for qasm in qasms:
                qasm['qasm'] = qasm['qasm'].replace('IBMQASM 2.0;', '')
                qasm['qasm'] = qasm['qasm'].replace('OPENQASM 2.0;', '')

            data = {'qasms': qasms,
                    'shots': shots,
                    'backend': {}}

            if max_credits:
                data['maxCredits'] = max_credits

            if seed and len(str(seed)) < 11 and str(seed).isdigit():
                data['seed'] = seed
            elif seed:
                return {"error": "Not seed allowed. Max 10 digits."}

            data['backend']['name'] = backend_type
        elif isinstance(job, dict):
            q_obj = job
            data = {'qObject': q_obj,
                    'backend': {}}

            data['backend']['name'] = backend_type
        else:
            return {"error": "Not a valid data to send"}

        if hpc:
            data['hpc'] = hpc

        url = get_job_url(self.config, hub, group, project)

        job = self.req.post(url, data=json.dumps(data))

        return job

    def get_job(self, id_job, hub=None, group=None, project=None,
                exclude_fields=None, include_fields=None,
                access_token=None, user_id=None):
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

        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not id_job:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        url = get_job_url(self.config, hub, group, project)

        url += '/' + id_job

        job = self.req.get(url, params=build_url_filter(exclude_fields,
                                                        include_fields))

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

    def get_jobs(self, limit=10, skip=0, backend=None, only_completed=False,
                 filter=None, hub=None, group=None, project=None,
                 access_token=None, user_id=None):
        """Get the information about the user jobs."""
        # pylint: disable=redefined-builtin

        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            return {"error": "Not credentials valid"}

        url = get_job_url(self.config, hub, group, project)
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
                query['where']['status'] = 'COMPLETED'

        url_filter = url_filter + json.dumps(query)
        jobs = self.req.get(url, url_filter)
        for job in jobs:
            if 'calibration' in job:
                job['properties'] = job.pop('calibration')

        return jobs

    def get_status_job(self, id_job, hub=None, group=None, project=None,
                       access_token=None, user_id=None):
        """Get the status about a job, by its id."""
        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not id_job:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        url = get_job_url(self.config, hub, group, project)

        url += '/' + id_job + '/status'

        status = self.req.get(url)

        return status

    def get_status_jobs(self, limit=10, skip=0, backend=None, filter=None,
                        hub=None, group=None, project=None, access_token=None,
                        user_id=None):
        """Get the information about the user jobs."""
        # pylint: disable=redefined-builtin

        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            return {"error": "Not credentials valid"}

        url = get_job_url(self.config, hub, group, project)
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

    def cancel_job(self, id_job, hub=None, group=None, project=None,
                   access_token=None, user_id=None):
        """Cancel the information about a job, by its id."""
        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            return {'status': 'Error',
                    'error': 'Not credentials valid'}
        if not id_job:
            return {'status': 'Error',
                    'error': 'Job ID not specified'}

        url = get_job_url(self.config, hub, group, project)

        url += '/{}/cancel'.format(id_job)

        res = self.req.post(url)

        return res

    def backend_status(self, backend, access_token=None, user_id=None):
        """Get the status of a chip."""
        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        backend_type = self._check_backend(backend)
        if not backend_type:
            raise BadBackendError(backend)

        status = self.req.get('/Backends/' + backend_type + '/queue/status',
                              with_token=False)
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

    def backend_properties(self, backend, hub=None, access_token=None,
                           user_id=None):
        """Get the parameters of calibration of a real chip."""
        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            raise CredentialsError('credentials invalid')

        backend_type = self._check_backend(backend)

        if not backend_type:
            raise BadBackendError(backend)

        url = get_backend_properties_url(self.config, backend_type, hub)

        ret = self.req.get(url, params="&version=1")
        if not bool(ret):
            ret = {}
        else:
            ret["backend_name"] = backend_type
        return ret

    def available_backends(self, hub=None, group=None, project=None,
                           access_token=None, user_id=None):
        """Get the backends available to use in the QX Platform."""
        if access_token:
            self.req.credential.set_token(access_token)
        if user_id:
            self.req.credential.set_user_id(user_id)
        if not self.check_credentials():
            raise CredentialsError('credentials invalid')

        url = get_backends_url(self.config, hub, group, project)

        response = self.req.get(url)
        if (response is not None) and (isinstance(response, dict)):
            return []

        return response

    def api_version(self):
        """Get the API Version of the QX Platform."""
        return self.req.get('/version')
