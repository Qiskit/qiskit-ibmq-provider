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

import logging
from typing import Dict, List, Callable, Optional, Any, Union
from types import SimpleNamespace
from datetime import datetime

from qiskit.providers import JobStatus, QiskitBackendNotFoundError  # type: ignore[attr-defined]
from qiskit.providers.providerutils import filter_backends
from qiskit.validation.exceptions import ModelValidationError
from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .api.exceptions import ApiError
from .apiconstants import ApiJobStatus
from .exceptions import IBMQBackendError, IBMQBackendValueError
from .ibmqbackend import IBMQBackend, IBMQRetiredBackend
from .job import IBMQJob
from .utils import to_python_identifier

logger = logging.getLogger(__name__)


class IBMQBackendService(SimpleNamespace):
    """Backend namespace for an IBM Quantum Experience account provider."""

    def __init__(self, provider: 'accountprovider.AccountProvider') -> None:
        """Creates a new IBMQBackendService instance.

        Args:
            provider: IBM Q Experience account provider
        """
        super().__init__()

        self._provider = provider
        self._discover_backends()

    def _discover_backends(self) -> None:
        """Discovers the remote backends if not already known."""
        for backend in self._provider._backends.values():
            backend_name = to_python_identifier(backend.name())

            # Append _ if duplicate
            while backend_name in self.__dict__:
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
            name: backend name to filter by
            filters: more complex filters, such as lambda functions
                e.g. AccountProvider.backends(
                    filters=lambda b: b.configuration['n_qubits'] > 5)
            timeout: number of seconds to wait for backend discovery.
            kwargs: simple filters specifying a true/false criteria in the
                backend configuration or backend status or provider credentials
                e.g. AccountProvider.backends(n_qubits=5, operational=True)

        Returns:
            list of backends available that match the filter
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
            start_datetime: Optional[datetime] = None,
            end_datetime: Optional[datetime] = None,
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
            limit: number of jobs to retrieve.
            skip: starting index for the job retrieval.
            backend_name: name of the backend.
            status: only get jobs with this status, where status is e.g.
                `JobStatus.RUNNING` or `'RUNNING'`
            job_name: filter by job name. The `job_name` is matched partially
                and `regular expressions
                <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions>
                `_ can be used.
            start_datetime: filter by start date. This is used to find jobs
                whose creation dates are after (greater than) this date/time.
            end_datetime: filter by end date. This is used to find jobs
                whose creation dates are before (less than) this date/time.
            db_filter: `loopback-based filter
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
            list of IBMQJob instances

        Raises:
            IBMQBackendValueError: status keyword value unrecognized
        """
        # Build the filter for the query.
        api_filter = {}  # type: Dict[str, Any]

        if backend_name:
            api_filter['backend.name'] = backend_name

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
            api_filter['name'] = {"regexp": job_name}

        # Create the date query according to the parameters specified.
        if start_datetime or end_datetime:
            date_filter = {'creationDate': {}}  # type: ignore[var-annotated]
            if start_datetime:
                date_filter['creationDate'].update({'gt': start_datetime.isoformat()})
            if end_datetime:
                date_filter['creationDate'].update({'lt': end_datetime.isoformat()})

            api_filter.update(date_filter)

        if db_filter:
            # status takes precedence over db_filter for same keys
            api_filter = {**db_filter, **api_filter}

        # Retrieve the requested number of jobs, using pagination. The API
        # might limit the number of jobs per request.
        job_responses = []  # type: List[Dict[str, Any]]
        current_page_limit = limit

        while True:
            job_page = self._provider._api.list_jobs_statuses(
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
            job_id = job_info.get('id', "")
            # Recreate the backend used for this job.
            backend_name = job_info.get('backend', {}).get('name', 'unknown')
            try:
                backend = self._provider.get_backend(backend_name)
            except QiskitBackendNotFoundError:
                backend = IBMQRetiredBackend.from_name(backend_name,
                                                       self._provider,
                                                       self._provider.credentials,
                                                       self._provider._api)

            job_info.update({
                '_backend': backend,
                'api': self._provider._api,
            })
            try:
                job = IBMQJob.from_dict(job_info)
            except ModelValidationError:
                logger.warning('Discarding job "%s" because it contains invalid data.', job_id)
                continue

            job_list.append(job)

        return job_list

    def retrieve_job(self, job_id: str) -> IBMQJob:
        """Return a single job from the API.

        Args:
            job_id: the job id of the job to retrieve

        Returns:
            class instance

        Raises:
            IBMQBackendError: if retrieval failed
        """
        try:
            job_info = self._provider._api.job_get(job_id)
        except ApiError as ex:
            raise IBMQBackendError('Failed to get job "{}": {}'
                                   .format(job_id, str(ex)))

        # Recreate the backend used for this job.
        backend_name = job_info.get('backend', {}).get('name', 'unknown')
        try:
            backend = self._provider.get_backend(backend_name)
        except QiskitBackendNotFoundError:
            backend = IBMQRetiredBackend.from_name(backend_name,
                                                   self._provider,
                                                   self._provider.credentials,
                                                   self._provider._api)

        job_info.update({
            '_backend': backend,
            'api': self._provider._api
        })
        try:
            job = IBMQJob.from_dict(job_info)
        except ModelValidationError as ex:
            raise IBMQBackendError('Failed to get job "{}". Invalid job data received: {}'
                                   .format(job_id, str(ex)))

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
