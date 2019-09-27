# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Backend namespace for an IBM Quantum Experience account provider."""

import re
import keyword
import warnings
from typing import Dict, List, Callable, Optional, Any, Union
from types import SimpleNamespace

from qiskit.providers import JobStatus
from qiskit.providers.providerutils import filter_backends

from .api.exceptions import ApiError
from .apiconstants import ApiJobStatus, ApiJobKind
from .exceptions import IBMQBackendError, IBMQBackendValueError
from .ibmqbackend import IBMQBackend
from .job import IBMQJob


class ProviderBackends(SimpleNamespace):
    """Backend namespace for an IBM Quantum Experience account provider."""

    def __init__(self, provider: 'AccountProvider') -> None:
        """Creates a new ProviderBackends instance.

        Args:
            provider (AccountProvider): IBM Q Experience account provider
        """
        super().__init__()

        self._provider = provider
        self._discover_backends()

    def _discover_backends(self) -> None:
        """Discovers the remote backends if not already known."""
        # Python identifiers can only contain alphanumeric characters
        # and underscores and cannot start with a digit.
        pattern = re.compile(r"\W|^(?=\d)", re.ASCII)
        for backend in self._provider._backends.values():
            backend_name = backend.name()

            # Make it a valid identifier
            if not backend_name.isidentifier():
                backend_name = re.sub(pattern, '_', backend_name)

            # Append _ if is keyword or duplicate
            while keyword.iskeyword(backend_name) or backend_name in self.__dict__:
                backend_name += '_'

            setattr(self, backend_name, backend)

    def __call__(
            self,
            name: Optional[str] = None,
            filters: Optional[Callable[[List[IBMQBackend]], bool]] = None,
            timeout: Optional[float] = None,
            **kwargs: Any
    ) -> List[IBMQBackend]:
        """Return all backends accessible via this provider, subject to optional filtering.

        Args:
            name (str): backend name to filter by
            filters (callable): more complex filters, such as lambda functions
                e.g. AccountProvider.backends(
                    filters=lambda b: b.configuration['n_qubits'] > 5)
            timeout (float or None): number of seconds to wait for backend discovery.
            kwargs: simple filters specifying a true/false criteria in the
                backend configuration or backend status or provider credentials
                e.g. AccountProvider.backends(n_qubits=5, operational=True)

        Returns:
            list[IBMQBackend]: list of backends available that match the filter
        """
        backends = self._provider._backends.values()

        # Special handling of the `name` parameter, to support alias
        # resolution.
        if name:
            aliases = self._aliased_backend_names()
            aliases.update(self._deprecated_backend_names())
            name = aliases.get(name, name)
            kwargs['backend_name'] = name

        return filter_backends(backends, filters=filters, **kwargs)

    def jobs(
            self,
            limit: int = 10,
            skip: int = 0,
            backend_name: Optional[str] = None,
            status: Optional[Union[JobStatus, str]] = None,
            job_name: Optional[str] = None,
            db_filter: Optional[Dict[str, Any]] = None
    ) -> List[IBMQJob]:
        """Return a list of jobs from the API.

        Return a list of jobs, with optional filtering and pagination. Note
        that the API has a limit for the number of jobs returned in a single
        call, and this function might involve making several calls to the API.
        See also the `skip` parameter for more control over pagination.

        Note that jobs submitted with earlier versions of Qiskit
        (in particular, those that predate the Qobj format) are not included
        in the returned list.

        Args:
            limit (int): number of jobs to retrieve.
            skip (int): starting index for the job retrieval.
            backend_name (str): name of the backend.
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
        api_filter = {}

        if backend_name:
            api_filter['backend_name'] = backend_name

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
            job_page = self.provider._api.list_jobs_statuses(
                limit=current_page_limit, skip=skip, extra_filter=api_filter)
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
            kwargs = {}
            try:
                job_kind = ApiJobKind(job_info.get('kind', None))
            except ValueError:
                # Discard pre-qobj jobs.
                break

            kwargs['use_websockets'] = True
            if job_kind == ApiJobKind.QOBJECT_STORAGE:
                kwargs['use_object_storage'] = True

            job = IBMQJob(self, job_info.get('id'), self.provider._api,
                          creation_date=job_info.get('creationDate'),
                          api_status=job_info.get('status'),
                          **kwargs)
            job_list.append(job)

        return job_list

    def retrieve_job(self, job_id: str) -> IBMQJob:
        """Return a single job from the API.

        Args:
            job_id (str): the job id of the job to retrieve

        Returns:
            IBMQJob: class instance

        Raises:
            IBMQBackendError: if retrieval failed
        """
        try:
            job_info = self.provider._api.job_get(job_id)

            # Check for generic errors.
            if 'error' in job_info:
                raise IBMQBackendError('Failed to get job "{}": {}'
                                       .format(job_id, job_info['error']))

            # Check for pre-qobj jobs.
            kwargs = {}
            try:
                job_kind = ApiJobKind(job_info.get('kind', None))

                kwargs['use_websockets'] = True
                if job_kind == ApiJobKind.QOBJECT_STORAGE:
                    kwargs['use_object_storage'] = True

            except ValueError:
                warnings.warn('The result of job {} is in a no longer supported format. '
                              'Please send the job using Qiskit 0.8+.'.format(job_id),
                              DeprecationWarning)
                raise IBMQBackendError('Failed to get job "{}": {}'
                                       .format(job_id, 'job in pre-qobj format'))
        except ApiError as ex:
            raise IBMQBackendError('Failed to get job "{}": {}'
                                   .format(job_id, str(ex)))

        job = IBMQJob(self, job_info.get('id'), self.provider._api,
                      creation_date=job_info.get('creationDate'),
                      api_status=job_info.get('status'),
                      **kwargs)

        return job

    @staticmethod
    def _deprecated_backend_names() -> Dict[str, str]:
        """Returns deprecated backend names."""
        return {
            'ibmqx_qasm_simulator': 'ibmq_qasm_simulator',
            'ibmqx_hpc_qasm_simulator': 'ibmq_qasm_simulator',
            'real': 'ibmqx1'
            }

    @staticmethod
    def _aliased_backend_names() -> Dict[str, str]:
        """Returns aliased backend names."""
        return {
            'ibmq_5_yorktown': 'ibmqx2',
            'ibmq_5_tenerife': 'ibmqx4',
            'ibmq_16_rueschlikon': 'ibmqx5',
            'ibmq_20_austin': 'QS1_1'
            }
