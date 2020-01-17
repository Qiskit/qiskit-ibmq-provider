# -*- coding: utf-8 -*-

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

"""Job manager used to manage jobs for IBM Q Experience."""

import logging
from typing import List, Optional, Union, Any
from concurrent import futures

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule
from qiskit.providers.ibmq.apiconstants import ApiJobShareLevel
from qiskit.providers.ibmq.utils import validate_job_tags
from qiskit.providers.ibmq.accountprovider import AccountProvider

from .exceptions import IBMQJobManagerInvalidStateError
from .utils import format_job_details, format_status_counts
from .managedjobset import ManagedJobSet
from ..ibmqbackend import IBMQBackend

logger = logging.getLogger(__name__)


class IBMQJobManager:
    """Job manager for IBM Quantum Experience.

    The Job Manager is a higher level mechanism for handling jobs composed of
    multiple circuits or pulse schedules. It splits the experiments into
    multiple jobs based on backend restrictions. When the jobs are finished,
    it collects and presents the results in a unified view.

    To use the Job Manager to submit multiple experiments, invoking the
    ``run()`` method::

        from qiskit.providers.ibmq.managed import IBMQJobManager
        job_manager = IBMQJobManager()
        job_set_foo = job_manager.run(circs, backend=backend, name='foo')

    The ``run()`` method returns a ``ManagedJobSet`` instance, which
    represents the set of jobs for the experiments. You can use the
    ``ManagedJobSet`` methods, such as ``statuses()``, ``results()``, and
    ``error_messages()`` to get a combined view of the jobs in the set.
    For example::

        results = job_set_foo.results()
        results.get_counts(5)  # Counts for experiment 5.

    The ``job_set_id()`` method of ``ManagedJobSet`` returns the job set ID,
    which can be used to retrieve the job set later::

        job_set_id = job_set_foo.job_set_id()
        retrieved_foo = job_manager.retrieve_job_set(job_set_id=job_set_id, provider=provider)
    """

    def __init__(self) -> None:
        """Creates a new IBMQJobManager instance."""
        self._job_sets = []  # type: List[ManagedJobSet]
        self._executor = futures.ThreadPoolExecutor()

    def run(
            self,
            experiments: Union[List[QuantumCircuit], List[Schedule]],
            backend: IBMQBackend,
            name: Optional[str] = None,
            max_experiments_per_job: Optional[int] = None,
            job_share_level: Optional[str] = None,
            job_tags: Optional[List[str]] = None,
            **run_config: Any
    ) -> ManagedJobSet:
        """Execute a set of circuits or pulse schedules on a backend.

        The circuits or schedules will be split into multiple jobs. Circuits
        or schedules in a job will be executed together in each shot.

        Args:
            experiments: Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            name: Name for this set of jobs. Each job within the set will have
                a job name that consists of the set name followed by a suffix.
                Default: current datetime.
            max_experiments_per_job: Maximum number of experiments to run in each job.
                If not specified, the default is to use the maximum allowed by
                the backend.
                If the specified value is greater the maximum allowed by the
                backend, the default is used.
            job_share_level: Allows sharing the jobs at the hub/group/project and
                global level. The possible job share levels are: "global", "hub",
                "group", "project", and "none". Default: "none".
            job_tags: tags to be assigned to the job. The tags can
                subsequently be used as a filter in the ``jobs()`` function call.
                Default: None.
            run_config: Configuration of the runtime environment. Some
                examples of these configuration parameters include:
                ``qobj_id``, ``qobj_header``, ``shots``, ``memory``,
                ``seed_simulator``, ``qubit_lo_freq``, ``meas_lo_freq``,
                ``qubit_lo_range``, ``meas_lo_range``, ``schedule_los``,
                ``meas_level``, ``meas_return``, ``meas_map``,
                ``memory_slot_size``, ``rep_time``, and ``parameter_binds``.

                Refer to the documentation on ``qiskit.compiler.assemble()``
                for details on these arguments.

        Returns:
            Managed job set.

        Raises:
            IBMQJobManagerInvalidStateError: If an input parameter value is not valid.
        """
        if (any(isinstance(exp, Schedule) for exp in experiments) and
                not backend.configuration().open_pulse):
            raise IBMQJobManagerInvalidStateError(
                "Pulse schedules found, but the backend does not support pulse schedules.")

        # Validate job share level
        if job_share_level:
            try:
                api_job_share_level = ApiJobShareLevel(job_share_level.lower())
            except ValueError:
                raise IBMQJobManagerInvalidStateError(
                    '"{}" is not a valid job share level. Valid job share levels are: {}'.format(
                        job_share_level, ', '.join(level.value for level in ApiJobShareLevel)))
        else:
            api_job_share_level = ApiJobShareLevel.NONE

        validate_job_tags(job_tags, IBMQJobManagerInvalidStateError)

        experiment_list = self._split_experiments(
            experiments, backend=backend, max_experiments_per_job=max_experiments_per_job)

        job_set = ManagedJobSet(name=name)
        job_set.run(experiment_list, backend=backend, executor=self._executor,
                    job_share_level=api_job_share_level, job_tags=job_tags, **run_config)
        self._job_sets.append(job_set)

        return job_set

    def _split_experiments(
            self,
            experiments: Union[List[QuantumCircuit], List[Schedule]],
            backend: IBMQBackend,
            max_experiments_per_job: Optional[int] = None
    ) -> List[Union[List[QuantumCircuit], List[Schedule]]]:
        """Split a list of experiments into sublists.

        Args:
            experiments: Experiments to be split.
            backend: Backend to execute the experiments on.
            max_experiments_per_job: Maximum number of experiments to run in each job.

        Returns:
            A list of sublists of experiments.
        """
        if hasattr(backend.configuration(), 'max_experiments'):
            backend_max = backend.configuration().max_experiments
            chunk_size = backend_max if max_experiments_per_job is None \
                else min(backend_max, max_experiments_per_job)
        elif max_experiments_per_job:
            chunk_size = max_experiments_per_job
        else:
            return [experiments]

        return [experiments[x:x + chunk_size] for x in range(0, len(experiments), chunk_size)]

    def report(self, detailed: bool = True) -> str:
        """Return a report on the statuses of all jobs managed by this manager.

        Args:
            detailed: True if a detailed report is be returned. False
                if a summary report is to be returned.

        Returns:
            A report on job statuses.
        """
        job_set_statuses = [job_set.statuses() for job_set in self._job_sets]
        flat_status_list = [stat for stat_list in job_set_statuses for stat in stat_list]

        report = ["Summary report:"]
        report.extend(format_status_counts(flat_status_list))

        if detailed:
            report.append("\nDetail report:")
            for i, job_set in enumerate(self._job_sets):
                report.append(("  Job set name: {}, ID: {}".format(
                    job_set.name(), job_set.job_set_id())))
                report.extend(format_job_details(
                    job_set_statuses[i], job_set.managed_jobs()))

        return '\n'.join(report)

    def job_sets(self, name: Optional[str] = None) -> List[ManagedJobSet]:
        """Returns a list of managed job sets matching the specified filtering
            in this session.

        Args:
             name: Name of the managed job sets.

        Returns:
            A list of managed job sets.
        """
        if name:
            return [job_set for job_set in self._job_sets if job_set.name() == name]

        return self._job_sets

    def retrieve_job_set(
            self,
            job_set_id: str,
            provider: AccountProvider,
            refresh: bool = False
    ) -> ManagedJobSet:
        """Retrieve a previously submitted job set.

        Args:
            job_set_id: ID of the job set.
            provider: Provider used for this job set.
            refresh: If True, re-query the API for the job set.
                Otherwise return the cached value. Default: False.

        Returns:
            Retrieved job set.

        Raises:
            IBMQJobManagerUnknownJobSet: If the job set cannot be found.
            IBMQJobManagerInvalidStateError: If jobs for this job set are
                found but have unexpected attributes.
        """
        for index, mjs in enumerate(self._job_sets):
            if mjs.job_set_id() == job_set_id:
                if not refresh:
                    return mjs
                del self._job_sets[index]
                break

        new_job_set = ManagedJobSet(short_id=job_set_id)
        new_job_set.retrieve_jobs(provider=provider)
        self._job_sets.append(new_job_set)
        return new_job_set
