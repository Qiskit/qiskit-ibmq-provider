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

"""Module for interfacing with an IBM Quantum Experience Backend."""

import logging
import warnings

from typing import Dict, List, Union, Optional, Any
from datetime import datetime as python_datetime

from qiskit.qobj import QasmQobj, PulseQobj, validate_qobj_against_schema
from qiskit.providers.basebackend import BaseBackend  # type: ignore[attr-defined]
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.models import (BackendStatus, BackendProperties,
                                     PulseDefaults, GateConfig)
from qiskit.tools.events.pubsub import Publisher
from qiskit.providers.models import (QasmBackendConfiguration,
                                     PulseBackendConfiguration)

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import
from .apiconstants import ApiJobShareLevel, ApiJobStatus, API_JOB_FINAL_STATES
from .job.utils import api_status_to_job_status
from .api.clients import AccountClient
from .api.exceptions import ApiError
from .backendjoblimit import BackendJobLimit
from .credentials import Credentials
from .exceptions import (IBMQBackendError, IBMQBackendValueError,
                         IBMQBackendApiError, IBMQBackendApiProtocolError,
                         IBMQBackendJobLimitError)
from .job import IBMQJob
from .utils import update_qobj_config, validate_job_tags
from .utils.json_decoder import decode_pulse_defaults, decode_backend_properties

logger = logging.getLogger(__name__)


class IBMQBackend(BaseBackend):
    """Backend class interfacing with an IBM Quantum Experience device.

    You can run experiments on a backend using the :meth:`run()` method after
    assembling them into the :class:`Qobj<qiskit.qobj.Qobj>` format. The
    :meth:`run()` method returns an :class:`IBMQJob<qiskit.providers.ibmq.job.IBMQJob>`
    instance that represents the submitted job. Each job has a unique job ID, which
    can later be used to retrieve the job. An example of this flow::

        from qiskit import IBMQ, assemble, transpile
        from qiskit.circuit.random import random_circuit

        provider = IBMQ.load_account()
        backend = provider.backends.ibmq_vigo
        qx = random_circuit(n_qubits=5, depth=4)
        qobj = assemble(transpile(qx, backend=backend), backend=backend)
        job = backend.run(qobj)
        retrieved_job = backend.retrieve_job(job.job_id())

    Note:
        You should not instantiate the ``IBMQBackend`` class directly. Instead, use
        the methods provided by an :class:`AccountProvider` instance to retrieve and handle
        backends.

    Other methods return information about the backend. For example, the :meth:`status()` method
    returns a :class:`BackendStatus<qiskit.providers.models.BackendStatus>` instance.
    The instance contains the ``operational`` and ``pending_jobs`` attributes, which state whether
    the backend is operational and also the number of jobs in the server queue for the backend,
    respectively::

        status = backend.status()
        is_operational = status.operational
        jobs_in_queue = status.pending_jobs

    It is also possible to see the number of remaining jobs you are able to submit to the
    backend with the :meth:`job_limit()` method, which returns a
    :class:`BackendJobLimit<qiskit.providers.ibmq.BackendJobLimit>` instance::

        job_limit = backend.job_limit()
    """

    def __init__(
            self,
            configuration: Union[QasmBackendConfiguration, PulseBackendConfiguration],
            provider: 'accountprovider.AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> None:
        """IBMQBackend constructor.

        Args:
            configuration: Backend configuration.
            provider: IBM Quantum Experience account provider
            credentials: IBM Quantum Experience credentials.
            api: IBM Quantum Experience client used to communicate with the server.
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
            qobj: Union[QasmQobj, PulseQobj],
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None,
            validate_qobj: bool = False
    ) -> IBMQJob:
        """Run a Qobj asynchronously.

        Args:
            qobj: The Qobj to be executed.
            job_name: Custom name to be assigned to the job. This job
                name can subsequently be used as a filter in the
                :meth:`jobs()` method. Job names do not need to be unique.
            job_share_level: Allows sharing a job at the hub, group, project,
                or global level. The possible job share levels are: ``global``, ``hub``,
                ``group``, ``project``, and ``none``.

                    * global: The job is public to any user.
                    * hub: The job is shared between the users in the same hub.
                    * group: The job is shared between the users in the same group.
                    * project: The job is shared between the users in the same project.
                    * none: The job is not shared at any level.

                If the job share level is not specified, the job is not shared at any level.
            job_tags: Tags to be assigned to the jobs. The tags can subsequently be used
                as a filter in the :meth:`jobs()` function call.
            validate_qobj: If ``True``, run JSON schema validation against the
                submitted payload

        Returns:
            The job to be executed, an instance derived from BaseJob.

        Raises:
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
                valid_job_share_levels_str = ', '.join(level.value for level in ApiJobShareLevel)
                raise IBMQBackendValueError(
                    '"{}" is not a valid job share level. '
                    'Valid job share levels are: {}.'
                    .format(job_share_level, valid_job_share_levels_str)) from None
        else:
            api_job_share_level = ApiJobShareLevel.NONE

        validate_job_tags(job_tags, IBMQBackendValueError)
        if validate_qobj:
            validate_qobj_against_schema(qobj)
        return self._submit_job(qobj, job_name, api_job_share_level, job_tags)

    def _submit_job(
            self,
            qobj: Union[QasmQobj, PulseQobj],
            job_name: Optional[str] = None,
            job_share_level: Optional[ApiJobShareLevel] = None,
            job_tags: Optional[List[str]] = None
    ) -> IBMQJob:
        """Submit the Qobj to the backend.

        Args:
            qobj: The Qobj to be executed.
            job_name: Custom name to be assigned to the job. This job
                name can subsequently be used as a filter in the
                ``jobs()``method.
                Job names do not need to be unique.
            job_share_level: Level the job should be shared at.
            job_tags: Tags to be assigned to the job.

        Returns:
            The job to be executed, an instance derived from BaseJob.

        Events:
            ibmq.job.start: The job has started.

        Raises:
            IBMQBackendApiError: If an unexpected error occurred while submitting
                the job.
            IBMQBackendError: If an unexpected error occurred after submitting
                the job.
            IBMQBackendApiProtocolError: If an unexpected value is received from
                 the server.
            IBMQBackendJobLimitError: If the job could not be submitted because
                the job limit has been reached.
        """
        try:
            qobj_dict = qobj.to_dict()
            submit_info = self._api.job_submit(
                backend_name=self.name(),
                qobj_dict=qobj_dict,
                job_name=job_name,
                job_share_level=job_share_level,
                job_tags=job_tags)
        except ApiError as ex:
            if 'Error code: 3458' in str(ex):
                raise IBMQBackendJobLimitError('Error submitting job: {}'.format(str(ex))) from ex
            raise IBMQBackendApiError('Error submitting job: {}'.format(str(ex))) from ex

        # Error in the job after submission:
        # Transition to the `ERROR` final state.
        if 'error' in submit_info:
            raise IBMQBackendError(
                'Error submitting job: {}'.format(str(submit_info['error'])))

        # Submission success.
        try:
            job = IBMQJob(backend=self, api=self._api, qobj=qobj, **submit_info)
            logger.debug('Job %s was successfully submitted.', job.job_id())
        except TypeError as err:
            raise IBMQBackendApiProtocolError('Unexpected return value received from the server '
                                              'when submitting job: {}'.format(str(err))) from err
        Publisher().publish("ibmq.job.start", job)
        return job

    def properties(
            self,
            refresh: bool = False,
            datetime: Optional[python_datetime] = None
    ) -> Optional[BackendProperties]:
        """Return the backend properties, subject to optional filtering.

        Args:
            refresh: If ``True``, re-query the server for the backend properties.
                Otherwise, return a cached version.
            datetime: By specifying `datetime`, this function returns an instance
                of the :class:`BackendProperties<qiskit.providers.models.BackendProperties>`
                whose timestamp is closest to, but older than, the specified `datetime`.

        Returns:
            The backend properties or ``None`` if the backend properties are not
            currently available.
        """
        # pylint: disable=arguments-differ
        if datetime:
            # Do not use cache for specific datetime properties.
            api_properties = self._api.backend_properties(self.name(), datetime=datetime)
            if not api_properties:
                return None
            decode_backend_properties(api_properties)
            return BackendProperties.from_dict(api_properties)

        if refresh or self._properties is None:
            api_properties = self._api.backend_properties(self.name())
            decode_backend_properties(api_properties)
            self._properties = BackendProperties.from_dict(api_properties)

        return self._properties

    def status(self) -> BackendStatus:
        """Return the backend status.

        Returns:
            The status of the backend.

        Raises:
            IBMQBackendApiProtocolError: If the status for the backend cannot be formatted properly.
        """
        api_status = self._api.backend_status(self.name())

        try:
            return BackendStatus.from_dict(api_status)
        except TypeError as ex:
            raise IBMQBackendApiProtocolError(
                'Unexpected return value received from the server when '
                'getting backend status: {}'.format(str(ex))) from ex

    def defaults(self, refresh: bool = False) -> Optional[PulseDefaults]:
        """Return the pulse defaults for the backend.

        Args:
            refresh: If ``True``, re-query the server for the backend pulse defaults.
                Otherwise, return a cached version.

        Returns:
            The backend pulse defaults or ``None`` if the backend does not support pulse.
        """
        if not self.configuration().open_pulse:
            return None

        if refresh or self._defaults is None:
            api_defaults = self._api.backend_pulse_defaults(self.name())
            if api_defaults:
                decode_pulse_defaults(api_defaults)
                self._defaults = PulseDefaults.from_dict(api_defaults)
            else:
                self._defaults = None

        return self._defaults

    def job_limit(self) -> BackendJobLimit:
        """Return the job limit for the backend.

        The job limit information includes the current number of active jobs
        you have on the backend and the maximum number of active jobs you can have
        on it.

        Note:
            Job limit information for a backend is provider specific.
            For example, if you have access to the same backend via
            different providers, the job limit information might be
            different for each provider.

        If the method call was successful, you can inspect the job limit for
        the backend by accessing the ``maximum_jobs`` and ``active_jobs`` attributes
        of the :class:`BackendJobLimit<BackendJobLimit>` instance returned. For example::

            backend_job_limit = backend.job_limit()
            maximum_jobs = backend_job_limit.maximum_jobs
            active_jobs = backend_job_limit.active_jobs

        If ``maximum_jobs`` is equal to ``None``, then there is
        no limit to the maximum number of active jobs you could
        have on the backend.

        Returns:
            The job limit for the backend, with this provider.

        Raises:
            IBMQBackendApiProtocolError: If an unexpected value is received from the server.
        """
        api_job_limit = self._api.backend_job_limit(self.name())

        try:
            job_limit = BackendJobLimit(**api_job_limit)
            if job_limit.maximum_jobs == -1:
                # Manually set `maximum` to `None` if backend has no job limit.
                job_limit.maximum_jobs = None
            return job_limit
        except TypeError as ex:
            raise IBMQBackendApiProtocolError(
                'Unexpected return value received from the server when '
                'querying job limit data for the backend: {}.'.format(ex)) from ex

    def remaining_jobs_count(self) -> Optional[int]:
        """Return the number of remaining jobs that could be submitted to the backend.

        Note:
            The number of remaining jobs for a backend is provider
            specific. For example, if you have access to the same backend
            via different providers, the number of remaining jobs might
            be different for each. See :class:`BackendJobLimit<BackendJobLimit>`
            for the job limit information of a backend.

        If ``None`` is returned, there are no limits to the maximum
        number of active jobs you could have on the backend.

        Returns:
            The remaining number of jobs a user could submit to the backend, with
            this provider, before the maximum limit on active jobs is reached.

        Raises:
            IBMQBackendApiProtocolError: If an unexpected value is received from the server.
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
            descending: bool = True,
            db_filter: Optional[Dict[str, Any]] = None
    ) -> List[IBMQJob]:
        """Return the jobs submitted to this backend, subject to optional filtering.

        Retrieve jobs submitted to this backend that match the given filters
        and paginate the results if desired. Note that the server has a limit for the
        number of jobs returned in a single call. As a result, this function might involve
        making several calls to the server. See also the `skip` parameter for more control
        over pagination.

        Args:
            limit: Number of jobs to retrieve.
            skip: Starting index for the job retrieval.
            status: Only get jobs with this status or one of the statuses.
                For example, you can specify `status=JobStatus.RUNNING` or `status="RUNNING"`
                or `status=["RUNNING", "ERROR"]`
            job_name: Filter by job name. The `job_name` is matched partially
                and `regular expressions
                <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions>`_
                can be used.
            start_datetime: Filter by the given start date, in local time. This is used to
                find jobs whose creation dates are after (greater than or equal to) this
                local date/time.
            end_datetime: Filter by the given end date, in local time. This is used to
                find jobs whose creation dates are before (less than or equal to) this
                local date/time.
            job_tags: Filter by tags assigned to jobs.
            job_tags_operator: Logical operator to use when filtering by job tags. Valid
                values are "AND" and "OR":

                    * If "AND" is specified, then a job must have all of the tags
                      specified in ``job_tags`` to be included.
                    * If "OR" is specified, then a job only needs to have any
                      of the tags specified in ``job_tags`` to be included.
            descending: If ``True``, return the jobs in descending order of the job
                creation date (newest first). If ``False``, return in ascending order.
            db_filter: A `loopback-based filter
                <https://loopback.io/doc/en/lb2/Querying-data.html>`_.
                This is an interface to a database ``where`` filter. Some
                examples of its usage are:

                Filter last five jobs with errors::

                   job_list = backend.jobs(limit=5, status=JobStatus.ERROR)

                Filter last five jobs with hub name ``ibm-q``::

                  filter = {'hubInfo.hub.name': 'ibm-q'}
                  job_list = backend.jobs(limit=5, db_filter=filter)

        Returns:
            A list of jobs that match the criteria.

        Raises:
            IBMQBackendValueError: If a keyword value is not recognized.
        """
        return self._provider.backends.jobs(
            limit, skip, self.name(), status,
            job_name, start_datetime, end_datetime, job_tags, job_tags_operator,
            descending, db_filter)

    def active_jobs(self, limit: int = 10) -> List[IBMQJob]:
        """Return the unfinished jobs submitted to this backend.

        Return the jobs submitted to this backend, with this provider, that are
        currently in an unfinished job status state. The unfinished
        :class:`JobStatus<qiskit.providers.jobstatus.JobStatus>` states
        include: ``INITIALIZING``, ``VALIDATING``, ``QUEUED``, and ``RUNNING``.

        Args:
            limit: Number of jobs to retrieve.

        Returns:
            A list of the unfinished jobs for this backend on this provider.
        """
        # Get the list of api job statuses which are not a final api job status.
        active_job_states = list({api_status_to_job_status(status)
                                  for status in ApiJobStatus
                                  if status not in API_JOB_FINAL_STATES})

        return self.jobs(status=active_job_states, limit=limit)

    def retrieve_job(self, job_id: str) -> IBMQJob:
        """Return a single job submitted to this backend.

        Args:
            job_id: The ID of the job to retrieve.

        Returns:
            The job with the given ID.

        Raises:
            IBMQBackendError: If job retrieval failed.
        """
        job = self._provider.backends.retrieve_job(job_id)
        job_backend = job.backend()

        if self.name() != job_backend.name():
            warnings.warn('Job {} belongs to another backend than the one queried. '
                          'The query was made on backend {}, '
                          'but the job actually belongs to backend {}.'
                          .format(job_id, self.name(), job_backend.name()))
            raise IBMQBackendError('Failed to get job {}: '
                                   'job does not belong to backend {}.'
                                   .format(job_id, self.name()))

        return job

    def __repr__(self) -> str:
        credentials_info = ''
        if self.hub:
            credentials_info = "hub='{}', group='{}', project='{}'".format(
                self.hub, self.group, self.project)
        return "<{}('{}') from IBMQ({})>".format(
            self.__class__.__name__, self.name(), credentials_info)


class IBMQSimulator(IBMQBackend):
    """Backend class interfacing with an IBM Quantum Experience simulator."""

    def properties(
            self,
            refresh: bool = False,
            datetime: Optional[python_datetime] = None
    ) -> None:
        """Return ``None``, simulators do not have backend properties."""
        return None

    def run(
            self,
            qobj: Union[QasmQobj, PulseQobj],
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None,
            validate_qobj: bool = False,
            backend_options: Optional[Dict] = None,
            noise_model: Any = None
    ) -> IBMQJob:
        """Run a Qobj asynchronously.

        Args:
            qobj: The Qobj to be executed.
            backend_options: Backend options.
            noise_model: Noise model.
            job_name: Custom name to be assigned to the job. This job
                name can subsequently be used as a filter in the
                :meth:`jobs` method. Job names do not need to be unique.
            job_share_level: Allows sharing a job at the hub, group, project and
                global level (see :meth:`IBMQBackend.run()<IBMQBackend.run>` for more details).
            job_tags: Tags to be assigned to the jobs. The tags can subsequently be used
                as a filter in the :meth:`IBMQBackend.jobs()<IBMQBackend.jobs>` method.
            validate_qobj: If ``True``, run JSON schema validation against the
                submitted payload

        Returns:
            The job to be executed, an instance derived from ``BaseJob``.
        """
        # pylint: disable=arguments-differ
        qobj = update_qobj_config(qobj, backend_options, noise_model)
        return super(IBMQSimulator, self).run(qobj, job_name, job_share_level, job_tags,
                                              validate_qobj)


class IBMQRetiredBackend(IBMQBackend):
    """Backend class interfacing with an IBM Quantum Experience device no longer available."""

    def __init__(
            self,
            configuration: Union[QasmBackendConfiguration, PulseBackendConfiguration],
            provider: 'accountprovider.AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> None:
        """IBMQRetiredBackend constructor.

        Args:
            configuration: Backend configuration.
            provider: IBM Quantum Experience account provider
            credentials: IBM Quantum Experience credentials.
            api: IBM Quantum Experience client used to communicate with the server.
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
        """Return the backend properties."""
        return None

    def defaults(self, refresh: bool = False) -> None:
        """Return the pulse defaults for the backend."""
        return None

    def status(self) -> BackendStatus:
        """Return the backend status."""
        return self._status

    def job_limit(self) -> None:
        """Return the job limits for the backend."""
        return None

    def remaining_jobs_count(self) -> None:
        """Return the number of remaining jobs that could be submitted to the backend."""
        return None

    def active_jobs(self, limit: int = 10) -> None:
        """Return the unfinished jobs submitted to this backend."""
        return None

    def run(
            self,
            qobj: Union[QasmQobj, PulseQobj],
            job_name: Optional[str] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None,
            validate_qobj: bool = False
    ) -> None:
        """Run a Qobj."""
        raise IBMQBackendError('This backend ({}) is no longer available.'.format(self.name()))

    @classmethod
    def from_name(
            cls,
            backend_name: str,
            provider: 'accountprovider.AccountProvider',
            credentials: Credentials,
            api: AccountClient
    ) -> 'IBMQRetiredBackend':
        """Return a retired backend from its name."""
        configuration = QasmBackendConfiguration(
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
