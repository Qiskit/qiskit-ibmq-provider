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

"""Job manager used to manage jobs for IBM Q Experience."""

import logging
from typing import List, Optional, Union
from concurrent import futures

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import ScheduleComponent, Schedule
from qiskit.compiler import transpile

from .exceptions import IBMQJobManagerInvalidStateError
from .utils import format_job_details, format_status_counts
from .managedjobset import ManagedJobSet, RetrievedManagedJobSet
from ..ibmqbackend import IBMQBackend
from ..accountprovider import AccountProvider

logger = logging.getLogger(__name__)


class IBMQJobManager:
    """Job manager for IBM Q Experience."""

    def __init__(self) -> None:
        """Creates a new IBMQJobManager instance."""
        self._job_sets = []  # type: List[ManagedJobSet]
        self._executor = futures.ThreadPoolExecutor()

    def run(
            self,
            experiments: Union[List[QuantumCircuit], List[Schedule]],
            backend: IBMQBackend,
            name: Optional[str] = None,
            shots: int = 1024,
            skip_transpile: bool = False,
            max_experiments_per_job: Optional[int] = None
    ) -> ManagedJobSet:
        """Execute a set of circuits or pulse schedules on a backend.

        The circuits or schedules will be split into multiple jobs. Circuits
        or schedules in a job will be executed together in each shot.

        The circuits will first be transpiled before submitted, using the
        default transpiler settings. Specify ``skip_transpiler=True`` if you
        want to skip this step.

        Args:
            experiments : Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            name: Name for this set of jobs. Each job in this set will have the
                job name of this name followed by an underscore (_) followed by
                the job index.
            shots: Number of repetitions of each experiment, for sampling. Default: 1024.
            skip_transpile: True if transpilation is to be skipped, otherwise False.
            max_experiments_per_job: Maximum number of experiments to run in each job.
                If not specified, the default is to use the maximum allowed by
                the backend.
                If the specified value is greater the maximum allowed by the
                backend, the default is used.

        Returns:
            Managed job set.

        Raises:
            IBMQJobManagerInvalidStateError: If the backend does not support
                the experiment type.
        """
        if (any(isinstance(exp, ScheduleComponent) for exp in experiments) and
                not backend.configuration().open_pulse):
            raise IBMQJobManagerInvalidStateError("The backend does not support pulse schedules.")

        if not skip_transpile:
            experiments = transpile(circuits=experiments, backend=backend)
        experiment_list = self._split_experiments(
            experiments, backend=backend, max_experiments_per_job=max_experiments_per_job)

        job_set = ManagedJobSet(name=name)
        job_set.run(experiment_list, backend=backend, executor=self._executor, shots=shots)
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
        job_set_statues = [job_set.statuses() for job_set in self._job_sets]
        flat_status_list = [stat for stat_list in job_set_statues for stat in stat_list]

        report = ["Summary report:"]
        report.extend(format_status_counts(flat_status_list))

        if detailed:
            report.append("\nDetail report:")
            for i, job_set in enumerate(self._job_sets):
                report.append(("  Job set {}:".format(job_set.name())))
                report.extend(format_job_details(
                    job_set_statues[i], job_set.managed_jobs()))

        return '\n'.join(report)

    def job_set(self, name: str) -> Optional[ManagedJobSet]:
        """Returns the managed job set with the specified name.

        If multiple sets with the same name is found, the first set is returned.

        Args:
             name: Name of the managed job set.

        Returns:
            A set of managed jobs or ``None`` if no named set found.
        """
        for job_set in self._job_sets:
            if job_set.name() == name:
                return job_set
        return None

    @classmethod
    def managed_set(
            cls,
            name: str,
            provider: AccountProvider,
            limit: int = 10
    ) -> ManagedJobSet:
        """Returns the managed job set with the specified name.

        Args:
             name: Name of the managed job set.
             provider: Provider for the IBM Q Experience account.
             limit: number of jobs to retrieve.

        Returns:
            A set of jobs managed by a different instance of job manager.
        """
        job_name_regex = '^{}_[0-9]+$'.format(name)
        jobs = provider.backends.jobs(limit=limit, job_name=job_name_regex)
        return RetrievedManagedJobSet(jobs)
