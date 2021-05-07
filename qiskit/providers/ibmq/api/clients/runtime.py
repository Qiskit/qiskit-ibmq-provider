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

"""Client for accessing IBM Quantum runtime service."""

import logging
from typing import List, Dict, Union, Optional

from qiskit.providers.ibmq.credentials import Credentials
from qiskit.providers.ibmq.api.session import RetrySession

from ..rest.runtime import Runtime

logger = logging.getLogger(__name__)


class RuntimeClient:
    """Client for accessing runtime service."""

    def __init__(
            self,
            credentials: Credentials,
    ) -> None:
        """RandomClient constructor.

        Args:
            credentials: Account credentials.
        """
        self._session = RetrySession(credentials.runtime_url, credentials.access_token,
                                     **credentials.connection_parameters())
        self.api = Runtime(self._session)

    def list_programs(self) -> List[Dict]:
        """Return a list of runtime programs.

        Returns:
            A list of quantum programs.
        """
        return self.api.list_programs()

    def program_create(
            self,
            program_data: Union[bytes, str],
            name: str,
            description: str,
            max_execution_time: int,
            version: Optional[str] = None,
            backend_requirements: Optional[Dict] = None,
            parameters: Optional[Dict] = None,
            return_values: Optional[List] = None,
            interim_results: Optional[List] = None
    ) -> Dict:
        """Create a new program.

        Args:
            name: Name of the program.
            program_data: Program data.
            description: Program description.
            max_execution_time: Maximum execution time.
            version: Program version.
            backend_requirements: Backend requirements.
            parameters: Program parameters.
            return_values: Program return values.
            interim_results: Program interim results.

        Returns:
            Server response.
        """
        return self.api.create_program(
            program_data=program_data,
            name=name,
            description=description, max_execution_time=max_execution_time,
            version=version, backend_requirements=backend_requirements,
            parameters=parameters, return_values=return_values,
            interim_results=interim_results
        )

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
            params: str
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
        return self.api.program_run(program_id=program_id, hub=credentials.hub,
                                    group=credentials.group, project=credentials.project,
                                    backend_name=backend_name, params=params)

    def program_delete(self, program_id: str) -> None:
        """Delete the specified program.

        Args:
            program_id: Program ID.
        """
        self.api.program(program_id).delete()

    def job_get(self, job_id: str) -> Dict:
        """Get job data.

        Args:
            job_id: Job ID.

        Returns:
            JSON response.
        """
        response = self.api.program_job(job_id).get()
        logger.debug("Runtime job get response: %s", response)
        return response

    def jobs_get(self, limit: int = None, skip: int = None) -> Dict:
        """Get job data for all jobs.

        Args:
            limit: Number of results to return.
            skip: Number of results to skip.

        Returns:
            JSON response.
        """
        return self.api.jobs_get(limit=limit, skip=skip)

    def job_results(self, job_id: str) -> str:
        """Get the results of a program job.

        Args:
            job_id: Program job ID.

        Returns:
            Job result.
        """
        return self.api.program_job(job_id).results()

    def job_cancel(self, job_id: str) -> None:
        """Cancel a job.

        Args:
            job_id: Runtime job ID.
        """
        self.api.program_job(job_id).cancel()

    def job_delete(self, job_id: str) -> None:
        """Delete a job.

        Args:
            job_id: Runtime job ID.
        """
        self.api.program_job(job_id).delete()

    def logout(self) -> None:
        """Clear authorization cache."""
        self.api.logout()
