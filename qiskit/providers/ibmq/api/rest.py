# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Rest clients for accessing IBM Q."""
from functools import wraps
import json


class RestClient:

    URL_MAP = {}

    def __init__(self, session, prefix_url=''):
        self.session = session
        self.prefix_url = prefix_url

    def get_url(self, identifier):
        return '{}{}'.format(self.prefix_url, self.URL_MAP[identifier])


class AuthClient(RestClient):

    URL_MAP = {
        'login': '/users/loginWithToken',
        'user_info': '/users/me',
    }

    def login(self, api_token):
        url = self.get_url('login')
        return self.session.post(url, json={'apiToken': api_token}).json()

    def user_info(self):
        url = self.get_url('user_info')
        response = self.session.get(url).json()

        # Revise the URL.
        try:
            api_url = response['urls']['http']
            if api_url.endswith('.com?private=true'):
                response['urls']['http'] = '{}/api'.format(
                    api_url.split('?')[0])
        except KeyError:
            pass

        return response


class ApiClient(RestClient):

    URL_MAP = {
        'backends': '/Backends/v/1',
        'hubs': '/Network',
        'jobs': '/Jobs',
        'jobs_status': '/Jobs/status'
    }

    def backend(self, backend_name):
        return BackendClient(self.session, backend_name)

    def job(self, job_id):
        return JobClient(self.session, job_id)

    def backends(self):
        url = self.get_url('backends')
        return self.session.get(url).json()

    def hubs(self):
        url = self.get_url('hubs')
        return self.session.get(url).json()

    def jobs(self, limit=10, skip=0, extra_filter=None):
        url = self.get_url('jobs_status')

        query = {
            'order': 'creationDate DESC',
            'limit': limit,
            'skip': skip,
        }
        if extra_filter:
            query['where'] = extra_filter

        return self.session.get(
            url, params={'filter': json.dumps(query) if query else None}).json()

    def run_job(self, job_payload):
        url = self.get_url('jobs')
        return self.session.post(url, json=job_payload).json()


class BackendClient(RestClient):

    URL_MAP = {
        'status': '/queue/status',
        'properties': '/properties'
    }

    def __init__(self, session, backend_name):
        self.backend_name = backend_name
        super().__init__(session, '/Backends/{}'.format(backend_name))

    def status(self):
        url = self.get_url('status')
        response = self.session.get(url).json()

        # Adjust fields according to the specs (BackendStatus).
        ret = {
            'backend_name': self.backend_name,
            'backend_version': response.get('backend_version', '0.0.0'),
            'status_msg': response.get('status', ''),
            'operational': bool(response.get('state', False))
        }

        # 'pending_jobs' is required, and should be >= 0.
        if 'lengthQueue' in response:
            ret['pending_jobs'] = max(response['lengthQueue'], 0)
        else:
            ret['pending_jobs'] = 0

        # Not part of the schema.
        if 'busy' in response:
            ret['dedicated'] = response['busy']

        return ret

    def properties(self):
        url = self.get_url('properties')
        response = self.session.get(url, params={'version': 1}).json()

        # Adjust name of the backend.
        if response:
            response['backend_name'] = self.backend_name

        return response


class JobClient(RestClient):

    URL_MAP = {
        'cancel': 'cancel',
        'self': '',
        'status': '/status'
    }

    def __init__(self, session, job_id):
        self.job_id = job_id
        super().__init__(session, '/Jobs/{}'.format(job_id))

    def get(self, excluded_fields, included_fields):
        url = self.get_url('self')
        query = build_url_filter(excluded_fields, included_fields)

        return self.session.get(
            url, params={'filter': json.dumps(query) if query else None}).json()

    def cancel(self):
        url = self.get_url('cancel')
        return self.session.post(url).json()

    def status(self):
        url = self.get_url('status')
        return self.session.get(url).json()


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


def with_url(url_string):
    def _outer_wrapper(func):
        @wraps(func)
        def _wrapper(self, *args, **kwargs):
            kwargs.update({'url': url_string})
            return func(self, *args, **kwargs)
        return _wrapper
    return _outer_wrapper
