# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Root REST adapter."""

import logging
from typing import Dict, List, Any, Union, Optional
import json

from .base import RestAdapterBase
from .experiment import Experiment
from .analysis_result import AnalysisResult

logger = logging.getLogger(__name__)


class Api(RestAdapterBase):
    """Rest adapter for general endpoints."""

    URL_MAP = {
        'login': '/users/loginWithToken',
        'user_info': '/users/me',
        'hubs': '/Network',
        'version': '/version',
        'experiments': '/experiments',
        'experiment_devices': '/devices',
        'analysis_results': '/analysis_results',
        'device_components': '/device_components'
    }

# Function-specific rest adapters.

    def experiment(self, experiment_uuid: str) -> Experiment:
        """Return an adapter for the experiment.

        Args:
            experiment_uuid: UUID of the experiment.

        Returns:
            The experiment adapter.
        """
        return Experiment(self.session, experiment_uuid)

    def analysis_result(self, analysis_result_id: str) -> AnalysisResult:
        """Return an adapter for the analysis result.

        Args:
            analysis_result_id: UUID of the analysis result.

        Returns:
            The analysis result adapter.
        """
        return AnalysisResult(self.session, analysis_result_id)

# Client functions.

    def hubs(self) -> List[Dict[str, Any]]:
        """Return the list of hub/group/project sets available to the user.

        Returns:
            JSON response.
        """
        url = self.get_url('hubs')
        return self.session.get(url).json()

    def version(self) -> Dict[str, Union[str, bool]]:
        """Return the version information.

        Returns:
            A dictionary with information about the API version,
            with the following keys:

                * ``new_api`` (bool): Whether the new API is being used

            And the following optional keys:

                * ``api-*`` (str): The versions of each individual API component
        """
        url = self.get_url('version')
        response = self.session.get(url)

        try:
            version_info = response.json()
            version_info['new_api'] = True
        except json.JSONDecodeError:
            return {
                'new_api': False,
                'api': response.text
            }

        return version_info

    def login(self, api_token: str) -> Dict[str, Any]:
        """Login with token.

        Args:
            api_token: API token.

        Returns:
            JSON response.
        """
        url = self.get_url('login')
        return self.session.post(url, json={'apiToken': api_token}).json()

    def user_info(self) -> Dict[str, Any]:
        """Return user information.

        Returns:
            JSON response of user information.
        """
        url = self.get_url('user_info')
        response = self.session.get(url).json()

        return response

    # Experiment-related public functions.

    def experiments(self, backend_name: Optional[str] = None) -> List:
        """Return experiment data.

        Args:
            backend_name: Name of the backend.

        Returns:
            JSON response.
        """
        url = self.get_url('experiments')
        params = {}
        if backend_name:
            params['device_name'] = backend_name
        return self.session.get(url, params=params).json()

    def experiment_devices(self) -> List:
        """Return experiment devices.

        Returns:
            JSON response.
        """
        url = self.get_url('experiment_devices')
        raw_data = self.session.get(url).json()
        return raw_data

    def experiment_upload(self, experiment: Dict) -> Dict:
        """Upload an experiment.

        Args:
            experiment: The experiment to upload.

        Returns:
            JSON response.
        """
        url = self.get_url('experiments')
        raw_data = self.session.post(url, json=experiment).json()
        return raw_data

    def analysis_results(self, backend_name: Optional[str] = None) -> List:
        """Return all analysis results.

        Args:
            backend_name: Name of the backend.

        Returns:
            JSON response.
        """
        url = self.get_url('analysis_results')
        params = {}
        if backend_name:
            params['device_name'] = backend_name
        return self.session.get(url, params=params).json()

    def analysis_result_upload(self, result: Dict) -> Dict:
        """Upload an analysis result.

        Args:
            result: The analysis result to upload.

        Returns:
            JSON response.
        """
        url = self.get_url('analysis_results')
        # data = json.dumps(result)
        # print(f"upload data is {data}")
        return self.session.post(url, json=result).json()
        # return self.session.post(url, data=data).json()

    def device_components(self, backend_name: Optional[str] = None) -> List[Dict]:
        """Return a list of device components for the backend.

        Args:
            backend_name: Name of the backend.

        Returns:
            JSON response.
        """
        params = {}
        if backend_name:
            params['device_name'] = backend_name
        url = self.get_url('device_components')
        return self.session.get(url, params=params).json()
