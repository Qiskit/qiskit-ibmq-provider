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
import time
from typing import List, Optional, Union
from datetime import datetime
from collections import Counter

from qiskit.pulse import ScheduleComponent
from qiskit.compiler import assemble, transpile
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers import JobError, JobTimeoutError
from qiskit.result import Result

logger = logging.getLogger(__name__)


class JobManager:
    """Job manager for IBM Q Experience."""

    def __init__(self) -> None:
        """Creates a new JobManager instance."""
        self._jobs = []

    def run(
            self,
            experiments: Union[List['QuantumCircuit'], List['Schedule']],
            backend: 'IBMQBackend',
            name_prefix: Optional[str] = None,
            shots: int = 1024,
            skip_transpile: bool = False,
            max_experiments_per_job: Optional[int] = None
    ) -> List['IBMQJob']:
        """Execute a list of circuits or pulse schedules on a backend.

        The circuits or schedules will be split into multiple jobs. Circuits
        or schedules in a job will be executed together in each shot.

        The circuits will first be transpiled before submitted, using the
        default transpiler settings. Specify ``skip_transpiler=True`` if you
        want to skip this step.

        Args:
            experiments : Circuit(s) or pulse schedule(s) to execute.
            backend: Backend to execute the experiments on.
            name_prefix: Prefix of the job name. Each job name will be the
                prefix followed by an underscore (_) followed by the job index.
            shots: Number of repetitions of each experiment, for sampling. Default: 1024.
            skip_transpile: True if transpilation is to be skipped, otherwise False.
            max_experiments_per_job: Maximum number of experiments to run in each job.
                If not specified, the default is to use the maximum allowed by
                the backend.
                If the specified value is greater the maximum allowed by the
                backend, the default is used.

        Returns:
            A list of jobs submitted to the backend.

        Raises:
            JobError: If a job cannot be submitted.
        """
        if (all(isinstance(exp, ScheduleComponent) for exp in experiments) and
                not backend.configuration().open_pulse):
            raise JobError("The backend does not support pulse schedules.")

        if not skip_transpile:
            experiments = transpile(circuits=experiments, backend=backend)
        experiment_list = self._split_experiments(experiments, backend=backend,
                                                  max_experiments_per_job=max_experiments_per_job)

        name_prefix = name_prefix or datetime.utcnow().isoformat()
        for i, experiment in enumerate(experiment_list):
            qobj = assemble(experiment, backend=backend, shots=shots)
            job = backend.run(qobj=qobj, job_name="{}_{}".format(name_prefix, i))
            self._jobs.append(job)

        return self._jobs

    def status(self) -> List[Union[JobStatus, None]]:
        """Return the status of each job.

        Returns:
            A list of job statuses. The entry is ``None`` if the job status
                cannot be retrieved due to server error.
        """
        statuses = []
        for i, job in enumerate(self._jobs):
            try:
                statuses.append(job.status())
            except JobError as err:
                logger.warning("Unable to retrieve status for job %d (job ID=%s): %s",
                               i, job.job_id(), str(err))
                statuses.append(None)

        return statuses

    def report(self, detailed: bool = True) -> str:
        """Return a report on current job statuses.

        Args:
            detailed: True if a detailed report is be returned. False
                if a summary report is to be returned.

        Returns:
            str: a report on job statuses.
        """
        statuses = self.status()
        counts = Counter(statuses)

        report = [
            "Summary report:",
            "       Total jobs: {}".format(len(statuses)),
            "  Successful jobs: {}".format(counts[JobStatus.DONE]),
            "      Failed jobs: {}".format(counts[JobStatus.ERROR]),
            "   Cancelled jobs: {}".format(counts[JobStatus.CANCELLED]),
            "     Running jobs: {}".format(counts[JobStatus.RUNNING])
        ]

        if detailed:
            report.append("\nDetail report:")
            for i, status in enumerate(statuses):
                report.append("  - Job {} -".format(i))
                report.append("    job ID: {}".format(self._jobs[i].job_id()))
                report.append("    status: {}".format(status.value))
                if status is JobStatus.QUEUED:
                    report.append("    queue position: {}".format(
                        self._jobs[i].queue_position()))

        return '\n'.join(report)

    def result(self, timeout: Optional[float] = None) -> List[Union['Result', None]]:
        """Return the results of the jobs.

        This call will block until results for all successful jobs become
        available or the timeout is reached.

        Note:
            Some IBMQ job results can be read only once. A second attempt to
            query the API for the same job will fail, as the job is "consumed".

            The first call to this method in a ``JobManager`` instance will
            query the API and consume the results of successful jobs.
            Subsequent calls to the instance's method will also return the
            results, since they are cached. However, attempting to retrieve the
            results again in another instance or session might fail due to the
            jobs having been consumed.

        Args:
           timeout: Number of seconds to wait for job results.

        Returns:
            A list of job results. The entry is ``None`` if the job result
                cannot be retrieved.

        Raises:
            JobTimeoutError: if unable to retrieve all job results before the
                specified timeout.
        """
        results = []
        start_time = time.time()
        original_timeout = timeout

        for i, job in enumerate(self._jobs):
            result = None
            try:
                result = job.result(timeout=timeout)
            except JobError as err:
                if job.status() is JobStatus.ERROR:
                    try:
                        result_response = job._api.job_result(
                            job.job_id(), job._use_object_storage)
                        result = Result.from_dict(result_response)
                        continue
                    except Exception:   # pylint: disable=broad-except
                        pass
                logger.warning("Unable to retrieve result for job %d (job ID=%s): %s",
                               i, job.job_id(), str(err))

            results.append(result)
            if timeout:
                timeout = original_timeout - (time.time() - start_time)
                if timeout <= 0:
                    raise JobTimeoutError("Timeout waiting for the results for "
                                          "job {}.".format(i))

        return results

    def qobj(self) -> List['Qobj']:
        """Return the Qobj for the jobs.

        Returns:
            A list of Qobj for the jobs.
        """
        return [job.qobj() for job in self._jobs]

    def _split_experiments(
            self,
            experiments: Union[List['QuantumCircuit'], List['Schedule']],
            backend: 'IBMQBackend',
            max_experiments_per_job: Optional[int] = None
    ) -> List[Union[List['QuantumCircuit'], List['Schedule']]]:
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
