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
from typing import Any, Dict, Optional

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
        """RuntimeClient constructor.

        Args:
            credentials: Account credentials.
        """
        self._session = RetrySession(credentials.runtime_url, credentials.access_token,
                                     **credentials.connection_parameters())
        self.api = Runtime(self._session)

    def list_programs(self, limit: int = None, skip: int = None) -> Dict[str, Any]:
        """Return a list of runtime programs.

        Args:
            limit: The number of programs to return.
            skip: The number of programs to skip.

        Returns:
            A list of runtime programs.
        """
        return self.api.list_programs(limit, skip)

    def program_create(
            self,
            program_data: str,
            name: str,
            description: str,
            max_execution_time: int,
            is_public: Optional[bool] = False,
            spec: Optional[Dict] = None
    ) -> Dict:
        """Create a new program.

        Args:
            name: Name of the program.
            program_data: Program data (base64 encoded).
            description: Program description.
            max_execution_time: Maximum execution time.
            is_public: Whether the program should be public.
            spec: Backend requirements, parameters, interim results, return values, etc.

        Returns:
            Server response.
        """
        return self.api.create_program(
            program_data=program_data,
            name=name,
            description=description, max_execution_time=max_execution_time,
            is_public=is_public, spec=spec
        )

    def program_get(self, program_id: str) -> Dict:
        """Return a specific program.

        Args:
            program_id: Program ID.

        Returns:
            Program information.
        """
        return self.api.program(program_id).get()

    def set_program_visibility(self, program_id: str, public: bool) -> None:
        """Sets a program's visibility.

        Args:
            program_id: Program ID.
            public: If ``True``, make the program visible to all.
                If ``False``, make the program visible to just your account.

        """
        if public:
            self.api.program(program_id).make_public()
        else:
            self.api.program(program_id).make_private()

    def program_run(
            self,
            program_id: str,
            credentials: Credentials,
            backend_name: str,
            params: Dict,
            image: str,
            log_level: Optional[str] = None
    ) -> Dict:
        """Run the specified program.

        Args:
            program_id: Program ID.
            credentials: Credentials used to run the program.
            backend_name: Name of the backend to run the program.
            params: Parameters to use.
            image: The runtime image to use.
            log_level: Log level to use.

        Returns:
            JSON response.
        """
        return self.api.program_run(program_id=program_id, hub=credentials.hub,
                                    group=credentials.group, project=credentials.project,
                                    backend_name=backend_name, params=params,
                                    image=image, log_level=log_level)

    def program_delete(self, program_id: str) -> None:
        """Delete the specified program.

        Args:
            program_id: Program ID.
        """
        self.api.program(program_id).delete()

    def program_update(
            self,
            program_id: str,
            program_data: str = None,
            name: str = None,
            description: str = None,
            max_execution_time: int = None,
            spec: Optional[Dict] = None
    ) -> None:
        """Update a program.

        Args:
            program_id: Program ID.
            program_data: Program data (base64 encoded).
            name: Name of the program.
            description: Program description.
            max_execution_time: Maximum execution time.
            spec: Backend requirements, parameters, interim results, return values, etc.
        """
        if program_data:
            self.api.program(program_id).update_data(program_data)

        if any([name, description, max_execution_time, spec]):
            self.api.program(program_id).update_metadata(
                name=name, description=description,
                max_execution_time=max_execution_time, spec=spec)

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

    def jobs_get(
            self,
            limit: int = None,
            skip: int = None,
            pending: bool = None,
            program_id: str = None
    ) -> Dict:
        """Get job data for all jobs.

        Args:
            limit: Number of results to return.
            skip: Number of results to skip.
            pending: Returns 'QUEUED' and 'RUNNING' jobs if True,
                returns 'DONE', 'CANCELLED' and 'ERROR' jobs if False.
            program_id: Filter by Program ID.

        Returns:
            JSON response.
        """
        return self.api.jobs_get(limit=limit, skip=skip, pending=pending, program_id=program_id)

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

    def job_logs(self, job_id: str) -> str:
        """Get the job logs.

        Args:
            job_id: Program job ID.

        Returns:
            Job logs.
        """
        return self.api.program_job(job_id).logs()

    def logout(self) -> None:
        """Clear authorization cache."""
        self.api.logout()
