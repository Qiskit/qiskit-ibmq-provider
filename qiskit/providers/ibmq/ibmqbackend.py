# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2020.
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
from datetime import datetime as python_datetime
from marshmallow import ValidationError

from qiskit.qobj import Qobj, validate_qobj_against_schema
from qiskit.providers.basebackend import BaseBackend  # type: ignore[attr-defined]
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.models import (BackendStatus, BackendProperties,
                                     PulseDefaults, BackendConfiguration, GateConfig)
from qiskit.validation.exceptions import ModelValidationError
from qiskit.tools.events.pubsub import Publisher

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import
from .apiconstants import ApiJobShareLevel, ApiJobStatus, API_JOB_FINAL_STATES
from .job.utils import api_status_to_job_status
from .api.clients import AccountClient
from .api.exceptions import ApiError
from .backendjoblimit import BackendJobLimit
from .credentials import Credentials
from .exceptions import (IBMQBackendError, IBMQBackendValueError,
                         IBMQBackendApiError, IBMQBackendApiProtocolError)
from .job import IBMQJob
from .utils import update_qobj_config, validate_job_tags

logger = logging.getLogger(__name__)


class IBMQBackend(BaseBackend):
    """Backend class interfacing with an IBMQ backend."""

    def __init__(
            self,
            configuration: BackendConfiguration,
            provider: 'accountprovider.AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> None:
        """Initialize remote backend for IBM Quantum Experience.

        Args:
            configuration: configuration of backend.
            provider: provider.
            credentials: credentials.
            api: api for communicating with the Quantum Experience.
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

    def run(
            self,
            qobj: Qobj,
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None
    ) -> IBMQJob:
        """Run a Qobj asynchronously.

        Args:
            qobj: description of job.
            job_name: custom name to be assigned to the job. This job
                name can subsequently be used as a filter in the
                ``jobs()`` function call. Job names do not need to be unique.
                Default: None.
            job_share_level: allows sharing a job at the hub/group/project and
                global level. The possible job share levels are: "global", "hub",
                "group", "project", and "none".

                    * global: the job is public to any user.
                    * hub: the job is shared between the users in the same hub.
                    * group: the job is shared between the users in the same group.
                    * project: the job is shared between the users in the same project.
                    * none: the job is not shared at any level.

                If the job share level is not specified, then the job is not shared at any level.
            job_tags: tags to be assigned to the job. The tags can
                subsequently be used as a filter in the ``jobs()`` function call.
                Default: None.

        Returns:
            an instance derived from BaseJob

        Raises:
            SchemaValidationError: If the job validation fails.
            IBMQBackendApiError: If an unexpected error occurred while submitting
                the job.
            IBMQBackendApiProtocolError: If an unexpected value received from
                 the server.
            IBMQBackendValueError: If an input parameter value is not valid.
        """
        # pylint: disable=arguments-differ
        if job_share_level:
            try:
                api_job_share_level = ApiJobShareLevel(job_share_level.lower())
            except ValueError:
                raise IBMQBackendValueError(
                    '"{}" is not a valid job share level. '
                    'Valid job share levels are: {}'
                    .format(job_share_level, ', '.join(level.value for level in ApiJobShareLevel)))
        else:
            api_job_share_level = ApiJobShareLevel.NONE

        validate_job_tags(job_tags, IBMQBackendValueError)
        validate_qobj_against_schema(qobj)
        return self._submit_job(qobj, job_name, api_job_share_level, job_tags)

    def _submit_job(
            self,
            qobj: Qobj,
            job_name: Optional[str] = None,
            job_share_level: Optional[ApiJobShareLevel] = None,
            job_tags: Optional[List[str]] = None
    ) -> IBMQJob:
        """Submit qobj job to IBM-Q.
        Args:
            qobj: description of job.
            job_name: custom name to be assigned to the job. This job
                name can subsequently be used as a filter in the
                ``jobs()`` function call. Job names do not need to be unique.
            job_share_level: level the job should be shared at.
            job_tags: tags to be assigned to the job.

        Returns:
            an instance derived from BaseJob

        Events:
            ibmq.job.start: The job has started.

        Raises:
            IBMQBackendApiError: If an unexpected error occurred while submitting
                the job.
            IBMQBackendError: If an unexpected error occurred after submitting
                the job.
            IBMQBackendApiProtocolError: If an unexpected value received from
                 the server.
        """
        try:
            qobj_dict = qobj.to_dict()
            submit_info = self._api.job_submit(
                backend_name=self.name(),
                qobj_dict=qobj_dict,
                use_object_storage=getattr(self.configuration(), 'allow_object_storage', False),
                job_name=job_name,
                job_share_level=job_share_level,
                job_tags=job_tags)
        except ApiError as ex:
            raise IBMQBackendApiError('Error submitting job: {}'.format(str(ex)))

        # Error in the job after submission:
        # Transition to the `ERROR` final state.
        if 'error' in submit_info:
            raise IBMQBackendError(
                'Error submitting job: {}'.format(str(submit_info['error'])))

        # Submission success.
        submit_info.update({
            '_backend': self,
            'api': self._api,
            'qObject': qobj_dict
        })
        try:
            job = IBMQJob.from_dict(submit_info)
        except ModelValidationError as err:
            raise IBMQBackendApiProtocolError('Unexpected return value from the server '
                                              'when submitting job: {}'.format(str(err)))
        Publisher().publish("ibmq.job.start", job)
        return job

    def properties(
            self,
            refresh: bool = False,
            datetime: Optional[python_datetime] = None
    ) -> Optional[BackendProperties]:
        """Return the online backend properties with optional filtering.

        Args:
            refresh: if True, the return is via a QX API call.
                Otherwise, a cached version is returned.
            datetime: by specifying a datetime,
                this function returns an instance of the BackendProperties whose
                timestamp is closest to, but older than, the specified datetime.

        Returns:
            The properties of the backend. If the backend has no properties to
            display, it returns ``None``.
        """
        # pylint: disable=arguments-differ
        if datetime:
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
            The status of the backend.

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
            refresh: if True, the return is via a QX API call.
                Otherwise, a cached version is returned.

        Returns:
            the pulse defaults for the backend. If the backend does not support
            defaults, it returns ``None``.
        """
        if not self.configuration().open_pulse:
            return None

        if refresh or self._defaults is None:
            api_defaults = self._api.backend_pulse_defaults(self.name())
            if api_defaults:
                self._defaults = PulseDefaults.from_dict(api_defaults)
            else:
                self._defaults = None

        return self._defaults

    def job_limit(self) -> BackendJobLimit:
        """Return the job limit for the backend.

        The job limit information for this backend includes the current
        number of active jobs you have and the maximum number of active
        jobs you can have.

        Note:
            The job limit information for the backend is provider specific.
            For example, if you have access to the same backend via
            different providers, the job limit information might be
            different for each provider.

            If the method call was successful, you can inspect the job
            limit for the backend by accessing the ``maximum_jobs``
            and ``active_jobs`` attributes of the ``BackendJobLimit``
            instance returned.

            For example:
                backend_job_limit = backend.job_limit()
                maximum_jobs = backend_job_limit.maximum_jobs
                active_jobs = backend_job_limit.active_jobs

            * If ``maximum_jobs`` is equal to ``None``, then there are
                no limits to the maximum number of active jobs a
                user could have on the backend at any given time.

        Returns:
            the job limit for the backend with this provider.

        Raises:
            IBMQBackendApiProtocolError: If an unexpected value received from the server.
        """
        api_job_limit = self._api.backend_job_limit(self.name())

        try:
            job_limit = BackendJobLimit.from_dict(api_job_limit)
            if job_limit.maximum_jobs == -1:
                # Manually set `maximum` to `None` if backend has no job limit.
                job_limit.maximum_jobs = None
            return job_limit
        except ValidationError as ex:
            raise IBMQBackendApiProtocolError(
                'Unexpected return value from the server when '
                'querying job limit data for the backend: {}.'.format(ex))

    def remaining_jobs_count(self) -> Optional[int]:
        """Return the number of remaining jobs that could be submitted to the backend.

        Return the number of jobs that can be submitted to this backend
        with this provider before the maximum limit on active jobs is reached.

        Note:
            The number of remaining jobs for the backend is provider
            specific. For example, if you have access to the same backend
            via different providers, the number of remaining jobs might
            be different. See ``IBMQBackend.job_limit()`` for the job
            limit information of the backend.

            * If ``None`` is returned, then there are no limits to the maximum
                number of active jobs a user could have on the backend at any
                given time.

        Returns:
            Remaining number of jobs a user could submit to the backend
            with this provider before the maximum limit on active jobs is reached.

        Raises:
            IBMQBackendApiProtocolError: If an unexpected value received from the server.
        """
        job_limit = self.job_limit()

        if job_limit.maximum_jobs is None:
            return None

        return job_limit.maximum_jobs - job_limit.active_jobs

    def jobs(
            self,
            limit: int = 10,
            skip: int = 0,
            status: Optional[Union[JobStatus, str, List[Union[JobStatus, str]]]] = None,
            job_name: Optional[str] = None,
            start_datetime: Optional[python_datetime] = None,
            end_datetime: Optional[python_datetime] = None,
            job_tags: Optional[List[str]] = None,
            job_tags_operator: Optional[str] = "OR",
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
            limit: number of jobs to retrieve.
            skip: starting index for the job retrieval.
            status: only get jobs with this status or one of the statuses. Default: None.
                For example, you can specify `status=JobStatus.RUNNING` or `status="RUNNING"`
                    or `status=["RUNNING", "ERROR"]
            job_name: filter by job name. The `job_name` is matched partially
                and `regular expressions
                <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions>`_
                can be used.
            start_datetime: filter by start date. This is used to find jobs
                whose creation dates are after (greater than or equal to) this date/time.
            end_datetime: filter by end date. This is used to find jobs
                whose creation dates are before (less than or equal to) this date/time.
            job_tags: filter by tags assigned to jobs. Default: None.
            job_tags_operator: logical operator to use when filtering by job tags.
                Valid values are "AND" and "OR":
                 * If "AND" is specified, then a job must have all of the tags
                    specified in ``job_tags`` to be included.
                * If "OR" is specified, then a job only needs to have any
                    of the tags specified in ``job_tags`` to be included.
                Default: OR.
            db_filter: `loopback-based filter
                <https://loopback.io/doc/en/lb2/Querying-data.html>`_.
                This is an interface to a database ``where`` filter. Some
                examples of its usage are:

                Filter last five jobs with errors::

                   job_list = backend.jobs(limit=5, status=JobStatus.ERROR)

                Filter last five jobs with hub name ``ibm-q``::

                  filter = {'hubInfo.hub.name': 'ibm-q'}
                  job_list = backend.jobs(limit=5, db_filter=filter)

        Returns:
            list of IBMQJob instances

        Raises:
            IBMQBackendValueError: if a keyword value is not recognized.
        """
        return self._provider.backends.jobs(
            limit, skip, self.name(), status,
            job_name, start_datetime, end_datetime, job_tags, job_tags_operator, db_filter)

    def active_jobs(self, limit: int = 10) -> List[IBMQJob]:
        """Return the current, unfinished jobs submitted to this backend.

        Return the jobs submitted to this backend with this provider that are
        currently in an unfinished status, including: "INITIALIZING", "VALIDATING",
        "QUEUED", and "RUNNING".

        Args:
            limit: number of jobs to retrieve. Default: 10.

        Returns:
            a list of the current unfinished jobs for this backend on this provider.
        """
        # Get the list of api job statuses which are not a final api job status.
        active_job_states = list({api_status_to_job_status(status)
                                  for status in ApiJobStatus
                                  if status not in API_JOB_FINAL_STATES})

        return self.jobs(status=active_job_states, limit=limit)

    def retrieve_job(self, job_id: str) -> IBMQJob:
        """Return a job submitted to this backend.

        Args:
            job_id: the job id of the job to retrieve

        Returns:
            class instance

        Raises:
            IBMQBackendError: if retrieval failed
        """
        job = self._provider.backends.retrieve_job(job_id)
        job_backend = job.backend()

        if self.name() != job_backend.name():
            warnings.warn('Job "{}" belongs to another backend than the one queried. '
                          'The query was made on backend "{}", '
                          'but the job actually belongs to backend "{}".'
                          .format(job_id, self.name(), job_backend.name()))
            raise IBMQBackendError('Failed to get job "{}": '
                                   'job does not belong to backend "{}".'
                                   .format(job_id, self.name()))

        return self._provider.backends.retrieve_job(job_id)

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
            datetime: Optional[python_datetime] = None
    ) -> None:
        """Return the online backend properties.

        Returns:
            None
        """
        return None

    def run(
            self,
            qobj: Qobj,
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None,
            backend_options: Optional[Dict] = None,
            noise_model: Any = None
    ) -> IBMQJob:
        """Run qobj asynchronously.

        Args:
            qobj: description of job
            backend_options: backend options
            noise_model: noise model
            job_name: custom name to be assigned to the job
            job_share_level: allows sharing a job at the hub/group/project and
                global level (see `IBMQBackend.run()` for more details).
            job_tags: tags to be assigned to the job. The tags can
                subsequently be used as a filter in the ``jobs()`` function call.
                Default: None.

        Returns:
            an instance derived from BaseJob
        """
        # pylint: disable=arguments-differ
        qobj = update_qobj_config(qobj, backend_options, noise_model)
        return super(IBMQSimulator, self).run(qobj, job_name, job_share_level, job_tags)


class IBMQRetiredBackend(IBMQBackend):
    """Backend class interfacing with an IBMQ device that is no longer available."""

    def __init__(
            self,
            configuration: BackendConfiguration,
            provider: 'accountprovider.AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> None:
        """Initialize remote backend for IBM Quantum Experience.

        Args:
            configuration: configuration of backend.
            provider: provider.
            credentials: credentials.
            api: api for communicating with the Quantum Experience.
        """
        super().__init__(configuration, provider, credentials, api)
        self._status = BackendStatus(
            backend_name=self.name(),
            backend_version=self.configuration().backend_version,
            operational=False,
            pending_jobs=0,
            status_msg='This backend is no longer available.')

    def properties(
            self,
            refresh: bool = False,
            datetime: Optional[python_datetime] = None
    ) -> None:
        """Return the online backend properties."""
        return None

    def defaults(self, refresh: bool = False) -> None:
        """Return the pulse defaults for the backend."""
        return None

    def status(self) -> BackendStatus:
        """Return the online backend status."""
        return self._status

    def job_limit(self) -> None:
        """Return the job limits for the backend."""
        return None

    def remaining_jobs_count(self) -> None:
        """Return the number of remaining jobs that could be submitted to the backend."""
        return None

    def active_jobs(self, limit: int = 10) -> None:
        """Return the current, unfinished jobs submitted to this backend."""
        return None

    def run(
            self,
            qobj: Qobj,
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None
    ) -> None:
        """Run a Qobj."""
        raise IBMQBackendError('This backend is no longer available.')

    @classmethod
    def from_name(
            cls,
            backend_name: str,
            provider: 'accountprovider.AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> 'IBMQRetiredBackend':
        """Return a retired backend from its name."""
        configuration = BackendConfiguration(
            backend_name=backend_name,
            backend_version='0.0.0',
            n_qubits=1,
            basis_gates=[],
            simulator=False,
            local=False,
            conditional=False,
            open_pulse=False,
            memory=False,
            max_shots=1,
            gates=[GateConfig(name='TODO', parameters=[], qasm_def='TODO')],
            coupling_map=[[0, 1]],
        )
        return cls(configuration, provider, credentials, api)
