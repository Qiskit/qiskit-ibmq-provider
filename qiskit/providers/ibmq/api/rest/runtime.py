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
from typing import Dict, List, Any, Optional
import json
import subprocess
import os
import queue
from concurrent import futures
import uuid

from qiskit.providers.ibmq.utils.runtime import RuntimeDecoder

from .base import RestAdapterBase
from ..session import RetrySession

logger = logging.getLogger(__name__)
process = None


class Runtime(RestAdapterBase):
    """Rest adapter for RNG related endpoints."""

    URL_MAP = {
        'self': '/programs'
    }

    def program(self, program_id: str) -> 'Program':
        """Return an adapter for the program.

        Args:
            program_id: ID of the program.

        Returns:
            The program adapter.
        """
        return Program(self.session, program_id)

    def program_job(self, program_id, job_id):
        return ProgramJob(self.session, program_id, job_id)

    def list_programs(self) -> List[Dict]:
        """Return a list of runtime programs.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        # return self.session.get(url).json()
        # temporary code
        doc_file = os.getenv('NTC_DOC_FILE', 'runtime/qka_doc.json')
        with open(doc_file, 'r') as file:
            data = json.load(file)
        return [data]

    def create_program(self, name: str, data: bytes) -> Dict:
        """Upload a new program.

        Args:
            name: Name of the program.
            data: Program data.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        data = {'name': name,
                'program': (name, data)}  # type: ignore[dict-item]
        return self.session.post(url, files=data).json()


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

    def run(
            self,
            hub: str,
            group: str,
            project: str,
            backend_name: str,
            params: str,
            interim_queue: Optional[queue.Queue] = None
    ) -> Dict:
        """Execute the program.

        Args:
            hub: Hub to be used.
            group: Group to be used.
            project: Project to be used.
            backend_name: Name of the backend.
            params: Program parameters.

        Returns:
            JSON response.
        """
        url = self.get_url('run')
        payload = {
            'hub': hub,
            'group': group,
            'project': project,
            'backend': backend_name,
            'params': params
        }
        # data = json.dumps(payload, cls=json_encoder.IQXJsonEncoder)
        # temporary code
        python_bin = os.getenv('PYTHON_EXEC', 'python3')
        program_file = os.getenv('NTC_PROGRAM_FILE', 'runtime/qka_program.py')
        global process
        process = subprocess.Popen([python_bin, program_file, params],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True)
        if interim_queue:
            self._executor.submit(self._interim_result, interim_queue, process)

        return {'id': uuid.uuid4().hex}
        # return self.session.post(url, data=data).json()

    def _interim_result(self, interim_queue: queue.Queue, pgm_process):
        while True:
            nextline = pgm_process.stdout.readline()
            if nextline == '' and pgm_process.poll() is not None:
                break
            try:
                parsed = json.loads(nextline, cls=RuntimeDecoder)
                if any(text in parsed for text in ['post', 'results']):
                    interim_queue.put_nowait(parsed)
            except:
                print(nextline)
        interim_queue.put_nowait('poison_pill')

    def delete(self) -> Dict:
        """Delete this program.

        Returns:
            JSON response.
        """
        url = self.get_url('self')
        return self.session.delete(url).json()


class ProgramJob(RestAdapterBase):
    """Rest adapter for program job related endpoints."""

    URL_MAP = {
        'self': '',
        'results': 'results'
    }

    def __init__(
            self,
            session: RetrySession,
            program_id: str,
            job_id: str,
            url_prefix: str = ''
    ) -> None:
        """ProgramJob constructor.

        Args:
            session: Session to be used in the adapter.
            program_id: ID of the runtime program.
            job_id: ID of the program job.
            url_prefix: Prefix to use in the URL.
        """
        super().__init__(session, '{}/programs/{}/jobs/{}'.format(
            url_prefix, program_id, job_id))

    def get(self) -> Dict:
        """Return program job information.

        Returns:
            JSON response.
        """
        output = {}
        global process
        if process is not None:
            rc = process.poll()
            if rc is None:
                output['status'] = 'RUNNING'
            elif rc < 0:
                output['status'] = 'ERROR'
            else:
                output['status'] = 'DONE'
        return output
        # return self.session.get(self.get_url('self')).json()

    def delete(self) -> Dict:
        """Delete program job.

        Returns:
            JSON response.
        """
        return self.session.delete(self.get_url('self')).json()

    def results(self) -> Dict:
        """Return program job results.

        Returns:
            JSON response.
        """
        global process
        if process is not None:
            outs, errs = process.communicate()
            outs = outs.split('\n')
            for line in outs:
                try:
                    parsed = json.loads(line, cls=RuntimeDecoder)
                    if 'results' in parsed:
                        return parsed['results']
                except:
                    print(line)

        return {}
        # return self.session.get(self.get_url('results')).json()
