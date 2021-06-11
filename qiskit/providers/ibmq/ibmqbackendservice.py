# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
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
import warnings
import copy
from functools import wraps

from typing import Dict, List, Callable, Optional, Any, Union
from datetime import datetime

from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.exceptions import QiskitBackendNotFoundError
from qiskit.providers.providerutils import filter_backends
from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .api.exceptions import ApiError
from .apiconstants import ApiJobStatus
from .exceptions import (IBMQBackendValueError, IBMQBackendApiError, IBMQBackendApiProtocolError)
from .ibmqbackend import IBMQBackend, IBMQRetiredBackend
from .backendreservation import BackendReservation
from .job import IBMQJob
from .utils.utils import to_python_identifier, validate_job_tags, filter_data
from .utils.converters import local_to_utc
from .utils.backend import convert_reservation_data

logger = logging.getLogger(__name__)


class IBMQBackendService:
    """Backend namespace for an IBM Quantum Experience account provider.

    Represent a namespace that provides backend related services for the IBM
    Quantum Experience backends available to this provider. An instance of
    this class is used as a callable attribute to the :class:`AccountProvider`
    class. This allows a convenient way to query for all backends or to access
    a specific backend::

        backends = provider.backends()  # Invoke backends() to get the backends.
        sim_backend = provider.backend.ibmq_qasm_simulator  # Get a specific backend instance.

    Also, you are able to retrieve jobs from a provider without specifying the backend name.
    For example, to retrieve the ten most recent jobs you have submitted, regardless of the
    backend they were submitted to, you could do::

        most_recent_jobs = provider.backend.jobs(limit=10)

    It is also possible to retrieve a single job without specifying the backend name::

        job = provider.backend.retrieve_job(<JOB_ID>)
    """

    def __init__(self, provider: 'accountprovider.AccountProvider') -> None:
        """IBMQBackendService constructor.

        Args:
            provider: IBM Quantum Experience account provider.
        """
        super().__init__()

        self._provider = provider
        self._discover_backends()

    def _discover_backends(self) -> None:
        """Discovers the remote backends for this provider, if not already known."""
        for backend in self._provider._backends.values():
            backend_name = to_python_identifier(backend.name())

            # Append _ if duplicate
            while backend_name in self.__dict__:
                backend_name += '_'

            setattr(self, backend_name, backend)

    def backends(
            self,
            name: Optional[str] = None,
            filters: Optional[Callable[[List[IBMQBackend]], bool]] = None,
            timeout: Optional[float] = None,
            min_num_qubits: Optional[int] = None,
            input_allowed: Optional[Union[str, List[str]]] = None,
            **kwargs: Any
    ) -> List[IBMQBackend]:
        """Return all backends accessible via this provider, subject to optional filtering.

        Args:
            name: Backend name to filter by.
            filters: More complex filters, such as lambda functions.
                For example::

                    AccountProvider.backends(
                        filters=lambda b: b.configuration().quantum_volume > 16)
            timeout: Maximum number of seconds to wait for the discovery of
                remote backends.
            min_num_qubits: Minimum number of qubits the backend has to have.
            input_allowed: Filter by the types of input the backend supports.
                Valid input types are ``job`` (circuit job) and ``runtime`` (Qiskit Runtime).
                For example, ``inputs_allowed='runtime'`` will return all backends
                that support Qiskit Runtime. If a list is given, the backend must
                support all types specified in the list.
            kwargs: Simple filters that specify a ``True``/``False`` criteria in the
                backend configuration, backends status, or provider credentials.
                An example to get the operational backends with 5 qubits::

                    AccountProvider.backends(n_qubits=5, operational=True)

        Returns:
            The list of available backends that match the filter.
        """
        if timeout:
            warnings.warn("The `timeout` keyword argument is deprecated and will "
                          "be removed in a future release.",
                          DeprecationWarning, stacklevel=2)

        backends = list(self._provider._backends.values())

        # Special handling of the `name` parameter, to support alias
        # resolution.
        if name:
            aliases = self._aliased_backend_names()
            aliases.update(self._deprecated_backend_names())
            name = aliases.get(name, name)
            kwargs['backend_name'] = name

        if min_num_qubits:
            backends = list(filter(
                lambda b: b.configuration().n_qubits >= min_num_qubits, backends))

        if input_allowed:
            if not isinstance(input_allowed, list):
                input_allowed = [input_allowed]
            backends = list(filter(
                lambda b: set(input_allowed) <= set(b.configuration().input_allowed), backends))

        return filter_backends(backends, filters=filters, **kwargs)

    def jobs(
            self,
            limit: int = 10,
            skip: int = 0,
            backend_name: Optional[str] = None,
            status: Optional[Union[JobStatus, str, List[Union[JobStatus, str]]]] = None,
            job_name: Optional[str] = None,
            start_datetime: Optional[datetime] = None,
            end_datetime: Optional[datetime] = None,
            job_tags: Optional[List[str]] = None,
            job_tags_operator: Optional[str] = "OR",
            experiment_id: Optional[str] = None,
            descending: bool = True,
            db_filter: Optional[Dict[str, Any]] = None
    ) -> List[IBMQJob]:
        """Return a list of jobs, subject to optional filtering.

        Retrieve jobs that match the given filters and paginate the results
        if desired. Note that the server has a limit for the number of jobs
        returned in a single call. As a result, this function might involve
        making several calls to the server.

        Args:
            limit: Number of jobs to retrieve.
            skip: Starting index for the job retrieval.
            backend_name: Name of the backend to retrieve jobs from.
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
            experiment_id: Filter by job experiment ID.
            descending: If ``True``, return the jobs in descending order of the job
                creation date (i.e. newest first) until the limit is reached.
            db_filter: A `loopback-based filter
                <https://loopback.io/doc/en/lb2/Querying-data.html>`_.
                This is an interface to a database ``where`` filter.
                Some examples of its usage are:

                Filter last five jobs with errors::

                   job_list = backend.jobs(limit=5, status=JobStatus.ERROR)

                Filter last five jobs with hub name ``ibm-q``::

                  filter = {'hubInfo.hub.name': 'ibm-q'}
                  job_list = backend.jobs(limit=5, db_filter=filter)

        Returns:
            A list of ``IBMQJob`` instances.

        Raises:
            IBMQBackendValueError: If a keyword value is not recognized.
            TypeError: If the input `start_datetime` or `end_datetime` parameter value
                is not valid.
        """
        # Build the filter for the query.
        api_filter = {}  # type: Dict[str, Any]

        if backend_name:
            api_filter['backend.name'] = backend_name

        if status:
            status_filter = self._get_status_db_filter(status)
            api_filter.update(status_filter)

        if job_name:
            api_filter['name'] = {"regexp": job_name}

        if start_datetime or end_datetime:
            api_filter['creationDate'] = self._update_creation_date_filter(
                cur_dt_filter={},
                gte_dt=local_to_utc(start_datetime).isoformat() if start_datetime else None,
                lte_dt=local_to_utc(end_datetime).isoformat() if end_datetime else None)

        if job_tags:
            validate_job_tags(job_tags, IBMQBackendValueError)
            job_tags_operator = job_tags_operator.upper()
            if job_tags_operator == "OR":
                api_filter['tags'] = {'inq': job_tags}
            elif job_tags_operator == "AND":
                and_tags = []
                for tag in job_tags:
                    and_tags.append({'tags': tag})
                api_filter['and'] = and_tags
            else:
                raise IBMQBackendValueError(
                    '"{}" is not a valid job_tags_operator value. '
                    'Valid values are "AND" and "OR"'.format(job_tags_operator))

        if experiment_id:
            api_filter['experimentTag'] = experiment_id

        if db_filter:
            # Rather than overriding the logical operators `and`/`or`, first
            # check to see if the `api_filter` query should be extended with the
            # `api_filter` query for the same keys instead.
            self._merge_logical_filters(api_filter, db_filter)

            # Argument filters takes precedence over db_filter for same keys
            api_filter = {**db_filter, **api_filter}

        # Retrieve the requested number of jobs, using pagination. The server
        # might limit the number of jobs per request.
        job_responses = []  # type: List[Dict[str, Any]]
        current_page_limit = limit or 20
        initial_filter = copy.deepcopy(api_filter)

        while True:
            job_page = self._provider._api_client.list_jobs_statuses(
                limit=current_page_limit, skip=skip, descending=descending,
                extra_filter=api_filter)
            if logger.getEffectiveLevel() is logging.DEBUG:
                filtered_data = [filter_data(job) for job in job_page]
                logger.debug("jobs() response data is %s", filtered_data)
            job_responses += job_page

            if not job_page:
                # Stop if there are no more jobs returned by the server.
                break

            if limit:
                if len(job_responses) >= limit:
                    # Stop if we have reached the limit.
                    break
                current_page_limit = limit - len(job_responses)
            else:
                current_page_limit = 20

            # Use the last received job for pagination.
            skip = 0
            last_job = job_page[-1]
            api_filter = copy.deepcopy(initial_filter)
            cur_dt_filter = api_filter.pop('creationDate', {})
            if descending:
                new_dt_filter = self._update_creation_date_filter(
                    cur_dt_filter=cur_dt_filter, lte_dt=last_job['creation_date'])
            else:
                new_dt_filter = self._update_creation_date_filter(
                    cur_dt_filter=cur_dt_filter, gte_dt=last_job['creation_date'])
            if not cur_dt_filter:
                api_filter['creationDate'] = new_dt_filter
            else:
                self._merge_logical_filters(
                    api_filter, {'and': [{'creationDate': new_dt_filter}, cur_dt_filter]})

            if 'id' not in api_filter:
                api_filter['id'] = {'nin': [last_job['job_id']]}
            else:
                new_id_filter = {'and': [{'id': {'nin': [last_job['job_id']]}},
                                         {'id': api_filter.pop('id')}]}
                self._merge_logical_filters(api_filter, new_id_filter)

        job_list = []
        for job_info in job_responses:
            job_id = job_info.get('job_id', "")
            # Recreate the backend used for this job.
            backend_name = job_info.get('_backend_info', {}).get('name', 'unknown')
            try:
                backend = self._provider.get_backend(backend_name)
            except QiskitBackendNotFoundError:
                backend = IBMQRetiredBackend.from_name(backend_name,
                                                       self._provider,
                                                       self._provider.credentials,
                                                       self._provider._api_client)
            try:
                job = IBMQJob(backend=backend, api_client=self._provider._api_client, **job_info)
            except TypeError:
                logger.warning('Discarding job "%s" because it contains invalid data.', job_id)
                continue

            job_list.append(job)

        return job_list

    def _merge_logical_filters(self, cur_filter: Dict, new_filter: Dict) -> None:
        """Merge the logical operators in the input filters.

        Args:
            cur_filter: Current filter.
            new_filter: New filter to be merged into ``cur_filter``.

        Returns:
            ``cur_filter`` with ``new_filter``'s logical operators merged into it.
        """
        logical_operators_to_expand = ['or', 'and']
        for key in logical_operators_to_expand:
            if key in new_filter:
                if key in cur_filter:
                    cur_filter[key].extend(new_filter[key])
                else:
                    cur_filter[key] = new_filter[key]

    def _update_creation_date_filter(
            self,
            cur_dt_filter: Dict[str, Any],
            gte_dt: Optional[str] = None,
            lte_dt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use the new start and end datetime in the creation date filter.

        Args:
            cur_dt_filter: Current creation date filter.
            gte_dt: New start datetime.
            lte_dt: New end datetime.

        Returns:
            Updated creation date filter.
        """
        if not gte_dt:
            gt_list = [cur_dt_filter.pop(gt_op) for gt_op in ['gt', 'gte']
                       if gt_op in cur_dt_filter]
            if 'between' in cur_dt_filter and len(cur_dt_filter['between']) > 0:
                gt_list.append(cur_dt_filter.pop('between')[0])
            gte_dt = max(gt_list) if gt_list else None
        if not lte_dt:
            lt_list = [cur_dt_filter.pop(lt_op) for lt_op in ['lt', 'lte']
                       if lt_op in cur_dt_filter]
            if 'between' in cur_dt_filter and len(cur_dt_filter['between']) > 1:
                lt_list.append(cur_dt_filter.pop('between')[1])
            lte_dt = min(lt_list) if lt_list else None

        new_dt_filter = {}  # type: Dict[str, Union[str, List[str]]]
        if gte_dt and lte_dt:
            new_dt_filter['between'] = [gte_dt, lte_dt]
        elif gte_dt:
            new_dt_filter['gte'] = gte_dt
        elif lte_dt:
            new_dt_filter['lte'] = lte_dt

        return new_dt_filter

    def _get_status_db_filter(
            self,
            status_arg: Union[JobStatus, str, List[Union[JobStatus, str]]]
    ) -> Dict[str, Any]:
        """Return the db filter to use when retrieving jobs based on a status or statuses.

        Returns:
            The status db filter used to query the api when retrieving jobs that match
            a given status or list of statuses.

        Raises:
            IBMQBackendError: If a status value is not recognized.
        """
        _final_status_filter = None
        if isinstance(status_arg, list):
            _final_status_filter = {'or': []}
            for status in status_arg:
                status_filter = self._get_status_filter(status)
                _final_status_filter['or'].append(status_filter)
        else:
            status_filter = self._get_status_filter(status_arg)
            _final_status_filter = status_filter

        return _final_status_filter

    def _get_status_filter(self, status: Union[JobStatus, str]) -> Dict[str, Any]:
        """Return the db filter to use when retrieving jobs based on a status.

        Returns:
            The status db filter used to query the api when retrieving jobs
            that match a given status.

        Raises:
            IBMQBackendValueError: If the status value is not recognized.
        """
        if isinstance(status, str):
            try:
                status = JobStatus[status.upper()]
            except KeyError:
                raise IBMQBackendValueError(
                    '"{}" is not a valid status value. Valid values are {}'.format(
                        status, ", ".join(job_status.name for job_status in JobStatus))) \
                    from None

        _status_filter = {}  # type: Dict[str, Any]
        if status == JobStatus.INITIALIZING:
            _status_filter = {'status': {
                'inq': [ApiJobStatus.CREATING.value, ApiJobStatus.CREATED.value]
            }}
        elif status == JobStatus.VALIDATING:
            _status_filter = {'status': {
                'inq': [ApiJobStatus.VALIDATING.value, ApiJobStatus.VALIDATED.value]
            }}
        elif status == JobStatus.RUNNING:
            _status_filter = {'status': ApiJobStatus.RUNNING.value}
        elif status == JobStatus.QUEUED:
            _status_filter = {'status': ApiJobStatus.QUEUED.value}
        elif status == JobStatus.CANCELLED:
            _status_filter = {'status': ApiJobStatus.CANCELLED.value}
        elif status == JobStatus.DONE:
            _status_filter = {'status': ApiJobStatus.COMPLETED.value}
        elif status == JobStatus.ERROR:
            _status_filter = {'status': {'regexp': '^ERROR'}}
        else:
            raise IBMQBackendValueError(
                '"{}" is not a valid status value. Valid values are {}'.format(
                    status, ", ".join(job_status.name for job_status in JobStatus)))

        return _status_filter

    def retrieve_job(self, job_id: str) -> IBMQJob:
        """Return a single job.

        Args:
            job_id: The ID of the job to retrieve.

        Returns:
            The job with the given id.

        Raises:
            IBMQBackendApiError: If an unexpected error occurred when retrieving
                the job.
            IBMQBackendApiProtocolError: If unexpected return value received
                 from the server.
        """
        try:
            job_info = self._provider._api_client.job_get(job_id)
        except ApiError as ex:
            raise IBMQBackendApiError('Failed to get job {}: {}'
                                      .format(job_id, str(ex))) from ex

        # Recreate the backend used for this job.
        backend_name = job_info.get('_backend_info', {}).get('name', 'unknown')
        try:
            backend = self._provider.get_backend(backend_name)
        except QiskitBackendNotFoundError:
            backend = IBMQRetiredBackend.from_name(backend_name,
                                                   self._provider,
                                                   self._provider.credentials,
                                                   self._provider._api_client)
        try:
            job = IBMQJob(backend=backend, api_client=self._provider._api_client, **job_info)
        except TypeError as ex:
            raise IBMQBackendApiProtocolError(
                'Unexpected return value received from the server '
                'when retrieving job {}: {}'.format(job_id, str(ex))) from ex

        return job

    def my_reservations(self) -> List[BackendReservation]:
        """Return your upcoming reservations.

        Returns:
            A list of your upcoming reservations.
        """
        raw_response = self._provider._api_client.my_reservations()
        return convert_reservation_data(raw_response)

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


def _issue_warning(func):  # type: ignore
    @wraps(func)
    def _wrapper(self, *args, **kwargs):  # type: ignore
        if not self._backends_warning_issued:
            warnings.warn("The `backends` attribute is deprecated. "
                          "Please use `provider.backend` (singular) instead.",
                          DeprecationWarning, stacklevel=2)
            self._backends_warning_issued = True
        return func(self, *args, **kwargs)
    return _wrapper


class IBMQDeprecatedBackendService:

    # pylint: disable=W,C,R

    def __init__(self, backend_service: IBMQBackendService):
        self._backend_service = backend_service
        self._backends_warning_issued = False

    @_issue_warning
    def jobs(self, *args, **kwargs):  # type: ignore
        return self._backend_service.jobs(*args, **kwargs)

    @_issue_warning
    def retrieve_job(self, *args, **kwargs):  # type: ignore
        return self._backend_service.retrieve_job(*args, **kwargs)

    @_issue_warning
    def my_reservations(self, *args, **kwargs):  # type: ignore
        return self._backend_service.my_reservations(*args, **kwargs)

    def __getattribute__(self, item):  # type: ignore
        if item in ['_backend_service', '_backends_warning_issued']:
            return super().__getattribute__(item)

        if not self._backends_warning_issued:
            warnings.warn("The `backends` provider attribute is deprecated. "
                          "Please use `provider.backend` (singular) instead. "
                          "You can continue to use `provider.backends()` to "
                          "retrieve all backends.",
                          DeprecationWarning, stacklevel=2)
            self._backends_warning_issued = True

        return self._backend_service.__getattribute__(item)

    def __call__(self, *args, **kwargs):  # type: ignore
        return self._backend_service.backends(*args, **kwargs)
