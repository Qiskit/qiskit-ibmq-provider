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

"""Random REST adapter."""

import logging
from typing import Dict, List, Any, Union
import json
from concurrent import futures

from .base import RestAdapterBase
from ..session import RetrySession

logger = logging.getLogger(__name__)


class Runtime(RestAdapterBase):
    """Rest adapter for Runtime base endpoints."""

    URL_MAP = {
        'programs': '/programs',
        'jobs': '/jobs'
    }

    def program(self, program_id: str) -> 'Program':
        """Return an adapter for the program.

        Args:
            program_id: ID of the program.

        Returns:
            The program adapter.
        """
        return Program(self.session, program_id)

    def program_job(self, job_id: str) -> None:
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
            program_name: str,
            program_data: Union[bytes, str],
            max_execution_time: int
    ) -> Dict:
        """Upload a new program.

        Args:
            program_name: Name of the program.
            program_data: Program data.
            max_execution_time: Maximum execution time.

        Returns:
            JSON response.
        """
        url = self.get_url('programs')
        data = {'name': (None, program_name),
                'cost': (None, str(max_execution_time))}
        if isinstance(program_data, str):
            with open(program_data, 'rb') as file:
                data['program'] = (program_name, file)
                response = self.session.post(url, files=data).json()
        else:
            data['program'] = (program_name, program_data)
            response = self.session.post(url, files=data).json()
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


class Program(RestAdapterBase):
    """Rest adapter for program related endpoints."""

    URL_MAP = {
        'self': '',
        'data': '/data',
        'run': '/jobs'
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
        'cancel': '/cancel'
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

    def delete(self) -> Dict:
        """Delete program job.

        Returns:
            JSON response.
        """
        return self.session.delete(self.get_url('self')).json()

    def results(self) -> str:
        """Return program job results.

        Returns:
            JSON response.
        """
        response = self.session.get(self.get_url('results'))
        return response.text

    def cancel(self) -> None:
        """Cancel the job."""
        self.session.post(self.get_url('cancel'))
