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

import logging
from typing import Optional, List, NamedTuple

logger = logging.getLogger(__name__)


class RuntimeProgram:
    """Class representing program metadata.

    This class contains the metadata describing a program, including its
    name, ID, description, etc.

    You can use the :class:`~qiskit.providers.ibmq.runtime.IBMRuntimeService`
    to retrieve the metadata of a specific program or all programs. For example::

        from qiskit import IBMQ

        provider = IBMQ.load_account()

        # To retrieve metadata of all programs.
        programs = provider.runtime.programs()

        # To retrieve metadata of a single program.
        program = provider.runtime.program(program_id='circuit-runner')
        print(f"Program {program.name} takes parameters {program.parameters}")
    """

    def __init__(
            self,
            program_name: str,
            program_id: str,
            description: str,
            parameters: Optional[List] = None,
            return_values: Optional[List] = None,
            interim_results: Optional[List] = None,
            max_execution_time: int = 0
    ) -> None:
        """RuntimeProgram constructor.

        Args:
            program_name: Program name.
            program_id: Program ID.
            description: Program description.
            parameters: Documentation on program parameters.
            return_values: Documentation on program return values.
            interim_results: Documentation on program interim results.
            max_execution_time: Maximum execution time.
        """
        self._name = program_name
        self._id = program_id
        self._description = description
        self._max_execution_time = max_execution_time
        self._parameters = []
        self._return_values = []
        self._interim_results = []

        if parameters:
            for param in parameters:
                self._parameters.append(
                    ProgramParameter(name=param['name'],
                                     description=param['description'],
                                     type=param['type'],
                                     required=param['required']))
        if return_values is not None:
            for ret in return_values:
                self._return_values.append(ProgramResult(name=ret['name'],
                                                         description=ret['description'],
                                                         type=ret['type']))
        if interim_results is not None:
            for intret in interim_results:
                self._interim_results.append(ProgramResult(name=intret['name'],
                                                           description=intret['description'],
                                                           type=intret['type']))

    def __str__(self) -> str:
        def _format_common(items: List):
            """Add name, description, and type to `formatted`."""
            for item in items:
                formatted.append(" "*4 + "- " + item.name + ":")
                formatted.append(" "*6 + "Description: " + item.description)
                formatted.append(" "*6 + "Type: " + item.type)
                if hasattr(item, 'required'):
                    formatted.append(" "*6 + "Required: " + str(item.required))

        formatted = [f'{self.name}:',
                     f"  ID: {self._id}",
                     f"  Description: {self._description}",
                     f"  Parameters:"]

        if self._parameters:
            _format_common(self._parameters)
        else:
            formatted.append(" "*4 + "none")

        formatted.append("  Interim results:")
        if self._interim_results:
            _format_common(self._interim_results)
        else:
            formatted.append(" "*4 + "none")

        formatted.append("  Returns:")
        if self._return_values:
            _format_common(self._return_values)
        else:
            formatted.append(" "*4 + "none")
        return '\n'.join(formatted)

    @property
    def program_id(self) -> str:
        """Return program ID.

        Returns:
            Program ID.
        """
        return self._id

    @property
    def name(self) -> str:
        """Return program name.

        Returns:
            Program name.
        """
        return self._name

    @property
    def description(self) -> str:
        """Return program description.

        Returns:
            Program description.
        """
        return self._description

    @property
    def parameters(self) -> List['ProgramParameter']:
        """Return program parameter definitions.

        Returns:
            Parameter definitions for this program.
        """
        return self._parameters

    @property
    def return_values(self) -> List['ProgramResult']:
        """Return program return value definitions.

        Returns:
            Return value definitions for this program.
        """
        return self._return_values

    @property
    def interim_results(self) -> List['ProgramResult']:
        """Return program interim result definitions.

        Returns:
            Interim result definitions for this program.
        """
        return self._interim_results

    @property
    def max_execution_time(self) -> int:
        """Return maximum execution time.

        Returns:
            Maximum execution time.
        """
        return self._max_execution_time


class ProgramParameter(NamedTuple):
    """Program parameter."""
    name: str
    description: str
    type: str
    required: bool


class ProgramResult(NamedTuple):
    """Program result."""
    name: str
    description: str
    type: str
