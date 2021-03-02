# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Client for accessing Random Number Generator (RNG) services."""

import logging
from typing import List, Dict, Any

from qiskit.providers.ibmq.credentials import Credentials
from qiskit.providers.ibmq.api.session import RetrySession

from ..rest.runtime import Runtime

logger = logging.getLogger(__name__)


class RuntimeClient:
    """Client for accessing runtime service."""

    def __init__(
            self,
            access_token: str,
            credentials: Credentials,
    ) -> None:
        """RandomClient constructor.

        Args:
            access_token: IBM Quantum Experience access token.
            credentials: Account credentials.
        """
        url = ''
        self._session = RetrySession(url, access_token,
                                     **credentials.connection_parameters())
        self.api = Runtime(self._session)

    def list_programs(self) -> List[Dict]:
        """Return a list of runtime programs.

        Returns:
            A list of quantum programs.
        """
        return self.api.list_programs()

    def program_get(self, program_id: str) -> Dict:
        """Return a specific program.

        Args:
            program_id: Program ID.

        Returns:
            Program information.
        """
        return self.api.program(program_id).get()

    def program_get_data(self, program_id: str) -> Dict:
        """Return a specific program and its data.

        Args:
            program_id: Program ID.

        Returns:
            Program information, including data.
        """
        return self.api.program(program_id).get_data()

    def program_run(
            self,
            program_id: str,
            credentials: Credentials,
            backend_name: str,
            params: Dict
    ) -> Dict:
        """Run the specified program.

        Args:
            program_id: Program ID.
            credentials: Credentials used to run the program.
            backend_name: Name of the backend to run the program.
            params: Parameters to use.

        Returns:
            JSON response.
        """
        return self.api.program(program_id).run(
            hub=credentials.hub, group=credentials.group, project=credentials.project,
            backend_name=backend_name, params=params)

    def program_delete(self, program_id: str):
        """Delete the specified program.

        Args:
            program_id: Program ID.

        Returns:
            JSON response.
        """
        return self.api.program(program_id).delete()

    def program_job_get(self, program_id, job_id):
        return self.api.program_job(program_id, job_id).get()

    def program_job_results(self, program_id, job_id: str) -> Dict:
        """Get the results of a program job.

        Args:
            job_id: Program job ID.

        Returns:
            JSON response.
        """
        return self.api.program_job(program_id, job_id).results()
