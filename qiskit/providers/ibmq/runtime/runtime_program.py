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

"""Qiskit runtime program."""

import logging
from typing import Optional, List, NamedTuple, Dict
from types import SimpleNamespace
from qiskit.providers.ibmq.exceptions import IBMQInputValueError


logger = logging.getLogger(__name__)


class RuntimeProgram:
    """Class representing program metadata.

    This class contains the metadata describing a program, such as its
    name, ID, description, etc.

    You can use the :class:`~qiskit.providers.ibmq.runtime.IBMRuntimeService`
    to retrieve the metadata of a specific program or all programs. For example::

        from qiskit import IBMQ

        provider = IBMQ.load_account()

        # To retrieve metadata of all programs.
        programs = provider.runtime.programs()

        # To retrieve metadata of a single program.
        program = provider.runtime.program(program_id='circuit-runner')
        print(f"Program {program.name} takes parameters {program.parameters().metadata}")
    """

    def __init__(
            self,
            program_name: str,
            program_id: str,
            description: str,
            parameters: Optional[List] = None,
            return_values: Optional[List] = None,
            interim_results: Optional[List] = None,
            max_execution_time: int = 0,
            version: str = "0",
            backend_requirements: Optional[Dict] = None,
            creation_date: str = "",
            is_public: bool = False
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
            version: Program version.
            backend_requirements: Backend requirements.
            creation_date: Program creation date.
            is_public: ``True`` if program is visible to all. ``False`` if it's only visible to you.
        """
        self._name = program_name
        self._id = program_id
        self._description = description
        self._max_execution_time = max_execution_time
        self._version = version
        self._backend_requirements = backend_requirements or {}
        self._parameters: List[ProgramParameter] = []
        self._return_values: List[ProgramResult] = []
        self._interim_results: List[ProgramResult] = []
        self._creation_date = creation_date
        self._is_public = is_public

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
        def _format_common(items: List) -> None:
            """Add name, description, and type to `formatted`."""
            for item in items:
                formatted.append(" "*4 + "- " + item.name + ":")
                formatted.append(" "*6 + "Description: " + item.description)
                formatted.append(" "*6 + "Type: " + item.type)
                if hasattr(item, 'required'):
                    formatted.append(" "*6 + "Required: " + str(item.required))

        formatted = [f'{self.program_id}:',
                     f"  Name: {self.name}",
                     f"  Description: {self.description}",
                     f"  Version: {self.version}",
                     f"  Creation date: {self.creation_date}",
                     f"  Max execution time: {self.max_execution_time}",
                     f"  Input parameters:"]

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

    def to_dict(self) -> Dict:
        """Convert program metadata to dictionary format.

        Returns:
            Program metadata in dictionary format.
        """
        return {
            "program_id": self.program_id,
            "name": self.name,
            "description": self.description,
            "max_execution_time": self.max_execution_time,
            "version": self.version,
            "backend_requirements": self.backend_requirements,
            "parameters": self.parameters(),
            "return_values": self.return_values,
            "interim_results": self.interim_results,
            "is_public": self._is_public
        }

    def parameters(self) -> 'ParameterNamespace':
        """Program parameter namespace.

        You can use the returned namespace to assign parameter values and pass
        the namespace to :meth:`qiskit.providers.ibmq.runtime.IBMRuntimeService.run`.
        The namespace allows you to use auto-completion to find program parameters.

        Note that each call to this method returns a new namespace instance and
        does not include any modification to the previous instance.

        Returns:
            Program parameter namespace.
        """
        return ParameterNamespace(self._parameters)

    @property
    def program_id(self) -> str:
        """Program ID.

        Returns:
            Program ID.
        """
        return self._id

    @property
    def name(self) -> str:
        """Program name.

        Returns:
            Program name.
        """
        return self._name

    @property
    def description(self) -> str:
        """Program description.

        Returns:
            Program description.
        """
        return self._description

    @property
    def return_values(self) -> List['ProgramResult']:
        """Program return value definitions.

        Returns:
            Return value definitions for this program.
        """
        return self._return_values

    @property
    def interim_results(self) -> List['ProgramResult']:
        """Program interim result definitions.

        Returns:
            Interim result definitions for this program.
        """
        return self._interim_results

    @property
    def max_execution_time(self) -> int:
        """Maximum execution time in seconds.

        A program execution exceeding this time will be forcibly terminated.

        Returns:
            Maximum execution time.
        """
        return self._max_execution_time

    @property
    def version(self) -> str:
        """Program version.

        Returns:
            Program version.
        """
        return self._version

    @property
    def backend_requirements(self) -> Dict:
        """Backend requirements.

        Returns:
            Backend requirements for this program.
        """
        return self._backend_requirements

    @property
    def creation_date(self) -> str:
        """Program creation date.

        Returns:
            Program creation date.
        """
        return self._creation_date

    @property
    def is_public(self) -> bool:
        """Whether the program is visible to all.

        Returns:
            Whether the program is public.
        """
        return self._is_public


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


class ParameterNamespace(SimpleNamespace):
    """ A namespace for program parameters with validation.

    This class provides a namespace for program parameters with auto-completion
    and validation support.
    """

    def __init__(self, params: List[ProgramParameter]):
        """ParameterNamespace constructor.

        Args:
            params: The program's input parameters.
        """
        super().__init__()
        # Allow access to the raw program parameters list
        self.__metadata = params
        # For localized logic, create store of parameters in dictionary
        self.__program_params: dict = {}

        for param in params:
            # (1) Add parameters to a dict by name
            setattr(self, param.name, None)
            # (2) Store the program params for validation
            self.__program_params[param.name] = param

    @property
    def metadata(self) -> List[ProgramParameter]:
        """Returns the parameter metadata"""
        return self.__metadata

    def validate(self) -> None:
        """Validate program input values.

        Note:
            This method only verifies that required parameters have values. It
            does not fail the validation if the namepsace has extraneous parameters.

        Raises:
            IBMQInputValueError if validation fails
        """

        # Iterate through the user's stored inputs
        for param_name, program_param in self.__program_params.items():
            # Set invariants: User-specified parameter value (value) and whether it's required (req)
            value = getattr(self, param_name, None)
            # Check there exists a program parameter of that name.
            if value is None and program_param.required:
                raise IBMQInputValueError('Param (%s) missing required value!' % param_name)

    def __str__(self) -> str:
        """Creates string representation of object"""
        # Header
        header = '| {:10.10} | {:12.12} | {:12.12} ' \
                 '| {:8.8} | {:>15} |'.format(
                     'Name',
                     'Value',
                     'Type',
                     'Required',
                     'Description'
                     )
        # List of ProgramParameter objects (str)
        params_str = '\n'.join([
            '| {:10.10} | {:12.12} | {:12.12}| {:8.8} | {:>15} |'.format(
                param.name,
                str(getattr(self, param.name, 'None')),
                param.type,
                str(param.required),
                param.description
            ) for param in self.__program_params.values()])

        return "ParameterNamespace (Values):\n%s\n%s\n%s" \
               % (header, '-' * len(header), params_str)
