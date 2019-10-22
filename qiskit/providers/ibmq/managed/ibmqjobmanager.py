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
from typing import List, Optional, Union, Any
from concurrent import futures

from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule

from .exceptions import IBMQJobManagerInvalidStateError
from .utils import format_job_details, format_status_counts
from .managedjobset import ManagedJobSet
from ..ibmqbackend import IBMQBackend

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
            max_experiments_per_job: Optional[int] = None,
            **run_config: Any
    ) -> ManagedJobSet:
        """Execute a set of circuits or pulse schedules on a backend.

        The circuits or schedules will be split into multiple jobs. Circuits
        or schedules in a job will be executed together in each shot.

        A name can be assigned to this job set. Each job in this set will have
        a job name consists of the set name followed by an underscore (_)
        followed by the job index and another underscore. For example, a job
        for set ``foo`` can have a job name of ``foo_1_``.  The name can then
        be used to retrieve the jobs later. If no name is given, the job
        submission datetime will be used.

        Args:
            experiments: Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            name: Name for this set of jobs. Default: current datetime.
            max_experiments_per_job: Maximum number of experiments to run in each job.
                If not specified, the default is to use the maximum allowed by
                the backend.
                If the specified value is greater the maximum allowed by the
                backend, the default is used.
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
            IBMQJobManagerInvalidStateError: If the backend does not support
                the experiment type.
        """
        if (any(isinstance(exp, Schedule) for exp in experiments) and
                not backend.configuration().open_pulse):
            raise IBMQJobManagerInvalidStateError("The backend does not support pulse schedules.")

        experiment_list = self._split_experiments(
            experiments, backend=backend, max_experiments_per_job=max_experiments_per_job)

        job_set = ManagedJobSet(name=name)
        job_set.run(experiment_list, backend=backend, executor=self._executor, **run_config)
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
                report.append(("  Job set {}:".format(job_set.name())))
                report.extend(format_job_details(
                    job_set_statuses[i], job_set.managed_jobs()))

        return '\n'.join(report)

    def job_sets(self, name: Optional[str] = None) -> List[ManagedJobSet]:
        """Returns a list of managed job sets matching the specified filtering.

        Args:
             name: Name of the managed job sets.

        Returns:
            A list of managed job sets.
        """
        if name:
            return [job_set for job_set in self._job_sets if job_set.name() == name]

        return self._job_sets
