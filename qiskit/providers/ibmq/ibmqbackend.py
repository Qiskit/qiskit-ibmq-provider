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

"""Module for interfacing with an IBMQ Backend."""

import logging
import warnings

from typing import Dict, List, Union, Optional, Any
from datetime import datetime  # pylint: disable=unused-import
from marshmallow import ValidationError

from qiskit.qobj import Qobj
from qiskit.providers import BaseBackend, JobStatus, JobError
from qiskit.providers.models import (BackendStatus, BackendProperties,
                                     PulseDefaults, BackendConfiguration)

from .api import ApiError, IBMQConnector
from .api_v2.clients import BaseClient, AccountClient
from .apiconstants import ApiJobStatus
from .credentials import Credentials
from .exceptions import IBMQBackendError, IBMQBackendValueError
from .job import IBMQJob
from .utils import update_qobj_config

logger = logging.getLogger(__name__)


class IBMQBackend(BaseBackend):
    """Backend class interfacing with an IBMQ backend."""

    def __init__(
            self,
            configuration: BackendConfiguration,
            provider,
            credentials: Credentials,
            api: Union[AccountClient, IBMQConnector]
    ) -> None:
        """Initialize remote backend for IBM Quantum Experience.

        Args:
            configuration (BackendConfiguration): configuration of backend.
            provider (IBMQProvider): provider.
            credentials (Credentials): credentials.
            api (Union[AccountClient, IBMQConnector]):
                api for communicating with the Quantum Experience.
        """
        super().__init__(provider=provider, configuration=configuration)

        self._api = api
        self._credentials = credentials
        self.hub = credentials.hub
        self.group = credentials.group
        self.project = credentials.project

        # Attributes used by caching functions.
        self._properties = None
        self._defaults = None

    def run(self, qobj: Qobj, job_name: Optional[str] = None) -> IBMQJob:
        """Run a Qobj asynchronously.

        Args:
            qobj (Qobj): description of job.
            job_name (str): custom name to be assigned to the job. This job
                name can subsequently be used as a filter in the
                ``jobs()`` function call. Job names do not need to be unique.
                This parameter is ignored if IBM Q Experience v1 account is used.

        Returns:
            IBMQJob: an instance derived from BaseJob
        """
        # pylint: disable=arguments-differ

        job = IBMQJob(self, None, self._api, qobj=qobj)
        job.submit(job_name=job_name)
        return job

    def properties(
            self,
            refresh: bool = False,
            datetime: Optional[datetime] = None  # pylint: disable=redefined-outer-name
    ) -> Optional[BackendProperties]:
        """Return the online backend properties with optional filtering.

        Args:
            refresh (bool): if True, the return is via a QX API call.
                Otherwise, a cached version is returned.
            datetime (datetime.datetime): by specifying a datetime,
                this function returns an instance of the BackendProperties whose
                timestamp is closest to, but older than, the specified datetime.

        Returns:
            BackendProperties: The properties of the backend. If the backend has
                no properties to display, it returns ``None``.
        """
        # pylint: disable=arguments-differ
        if datetime:
            if not isinstance(self._api, BaseClient):
                warnings.warn('Retrieving the properties of a '
                              'backend in a specific datetime is '
                              'only available when using IBM Q v2')
                return None

            # Do not use cache for specific datetime properties.
            api_properties = self._api.backend_properties(self.name(), datetime=datetime)
            if not api_properties:
                return None
            return BackendProperties.from_dict(api_properties)

        if refresh or self._properties is None:
            api_properties = self._api.backend_properties(self.name())
            self._properties = BackendProperties.from_dict(api_properties)

        return self._properties

    def status(self) -> BackendStatus:
        """Return the online backend status.

        Returns:
            BackendStatus: The status of the backend.

        Raises:
            LookupError: If status for the backend can't be found.
            IBMQBackendError: If the status can't be formatted properly.
        """
        api_status = self._api.backend_status(self.name())

        try:
            return BackendStatus.from_dict(api_status)
        except ValidationError as ex:
            raise LookupError(
                "Couldn't get backend status: {0}".format(ex))

    def defaults(self, refresh: bool = False) -> Optional[PulseDefaults]:
        """Return the pulse defaults for the backend.

        Args:
            refresh (bool): if True, the return is via a QX API call.
                Otherwise, a cached version is returned.

        Returns:
            PulseDefaults: the pulse defaults for the backend. If the backend
                does not support defaults, it returns ``None``.
        """
        if not self.configuration().open_pulse:
            return None

        if refresh or self._defaults is None:
            api_defaults = self._api.backend_defaults(self.name())
            if api_defaults:
                self._defaults = PulseDefaults.from_dict(api_defaults)
            else:
                self._defaults = None

        return self._defaults

    def jobs(
            self,
            limit: int = 10,
            skip: int = 0,
            status: Optional[Union[JobStatus, str]] = None,
            job_name: Optional[str] = None,
            db_filter: Optional[Dict[str, Any]] = None
    ) -> List[IBMQJob]:
        """Return the jobs submitted to this backend.

        Return the jobs submitted to this backend, with optional filtering and
        pagination. Note that the API has a limit for the number of jobs
        returned in a single call, and this function might involve making
        several calls to the API. See also the `skip` parameter for more control
        over pagination.

        Note that jobs submitted with earlier versions of Qiskit
        (in particular, those that predate the Qobj format) are not included
        in the returned list.

        Args:
            limit (int): number of jobs to retrieve.
            skip (int): starting index for the job retrieval.
            status (None or qiskit.providers.JobStatus or str): only get jobs
                with this status, where status is e.g. `JobStatus.RUNNING` or
                `'RUNNING'`
            job_name (str): only get jobs with this job name.
            db_filter (dict): `loopback-based filter
                <https://loopback.io/doc/en/lb2/Querying-data.html>`_.
                This is an interface to a database ``where`` filter. Some
                examples of its usage are:

                Filter last five jobs with errors::

                   job_list = backend.jobs(limit=5, status=JobStatus.ERROR)

                Filter last five jobs with counts=1024, and counts for
                states ``00`` and ``11`` each exceeding 400::

                  cnts_filter = {'shots': 1024,
                                 'qasms.result.data.counts.00': {'gt': 400},
                                 'qasms.result.data.counts.11': {'gt': 400}}
                  job_list = backend.jobs(limit=5, db_filter=cnts_filter)

                Filter last five jobs from 30 days ago::

                   past_date = datetime.datetime.now() - datetime.timedelta(days=30)
                   date_filter = {'creationDate': {'lt': past_date.isoformat()}}
                   job_list = backend.jobs(limit=5, db_filter=date_filter)

        Returns:
            list(IBMQJob): list of IBMQJob instances

        Raises:
            IBMQBackendValueError: status keyword value unrecognized
        """
        # Build the filter for the query.
        backend_name = self.name()
        api_filter = {'backend.name': backend_name}
        if status:
            if isinstance(status, str):
                status = JobStatus[status]
            if status == JobStatus.RUNNING:
                this_filter = {'status': ApiJobStatus.RUNNING.value,
                               'infoQueue': {'exists': False}}
            elif status == JobStatus.QUEUED:
                this_filter = {'status': ApiJobStatus.RUNNING.value,
                               'infoQueue.status': 'PENDING_IN_QUEUE'}
            elif status == JobStatus.CANCELLED:
                this_filter = {'status': ApiJobStatus.CANCELLED.value}
            elif status == JobStatus.DONE:
                this_filter = {'status': ApiJobStatus.COMPLETED.value}
            elif status == JobStatus.ERROR:
                this_filter = {'status': {'regexp': '^ERROR'}}
            else:
                raise IBMQBackendValueError('unrecognized value for "status" keyword '
                                            'in job filter')
            api_filter.update(this_filter)

        if job_name:
            api_filter['name'] = job_name

        if db_filter:
            # status takes precedence over db_filter for same keys
            api_filter = {**db_filter, **api_filter}

        # Retrieve the requested number of jobs, using pagination. The API
        # might limit the number of jobs per request.
        job_responses = []
        current_page_limit = limit

        while True:
            job_page = self._api.get_status_jobs(limit=current_page_limit,
                                                 skip=skip, filter=api_filter)
            job_responses += job_page
            skip = skip + len(job_page)

            if not job_page:
                # Stop if there are no more jobs returned by the API.
                break

            if limit:
                if len(job_responses) >= limit:
                    # Stop if we have reached the limit.
                    break
                current_page_limit = limit - len(job_responses)
            else:
                current_page_limit = 0

        job_list = []
        for job_info in job_responses:
            if 'kind' not in job_info:
                # Discard pre-qobj jobs.
                break

            job_id = job_info.pop('id', "")
            try:
                job = IBMQJob(self, job_id, self._api, **job_info)
            except JobError:
                warnings.warn('Discarding job "{}" because it contains invalid data.'
                              .format(job_id))
                break

            job_list.append(job)

        return job_list

    def retrieve_job(self, job_id: str) -> IBMQJob:
        """Return a job submitted to this backend.

        Args:
            job_id (str): the job id of the job to retrieve

        Returns:
            IBMQJob: class instance

        Raises:
            IBMQBackendError: if retrieval failed
        """
        try:
            job_info = self._api.get_job(job_id)
        except ApiError as ex:
            raise IBMQBackendError('Failed to get job "{}": {}'
                                   .format(job_id, str(ex)))

        # Check for generic errors.
        if 'error' in job_info:
            raise IBMQBackendError('Failed to get job "{}": {}'
                                   .format(job_id, job_info['error']))

        # Check for jobs from a different backend.
        job_backend_name = job_info['backend']['name']
        if job_backend_name != self.name():
            warnings.warn('Job "{}" belongs to another backend than the one queried. '
                          'The query was made on backend "{}", '
                          'but the job actually belongs to backend "{}".'
                          .format(job_id, self.name(), job_backend_name))
            raise IBMQBackendError('Failed to get job "{}": '
                                   'job does not belong to backend "{}".'
                                   .format(job_id, self.name()))

        # Check for pre-qobj jobs.
        if 'kind' not in job_info:
            warnings.warn('The result of job {} is in a no longer supported format. '
                          'Please send the job using Qiskit 0.8+.'.format(job_id),
                          DeprecationWarning)
            raise IBMQBackendError('Failed to get job "{}": {}'
                                   .format(job_id, 'job in pre-qobj format'))

        # Remove keywords to be passed directly to IBMQJob
        job_info.pop('id', None)
        job_info.pop('backend', None)

        try:
            job = IBMQJob(self, job_id, self._api, **job_info)
        except JobError as err:
            raise IBMQBackendError(str(err))

        return job

    def __repr__(self) -> str:
        credentials_info = ''
        if self.hub:
            credentials_info = "hub='{}', group='{}', project='{}'".format(
                self.hub, self.group, self.project)
        return "<{}('{}') from IBMQ({})>".format(
            self.__class__.__name__, self.name(), credentials_info)


class IBMQSimulator(IBMQBackend):
    """Backend class interfacing with an IBMQ simulator."""

    def properties(
            self,
            refresh: bool = False,
            datetime: Optional[datetime] = None  # pylint: disable=redefined-outer-name
    ) -> None:
        """Return the online backend properties.

        Returns:
            None
        """
        return None

    def run(
            self,
            qobj: Qobj,
            backend_options: Optional[Dict] = None,
            noise_model=None,
            job_name: Optional[str] = None
    ) -> IBMQJob:
        """Run qobj asynchronously.

        Args:
            qobj (Qobj): description of job
            backend_options (dict): backend options
            noise_model (NoiseModel): noise model
            job_name (str): custom name to be assigned to the job

        Returns:
            IBMQJob: an instance derived from BaseJob
        """
        # pylint: disable=arguments-differ
        qobj = update_qobj_config(qobj, backend_options, noise_model)
        return super(IBMQSimulator, self).run(qobj, job_name)
