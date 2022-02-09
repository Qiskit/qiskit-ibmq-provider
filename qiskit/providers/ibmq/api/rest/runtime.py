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
from typing import Dict, Any, Union, Optional
import json
from concurrent import futures

from .base import RestAdapterBase
from ..session import RetrySession
from ...runtime.utils import RuntimeEncoder

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

    def list_programs(self, limit: int = None, skip: int = None) -> Dict[str, Any]:
        """Return a list of runtime programs.

        Args:
            limit: The number of programs to return.
            skip: The number of programs to skip.

        Returns:
            A list of runtime programs.
        """
        url = self.get_url('programs')
        payload: Dict[str, int] = {}
        if limit:
            payload['limit'] = limit
        if skip:
            payload['offset'] = skip
        return self.session.get(url, params=payload).json()

    def create_program(
            self,
            program_data: str,
            name: str,
            description: str,
            max_execution_time: int,
            is_public: Optional[bool] = False,
            spec: Optional[Dict] = None
    ) -> Dict:
        """Upload a new program.

        Args:
            program_data: Program data (base64 encoded).
            name: Name of the program.
            description: Program description.
            max_execution_time: Maximum execution time.
            is_public: Whether the program should be public.
            spec: Backend requirements, parameters, interim results, return values, etc.

        Returns:
            JSON response.
        """
        url = self.get_url('programs')
        payload = {'name': name,
                   'data': program_data,
                   'cost': max_execution_time,
                   'description': description,
                   'is_public': is_public}
        if spec is not None:
            payload['spec'] = spec
        data = json.dumps(payload)
        return self.session.post(url, data=data).json()

    def program_run(
            self,
            program_id: str,
            hub: str,
            group: str,
            project: str,
            backend_name: str,
            params: Dict,
            image: str,
            log_level: Optional[str] = None
    ) -> Dict:
        """Execute the program.

        Args:
            program_id: Program ID.
            hub: Hub to be used.
            group: Group to be used.
            project: Project to be used.
            backend_name: Name of the backend.
            params: Program parameters.
            image: Runtime image.
            log_level: Log level to use.

        Returns:
            JSON response.
        """
        url = self.get_url('jobs')
        payload = {
            'program_id': program_id,
            'hub': hub,
            'group': group,
            'project': project,
            'backend': backend_name,
            'params': params,
            'runtime': image
        }
        if log_level:
            payload["log_level"] = log_level
        data = json.dumps(payload, cls=RuntimeEncoder)
        return self.session.post(url, data=data).json()

    def jobs_get(
            self,
            limit: int = None,
            skip: int = None,
            pending: bool = None,
            program_id: str = None
    ) -> Dict:
        """Get a list of job data.

        Args:
            limit: Number of results to return.
            skip: Number of results to skip.
            pending: Returns 'QUEUED' and 'RUNNING' jobs if True,
                returns 'DONE', 'CANCELLED' and 'ERROR' jobs if False.
            program_id: Filter by Program ID.

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
        if program_id:
            payload['program'] = program_id
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

    def update_data(self, program_data: str) -> None:
        """Update program data.

        Args:
            program_data: Program data (base64 encoded).
        """
        url = self.get_url("data")
        self.session.put(url, data=program_data,
                         headers={'Content-Type': 'application/octet-stream'})

    def update_metadata(
            self,
            name: str = None,
            description: str = None,
            max_execution_time: int = None,
            spec: Optional[Dict] = None
    ) -> None:
        """Update program metadata.

        Args:
            name: Name of the program.
            description: Program description.
            max_execution_time: Maximum execution time.
            spec: Backend requirements, parameters, interim results, return values, etc.
        """
        url = self.get_url("self")
        payload: Dict = {}
        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        if max_execution_time:
            payload["cost"] = max_execution_time
        if spec:
            payload["spec"] = spec

        self.session.patch(url, json=payload)


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
