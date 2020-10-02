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
from typing import Dict, List, Any, Union, Optional, Tuple
import json

from .base import RestAdapterBase
from .experiment import Experiment, ExperimentPlot
from .analysis_result import AnalysisResult

logger = logging.getLogger(__name__)


class Api(RestAdapterBase):
    """Rest adapter for general endpoints."""

    URL_MAP = {
        'login': '/users/loginWithToken',
        'user_info': '/users/me',
        'hubs': '/Network',
        'version': '/version',
        'bookings': '/Network/bookings/v2',
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

    def experiment_plot(self, experiment_uuid: str, plot_name: str) -> ExperimentPlot:
        """

        Args:
            experiment_uuid: UUID of the experiment.
            plot_name: Name of the experiment plot.

        Returns:
            The experiment plot adapter.
        """
        return ExperimentPlot(self.session, experiment_uuid, plot_name)

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

    def reservations(self) -> List:
        """Return reservation information.

        Returns:
            JSON response.
        """
        url = self.get_url('bookings')
        return self.session.get(url).json()

    # Experiment-related public functions.

    def experiments(
            self,
            backend_name: Optional[str] = None,
            experiment_type: Optional[str] = None,
            start_time: Optional[List] = None,
            device_components: Optional[List[str]] = None,
            tags: Optional[List[str]] = None
    ) -> List:
        """Return experiment data.

        Args:
            backend_name: Name of the backend.
            experiment_type: Experiment type.
            start_time: A list of timestamps used to filter by experiment start time.
            device_components: A list of device components used for filtering.
            tags: Tags used for filtering.

        Returns:
            JSON response.
        """
        url = self.get_url('experiments')
        params = {}  # type: Dict[str, Any]
        if backend_name:
            params['device_name'] = backend_name
        if experiment_type:
            params['type'] = experiment_type
        if start_time:
            params['start_time'] = start_time
        if device_components:
            params['device_components'] = device_components
        if tags:
            params['tags'] = tags
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

    def analysis_results(
            self,
            backend_name: Optional[str] = None,
            device_components: Optional[List[str]] = None,
            experiment_uuid: Optional[str] = None,
            result_type: Optional[str] = None,
            quality: Optional[List[str]] = None
    ) -> List:
        """Return all analysis results.

        Args:
            backend_name: Name of the backend.
            device_components: A list of device components used for filtering.
            experiment_uuid: Experiment UUID used for filtering.
            result_type: Analysis result type used for filtering.
            quality: Quality value used for filtering.

        Returns:
            JSON response.
        """
        url = self.get_url('analysis_results')
        params = {}  # type: Dict[str, Any]
        if backend_name:
            params['device_name'] = backend_name
        if device_components:
            params['device_components'] = device_components
        if experiment_uuid:
            params['experiment_uuid'] = experiment_uuid
        if quality:
            params['quality'] = quality
        if result_type:
            params['type'] = result_type
        return self.session.get(url, params=params).json()

    def analysis_result_upload(self, result: Dict) -> Dict:
        """Upload an analysis result.

        Args:
            result: The analysis result to upload.

        Returns:
            JSON response.
        """
        url = self.get_url('analysis_results')
        return self.session.post(url, json=result).json()

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
