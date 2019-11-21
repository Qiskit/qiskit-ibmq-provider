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

"""Results managed by the job manager."""

from typing import List, Optional, Union, Tuple, Dict

from qiskit.result import Result
from qiskit.circuit import QuantumCircuit
from qiskit.pulse import Schedule

from .exceptions import IBMQManagedResultDataNotAvailable
from ..job.exceptions import JobError


class ManagedResults:
    """Results managed by job manager.

    This class is a wrapper around the `Result` class. It provides the same
    methods as the `Result` class. Please refer to the `Result` class for
    more information on the methods.
    """

    def __init__(
            self,
            job_set: 'ManagedJobSet',  # type: ignore[name-defined]
            backend_name: str,
            success: bool
    ):
        """Creates a new ManagedResults instance.

        Args:
            job_set: Managed job set for these results.
            backend_name: Name of the backend used to run the experiments.
            success: True if all experiments were successful and results
                available. False otherwise.
        """
        self._job_set = job_set
        self.backend_name = backend_name
        self.success = success

    def data(self, experiment: Union[str, QuantumCircuit, Schedule, int]) -> Dict:
        """Get the raw data for an experiment.

        Args:
            experiment: the index of the experiment. Several types are
                accepted for convenience::
                * str: the name of the experiment.
                * QuantumCircuit: the name of the circuit instance will be used.
                * Schedule: the name of the schedule instance will be used.
                * int: the position of the experiment.

        Returns:
            Refer to the ``Result.data()`` documentation for return information.

        Raises:
            IBMQManagedResultDataNotAvailable: If data for the experiment could not be retrieved.
            IBMQJobManagerJobNotFound: If the job for the experiment could not
                be found.
        """
        result, exp_index = self._get_result(experiment)
        return result.data(exp_index)

    def get_memory(
            self,
            experiment: Union[str, QuantumCircuit, Schedule, int]
    ) -> Union[list, 'numpy.ndarray']:  # type: ignore[name-defined]
        """Get the sequence of memory states (readouts) for each shot.
        The data from the experiment is a list of format
        ['00000', '01000', '10100', '10100', '11101', '11100', '00101', ..., '01010']

        Args:
            experiment: the index of the experiment, as specified by ``data()``.

        Returns:
            Refer to the ``Result.get_memory()`` documentation for return information.

        Raises:
            IBMQManagedResultDataNotAvailable: If data for the experiment could not be retrieved.
            IBMQJobManagerJobNotFound: If the job for the experiment could not
                be found.
        """
        result, exp_index = self._get_result(experiment)
        return result.get_memory(exp_index)

    def get_counts(
            self,
            experiment: Union[str, QuantumCircuit, Schedule, int]
    ) -> Dict[str, int]:
        """Get the histogram data of an experiment.

        Args:
            experiment: the index of the experiment, as specified by ``data()``.

        Returns:
            Refer to the ``Result.get_counts()`` documentation for return information.

        Raises:
            IBMQManagedResultDataNotAvailable: If data for the experiment could not be retrieved.
            IBMQJobManagerJobNotFound: If the job for the experiment could not
                be found.
        """
        result, exp_index = self._get_result(experiment)
        return result.get_counts(exp_index)

    def get_statevector(
            self,
            experiment: Union[str, QuantumCircuit, Schedule, int],
            decimals: Optional[int] = None
    ) -> List[complex]:
        """Get the final statevector of an experiment.

        Args:
            experiment: the index of the experiment, as specified by ``data()``.
            decimals: the number of decimals in the statevector.
                If None, does not round.

        Returns:
            Refer to the ``Result.get_statevector()`` documentation for return information.

        Raises:
            IBMQManagedResultDataNotAvailable: If data for the experiment could not be retrieved.
            IBMQJobManagerJobNotFound: If the job for the experiment could not
                be found.
        """
        result, exp_index = self._get_result(experiment)
        return result.get_statevector(experiment=exp_index, decimals=decimals)

    def get_unitary(
            self,
            experiment: Union[str, QuantumCircuit, Schedule, int],
            decimals: Optional[int] = None
    ) -> List[List[complex]]:
        """Get the final unitary of an experiment.

        Args:
            experiment: the index of the experiment, as specified by ``data()``.
            decimals: the number of decimals in the unitary.
                If None, does not round.

        Returns:
            Refer to the ``Result.get_unitary()`` documentation for return information.

        Raises:
            IBMQManagedResultDataNotAvailable: If data for the experiment could not be retrieved.
            IBMQJobManagerJobNotFound: If the job for the experiment could not
                be found.
        """
        result, exp_index = self._get_result(experiment)
        return result.get_unitary(experiment=exp_index, decimals=decimals)

    def _get_result(
            self,
            experiment: Union[str, QuantumCircuit, Schedule, int]
    ) -> Tuple[Result, int]:
        """Get the result of the job used to submit the experiment.

        Args:
            experiment: the index of the experiment, as specified by ``data()``.

        Returns:
            A tuple of the result of the job used to submit the experiment and
                the experiment index within the job.

        Raises:
            IBMQManagedResultDataNotAvailable: If data for the experiment could not be retrieved.
            IBMQJobManagerJobNotFound: If the job for the experiment could not
                be found.
        """

        (job, exp_index) = self._job_set.job(experiment)
        if job is None:
            raise IBMQManagedResultDataNotAvailable(
                "Job for experiment {} was not successfully submitted.".format(experiment))

        try:
            result = job.result()
            return result, exp_index
        except JobError as err:
            raise IBMQManagedResultDataNotAvailable(
                "Result data for experiment {} is not available.".format(experiment)) from err
