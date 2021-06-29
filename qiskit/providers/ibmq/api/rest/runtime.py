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

"""Runtime REST adapter."""

import logging
from typing import Dict, List, Any, Union, Optional
import json
from concurrent import futures

from .base import RestAdapterBase
from ..session import RetrySession

logger = logging.getLogger(__name__)


class Runtime(RestAdapterBase):
    """Rest adapter for Runtime base endpoints."""

    URL_MAP = {
        'programs': '/programs',
        'jobs': '/jobs',
        'logout': '/logout'
    }

    def program(self, program_id: str) -> 'Program':
        """Return an adapter for the program.

        Args:
            program_id: ID of the program.

        Returns:
            The program adapter.
        """
        return Program(self.session, program_id)

    def program_job(self, job_id: str) -> 'ProgramJob':
        """Return an adapter for the job.

        Args:
            job_id: Job ID.

        Returns:
            The program job adapter.
        """
        return ProgramJob(self.session, job_id)

    def list_programs(self) -> List[Dict]:
        """Return a list of runtime programs.

        Returns:
            JSON response.
        """
        url = self.get_url('programs')
        return self.session.get(url).json()

    def create_program(
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
        """Upload a new program.

        Args:
            program_data: Program data.
            name: Name of the program.
            description: Program description.
            max_execution_time: Maximum execution time.
            version: Program version.
            backend_requirements: Backend requirements.
            parameters: Program parameters.
            return_values: Program return values.
            interim_results: Program interim results.

        Returns:
            JSON response.
        """
        url = self.get_url('programs')
        data = {'name': name,
                'cost': str(max_execution_time),
                'description': description.encode(),
                'max_execution_time': max_execution_time}
        if version is not None:
            data['version'] = version
        if backend_requirements:
            data['backendRequirements'] = json.dumps(backend_requirements)
        if parameters:
            data['parameters'] = json.dumps({"doc": parameters})
        if return_values:
            data['returnValues'] = json.dumps(return_values)
        if interim_results:
            data['interimResults'] = json.dumps(interim_results)

        if isinstance(program_data, str):
            with open(program_data, 'rb') as file:
                files = {'program': (name, file)}
                response = self.session.post(url, data=data, files=files).json()
        else:
            files = {'program': (name, program_data)}  # type: ignore[dict-item]
            response = self.session.post(url, data=data, files=files).json()
        return response

    def program_run(
            self,
            program_id: str,
            hub: str,
            group: str,
            project: str,
            backend_name: str,
            params: str,
    ) -> Dict:
        """Execute the program.

        Args:
            program_id: Program ID.
            hub: Hub to be used.
            group: Group to be used.
            project: Project to be used.
            backend_name: Name of the backend.
            params: Program parameters.

        Returns:
            JSON response.
        """
        url = self.get_url('jobs')
        payload = {
            'programId': program_id,
            'hub': hub,
            'group': group,
            'project': project,
            'backend': backend_name,
            'params': [params]
        }
        data = json.dumps(payload)
        return self.session.post(url, data=data).json()

    def jobs_get(self, limit: int = None, skip: int = None, pending: bool = None) -> Dict:
        """Get a list of job data.

        Args:
            limit: Number of results to return.
            skip: Number of results to skip.
            pending: Returns 'QUEUED' and 'RUNNING' jobs if True,
                returns 'DONE', 'CANCELLED' and 'ERROR' jobs if False.

        Returns:
            JSON response.
        """
        url = self.get_url('jobs')
        payload: Dict[str, Union[int, str]] = {}
        if limit:
            payload['limit'] = limit
        if skip:
            payload['offset'] = skip
        if pending is not None:
            payload['pending'] = 'true' if pending else 'false'
        return self.session.get(url, params=payload).json()

    def logout(self) -> None:
        """Clear authorization cache."""
        url = self.get_url('logout')
        self.session.post(url)


class Program(RestAdapterBase):
    """Rest adapter for program related endpoints."""

    URL_MAP = {
        'self': '',
        'data': '/data',
        'run': '/jobs',
        'private': '/private',
        'public': '/public'
    }

    _executor = futures.ThreadPoolExecutor()

    def __init__(self, session: RetrySession, program_id: str, url_prefix: str = '') -> None:
        """Job constructor.

        Args:
            session: Session to be used in the adapter.
            program_id: ID of the runtime program.
            url_prefix: Prefix to use in the URL.
        """
        super().__init__(session, '{}/programs/{}'.format(url_prefix, program_id))

    def get(self) -> Dict[str, Any]:
        """Return program information.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.get(url).json()

    def get_data(self) -> Dict[str, Any]:
        """Return program information, including data.

        Returns:
            JSON response.
        """
        url = self.get_url('data')
        return self.session.get(url).json()

    def make_public(self) -> None:
        """Sets a runtime program's visibility to public."""
        url = self.get_url('public')
        self.session.put(url)

    def make_private(self) -> None:
        """Sets a runtime program's visibility to private."""
        url = self.get_url('private')
        self.session.put(url)

    def delete(self) -> None:
        """Delete this program.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        self.session.delete(url)


class ProgramJob(RestAdapterBase):
    """Rest adapter for program job related endpoints."""

    URL_MAP = {
        'self': '',
        'results': '/results',
        'cancel': '/cancel',
        'logs': '/logs'
    }

    def __init__(
            self,
            session: RetrySession,
            job_id: str,
            url_prefix: str = ''
    ) -> None:
        """ProgramJob constructor.

        Args:
            session: Session to be used in the adapter.
            job_id: ID of the program job.
            url_prefix: Prefix to use in the URL.
        """
        super().__init__(session, '{}/jobs/{}'.format(
            url_prefix, job_id))

    def get(self) -> Dict:
        """Return program job information.

        Returns:
            JSON response.
        """
        return self.session.get(self.get_url('self')).json()

    def delete(self) -> None:
        """Delete program job."""
        self.session.delete(self.get_url('self'))

    def results(self) -> str:
        """Return program job results.

        Returns:
            Job results.
        """
        response = self.session.get(self.get_url('results'))
        return response.text

    def cancel(self) -> None:
        """Cancel the job."""
        self.session.post(self.get_url('cancel'))

    def logs(self) -> str:
        """Retrieve job logs.

        Returns:
            Job logs.
        """
        return self.session.get(self.get_url('logs')).text
