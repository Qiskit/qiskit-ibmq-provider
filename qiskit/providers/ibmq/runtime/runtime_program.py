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
from datetime import datetime
from typing import Dict, Optional, List, Union

logger = logging.getLogger(__name__)


class RuntimeProgram:
    """Class representing a program definition."""

    def __init__(
            self,
            program_name: str,
            program_id: str,
            description: str,
            parameters: List,
            return_values: List,
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
        for param in parameters:
            self._parameters.append(
                ProgramParameter(name=param['name'],
                                 description=param['description'],
                                 param_type=param['type']))
        for ret in return_values:
            self._return_values.append(ProgramReturn(name=ret['name'],
                                                     description=ret['description'],
                                                     return_type=ret['type']))

    def pprint(self):
        formatted = [f'"{self.name}":',
                     f"  Description: {self._description}",
                     f"  Parameters:"]

        if self._parameters:
            for param in self._parameters:
                formatted.append(" "*4 + "- " + param.name + ":")
                formatted.append(" "*6 + "description: " + param.description)
                formatted.append(" "*6 + "type: " + param.type)
        else:
            formatted.append(" "*4 + "none")

        formatted.append("  Returns:")
        if self._return_values:
            for ret in self._return_values:
                formatted.append(" "*4 + "- " + ret.name + ":")
                formatted.append(" "*6 + "description: " + ret.description)
                formatted.append(" "*6 + "type: " + ret.type)
        else:
            formatted.append(" "*4 + "none")
        print('\n'.join(formatted))


class ProgramParameter:

    def __init__(self, name: str, description: str, param_type: str):
        """

        Args:
            description:
            param_type:
        """
        self.name = name
        self.description = description
        self.type = param_type


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
