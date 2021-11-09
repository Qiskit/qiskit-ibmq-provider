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
import re
from typing import Optional, List, Dict
from types import SimpleNamespace
from qiskit.providers.ibmq.exceptions import IBMQInputValueError, IBMQNotAuthorizedError
from .exceptions import QiskitRuntimeError, RuntimeProgramNotFound
from ..api.clients.runtime import RuntimeClient
from ..api.exceptions import RequestsApiError

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
            parameters: Optional[Dict] = None,
            return_values: Optional[Dict] = None,
            interim_results: Optional[Dict] = None,
            max_execution_time: int = 0,
            backend_requirements: Optional[Dict] = None,
            creation_date: str = "",
            update_date: str = "",
            is_public: Optional[bool] = False,
            data: str = "",
            api_client: Optional[RuntimeClient] = None
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
            backend_requirements: Backend requirements.
            creation_date: Program creation date.
            update_date: Program last updated date.
            is_public: ``True`` if program is visible to all. ``False`` if it's only visible to you.
            data: Program data.
            api_client: Runtime api client.
        """
        self._name = program_name
        self._id = program_id
        self._description = description
        self._max_execution_time = max_execution_time
        self._backend_requirements = backend_requirements or {}
        self._parameters = parameters or {}
        self._return_values = return_values or {}
        self._interim_results = interim_results or {}
        self._creation_date = creation_date
        self._update_date = update_date
        self._is_public = is_public
        self._data = data
        self._api_client = api_client

    def __str__(self) -> str:
        def _format_common(schema: Dict) -> None:
            """Add title, description and property details to `formatted`."""
            if "description" in schema:
                formatted.append(" "*4 + "Description: {}".format(schema["description"]))
            if "type" in schema:
                formatted.append(" "*4 + "Type: {}".format(str(schema["type"])))
            if "properties" in schema:
                formatted.append(" "*4 + "Properties:")
                for property_name, property_value in schema["properties"].items():
                    formatted.append(" "*8 + "- " + property_name + ":")
                    for key, value in property_value.items():
                        formatted.append(" "*12 + "{}: {}".format(sentence_case(key), str(value)))
                    formatted.append(" "*12 + "Required: " +
                                     str(property_name in schema.get("required", [])))

        def sentence_case(camel_case_text: str) -> str:
            """Converts camelCase to Sentence case"""
            if camel_case_text == '':
                return camel_case_text
            sentence_case_text = re.sub('([A-Z])', r' \1', camel_case_text)
            return sentence_case_text[:1].upper() + sentence_case_text[1:].lower()

        formatted = [f'{self.program_id}:',
                     f"  Name: {self.name}",
                     f"  Description: {self.description}",
                     f"  Creation date: {self.creation_date}",
                     f"  Update date: {self.update_date}",
                     f"  Max execution time: {self.max_execution_time}"]

        formatted.append("  Input parameters:")
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
    def return_values(self) -> Dict:
        """Program return value definitions.

        Returns:
            Return value definitions for this program.
        """
        return self._return_values

    @property
    def interim_results(self) -> Dict:
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
    def update_date(self) -> str:
        """Program last updated date.

        Returns:
            Program last updated date.
        """
        return self._update_date

    @property
    def is_public(self) -> bool:
        """Whether the program is visible to all.

        Returns:
            Whether the program is public.
        """
        return self._is_public

    @property
    def data(self) -> str:
        """Program data.

        Returns:
            Program data.

        Raises:
            IBMQNotAuthorizedError: if user is not the program author.
        """
        if not self._data:
            self._refresh()
            if not self._data:
                raise IBMQNotAuthorizedError(
                    'Only program authors are authorized to retrieve program data')
        return self._data

    def _refresh(self) -> None:
        """Refresh program data and metadata

        Raises:
            RuntimeProgramNotFound: If the program does not exist.
            QiskitRuntimeError: If the request failed.
        """
        try:
            response = self._api_client.program_get(self._id)
        except RequestsApiError as ex:
            if ex.status_code == 404:
                raise RuntimeProgramNotFound(f"Program not found: {ex.message}") from None
            raise QiskitRuntimeError(f"Failed to get program: {ex}") from None
        self._backend_requirements = {}
        self._parameters = {}
        self._return_values = {}
        self._interim_results = {}
        if "spec" in response:
            self._backend_requirements = response["spec"].get('backend_requirements', {})
            self._parameters = response["spec"].get('parameters', {})
            self._return_values = response["spec"].get('return_values', {})
            self._interim_results = response["spec"].get('interim_results', {})
        self._name = response['name']
        self._id = response['id']
        self._description = response.get('description', "")
        self._max_execution_time = response.get('cost', 0)
        self._creation_date = response.get('creation_date', "")
        self._update_date = response.get('update_date', "")
        self._is_public = response.get('is_public', False)
        self._data = response.get('data', "")


class ParameterNamespace(SimpleNamespace):
    """ A namespace for program parameters with validation.

    This class provides a namespace for program parameters with auto-completion
    and validation support.
    """

    def __init__(self, parameters: Dict):
        """ParameterNamespace constructor.

        Args:
            parameters: The program's input parameters.
        """
        super().__init__()
        # Allow access to the raw program parameters dict
        self.__metadata = parameters
        # For localized logic, create store of parameters in dictionary
        self.__program_params: dict = {}

        for parameter_name, parameter_value in parameters.get("properties", {}).items():
            # (1) Add parameters to a dict by name
            setattr(self, parameter_name, None)
            # (2) Store the program params for validation
            self.__program_params[parameter_name] = parameter_value

    @property
    def metadata(self) -> Dict:
        """Returns the parameter metadata"""
        return self.__metadata

    def validate(self) -> None:
        """Validate program input values.

        Note:
            This method only verifies that required parameters have values. It
            does not fail the validation if the namespace has extraneous parameters.

        Raises:
            IBMQInputValueError: if validation fails
        """

        # Iterate through the user's stored inputs
        for parameter_name, parameter_value in self.__program_params.items():
            # Set invariants: User-specified parameter value (value) and if it's required (req)
            value = getattr(self, parameter_name, None)
            # Check there exists a program parameter of that name.
            if value is None and parameter_name in self.metadata.get("required", []):
                raise IBMQInputValueError('Param (%s) missing required value!' % parameter_name)

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
        params_str = '\n'.join([
            '| {:10.10} | {:12.12} | {:12.12}| {:8.8} | {:>15} |'.format(
                parameter_name,
                str(getattr(self, parameter_name, "None")),
                str(parameter_value.get("type", "None")),
                str(parameter_name in self.metadata.get("required", [])),
                str(parameter_value.get("description", "None"))
            ) for parameter_name, parameter_value in self.__program_params.items()])

        return "ParameterNamespace (Values):\n%s\n%s\n%s" \
               % (header, '-' * len(header), params_str)
