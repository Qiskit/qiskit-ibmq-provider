# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Base class for program backend."""

import logging
from typing import Union, List, Dict, Optional
from abc import abstractmethod, ABC

from qiskit.qobj import QasmQobj, PulseQobj
from qiskit.pulse import Schedule
from qiskit.providers.backend import BackendV1 as Backend
from qiskit.providers.job import JobV1 as Job
from qiskit.circuit import QuantumCircuit

logger = logging.getLogger(__name__)


class ProgramBackend(Backend, ABC):
    """Base class for a program backend.

    This is a :class:`~qiskit.providers.Backend` class for runtime programs to
    submit circuits.
    """

    @abstractmethod
    def run(
            self,
            circuits: Union[QasmQobj, PulseQobj, QuantumCircuit, Schedule,
                            List[Union[QuantumCircuit, Schedule]]],
            timeout: Optional[int] = None,
            **run_config: Dict
    ) -> Job:
        """Run on the backend.

        Runtime circuit execution is synchronous, and control will not go
        back until the execution finishes. You can use the `timeout` parameter
        to set a timeout value to wait for the execution to finish. Note that if
        the execution times out, circuit execution results will not be available.

        Args:
            circuits: An individual or a
                list of :class:`~qiskit.circuits.QuantumCircuit` or
                :class:`~qiskit.pulse.Schedule` objects to run on the backend.
                A :class:`~qiskit.qobj.QasmQobj` or a
                :class:`~qiskit.qobj.PulseQobj` object is also supported but
                is deprecated.
            timeout: Seconds to wait for circuit execution to finish.
            **run_config: Extra arguments used to configure the run.

        Returns:
            The job to be executed.

        Raises:
            IBMQBackendApiError: If an unexpected error occurred while submitting
                the job.
            IBMQBackendApiProtocolError: If an unexpected value received from
                 the server.
            IBMQBackendValueError: If an input parameter value is not valid.
        """
        # pylint: disable=arguments-differ
        pass
