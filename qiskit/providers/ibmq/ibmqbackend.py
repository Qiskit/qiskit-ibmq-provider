# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
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
from qiskit.providers import BaseBackend, JobStatus
from qiskit.providers.models import (BackendStatus, BackendProperties,
                                     PulseDefaults, BackendConfiguration, GateConfig)
from qiskit.validation.exceptions import ModelValidationError
from qiskit.tools.events.pubsub import Publisher

from .api.clients import AccountClient
from .api.exceptions import ApiError
from .credentials import Credentials
from .exceptions import IBMQBackendError
from .job import IBMQJob
from .utils import update_qobj_config

logger = logging.getLogger(__name__)


class IBMQBackend(BaseBackend):
    """Backend class interfacing with an IBMQ backend."""

    def __init__(
            self,
            configuration: BackendConfiguration,
            provider: 'AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> None:
        """Initialize remote backend for IBM Quantum Experience.

        Args:
            configuration (BackendConfiguration): configuration of backend.
            provider (AccountProvider): provider.
            credentials (Credentials): credentials.
            api (AccountClient):
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

        Returns:
            IBMQJob: an instance derived from BaseJob

        Raises:
            SchemaValidationError: If the job validation fails.
            IBMQBackendError: If an unexpected error occurred while submitting
                the job.
        """
        # pylint: disable=arguments-differ

        validate_qobj_against_schema(qobj)
        return self._submit_job(qobj, job_name)

    def _submit_job(self, qobj: Qobj, job_name: Optional[str] = None) -> IBMQJob:
        """Submit qobj job to IBM-Q.
        Args:
            qobj (Qobj): description of job.
            job_name (str): custom name to be assigned to the job. This job
                name can subsequently be used as a filter in the
                ``jobs()`` function call. Job names do not need to be unique.

        Returns:
            IBMQJob: an instance derived from BaseJob

        Events:
            ibmq.job.start: The job has started.

        Raises:
            IBMQBackendError: If an unexpected error occurred while submitting
                the job.
        """
        try:
            qobj_dict = qobj.to_dict()
            submit_info = self._api.job_submit(
                backend_name=self.name(),
                qobj_dict=qobj_dict,
                use_object_storage=getattr(self.configuration(), 'allow_object_storage', False),
                job_name=job_name)
        except ApiError as ex:
            raise IBMQBackendError('Error submitting job: {}'.format(str(ex)))

        # Error in the job after submission:
        # Transition to the `ERROR` final state.
        if 'error' in submit_info:
            raise IBMQBackendError('Error submitting job: {}'.format(str(submit_info['error'])))

        # Submission success.
        submit_info.update({
            '_backend': self,
            'api': self._api,
            'qObject': qobj_dict
        })
        try:
            job = IBMQJob.from_dict(submit_info)
        except ModelValidationError as err:
            raise IBMQBackendError('Unexpected return value from the server when '
                                   'submitting job: {}'.format(str(err)))
        Publisher().publish("ibmq.job.start", job)
        return job

    def properties(
            self,
            refresh: bool = False,
            datetime: Optional[python_datetime] = None
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
            api_defaults = self._api.backend_pulse_defaults(self.name())
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
        warnings.warn('backend.jobs() is deprecated and will be removed after '
                      '0.5. Please use provider.backends.jobs(backend_name='
                      '"{}") instead.'.format(self.name()), DeprecationWarning)

        return self._provider.backends.jobs(
            limit, skip, self.name(), status, job_name, db_filter)

    def retrieve_job(self, job_id: str) -> IBMQJob:
        """Return a job submitted to this backend.

        Args:
            job_id (str): the job id of the job to retrieve

        Returns:
            IBMQJob: class instance

        Raises:
            IBMQBackendError: if retrieval failed
        """
        warnings.warn('backend.retrieve_job() is deprecated and will be removed'
                      'after 0.5. Please use provider.backends.retrieve_job()'
                      'instead.', DeprecationWarning)
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
            backend_options: Optional[Dict] = None,
            noise_model: Any = None,
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


class IBMQRetiredBackend(IBMQBackend):
    """Backend class interfacing with an IBMQ device that is no longer available."""

    def __init__(
            self,
            configuration: BackendConfiguration,
            provider: 'AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> None:
        """Initialize remote backend for IBM Quantum Experience.

        Args:
            configuration (BackendConfiguration): configuration of backend.
            provider (AccountProvider): provider.
            credentials (Credentials): credentials.
            api (AccountClient):
                api for communicating with the Quantum Experience.
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

    def run(self, qobj: Qobj, job_name: Optional[str] = None) -> None:
        """Run a Qobj."""
        raise IBMQBackendError('This backend is no longer available.')

    @classmethod
    def from_name(
            cls,
            backend_name: str,
            provider: 'AccountProvider',
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
