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
from typing import Optional, List

logger = logging.getLogger(__name__)


class RuntimeProgram:
    """Class representing a program definition."""

    def __init__(
            self,
            program_name: str,
            program_id: str,
            description: str,
            parameters: Optional[List] = None,
            return_values: Optional[List] = None,
            cost: float = 0,
            data: Optional[bytes] = None
    ) -> None:
        """

        Args:
            program_name:
            program_id:
            description:
            cost:
        """
        self.name = program_name
        self._id = program_id
        self._description = description
        self._cost = cost
        self._data = data
        self._parameters = []
        self._return_values = []
        if parameters is not None:
            for param in parameters:
                self._parameters.append(
                    ProgramParameter(name=param['name'],
                                     description=param['description'],
                                     param_type=param['type'],
                                     required=param['required']))
        if return_values is not None:
            for ret in return_values:
                self._return_values.append(ProgramReturn(name=ret['name'],
                                                         description=ret['description'],
                                                         return_type=ret['type']))

    def pprint(self):
        formatted = [f'{self.name}:',
                     f"  ID: {self._id}",
                     f"  Description: {self._description}",
                     f"  Parameters:"]

        if self._parameters:
            for param in self._parameters:
                formatted.append(" "*4 + "- " + param.name + ":")
                formatted.append(" "*6 + "Description: " + param.description)
                formatted.append(" "*6 + "Type: " + param.type)
                formatted.append(" "*6 + "Required: " + str(param.required))
        else:
            formatted.append(" "*4 + "none")

        formatted.append("  Returns:")
        if self._return_values:
            for ret in self._return_values:
                formatted.append(" "*4 + "- " + ret.name + ":")
                formatted.append(" "*6 + "Description: " + ret.description)
                formatted.append(" "*6 + "Type: " + ret.type)
        else:
            formatted.append(" "*4 + "none")
        print('\n'.join(formatted))

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        pass


class ProgramParameter:

    def __init__(self, name: str, description: str, param_type: str, required: bool):
        """

        Args:
            description:
            param_type:
        """
        self.name = name
        self.description = description
        self.type = param_type
        self.required = required


class ProgramReturn:

    def __init__(self, name: str, description: str, return_type: str):
        """

        Args:
            description:
            return_type:
        """
        self.name = name
        self.description = description
        self.type = return_type
