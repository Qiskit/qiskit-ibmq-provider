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

"""Client for accessing IBM Quantum Experience experiment services."""

import logging
from typing import List, Dict, Optional, Union, Tuple

from qiskit.providers.ibmq.credentials import Credentials

from ..rest import Api
from ..session import RetrySession
from .base import BaseClient

logger = logging.getLogger(__name__)


class ExperimentClient(BaseClient):
    """Client for accessing IBM Quantum Experience experiment services."""

    def __init__(
            self,
            access_token: str,
            credentials: Credentials
    ) -> None:
        """ExperimentClient constructor.

        Args:
            access_token: IBM Quantum Experience access token.
            credentials: Account credentials.
        """
        self._session = RetrySession(credentials.experiment_url, access_token,
                                     **credentials.connection_parameters())
        self.base_api = Api(self._session)

    def experiments(
            self,
            backend_name: Optional[str],
            experiment_type: Optional[str] = None,
            start_time: Optional[List] = None,
            device_components: Optional[List[str]] = None,
            tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """Retrieve experiments, with optional filtering.

        Args:
            backend_name: Name of the backend.
            experiment_type: Experiment type.
            start_time: A list of timestamps used to filter by experiment start time.
            device_components: A list of device components used for filtering.
            tags: Tags used for filtering.

        Returns:
            A list of experiments.
        """
        return self.base_api.experiments(
            backend_name, experiment_type, start_time, device_components, tags)

    def experiment_get(self, experiment_id: str) -> Dict:
        """Get a specific experiment.

        Args:
            experiment_id: Experiment uuid.

        Returns:
            Experiment data.
        """
        return self.base_api.experiment(experiment_id).retrieve()

    def experiment_upload(self, data: Dict) -> Dict:
        """Upload an experiment.

        Args:
            data: Experiment data.

        Returns:
            Experiment data.
        """
        return self.base_api.experiment_upload(data)

    def experiment_update(self, experiment_id: str, new_data: Dict) -> Dict:
        """Update an experiment.

        Args:
            experiment_id: Experiment UUID.
            new_data: New experiment data.

        Returns:
            Experiment data.
        """
        return self.base_api.experiment(experiment_id).update(new_data)

    def experiment_delete(self, experiment_id: str) -> Dict:
        """Delete an experiment.

        Args:
            experiment_id: Experiment UUID.

        Returns:
            Experiment data.
        """
        return self.base_api.experiment(experiment_id).delete()

    def experiment_plot_upload(
            self,
            experiment_id: str,
            plot: Union[bytes, str],
            plot_name: str
    ) -> Dict:
        """Upload an experiment plot.

        Args:
            experiment_id: Experiment UUID.
            plot: Plot file name or data to upload.
            plot_name: Name of the plot.

        Returns:
            JSON response.
        """
        return self.base_api.experiment(experiment_id).upload_plot(plot, plot_name)

    def experiment_plot_update(
            self,
            experiment_id: str,
            plot: Union[bytes, str],
            plot_name: str
    ) -> Dict:
        """Update an experiment plot.

        Args:
            experiment_id: Experiment UUID.
            plot: Plot file name or data to upload.
            plot_name: Name of the plot.

        Returns:
            JSON response.
        """
        return self.base_api.experiment_plot(experiment_id, plot_name).update(plot)

    def experiment_plot_get(self, experiment_id: str, plot_name: str) -> bytes:
        """Retrieve an experiment plot.

        Args:
            experiment_id: Experiment UUID.
            plot_name: Name of the plot.

        Returns:
            Retrieved experiment plot.
        """
        return self.base_api.experiment_plot(experiment_id, plot_name).retrieve()

    def experiment_plot_delete(self, experiment_id: str, plot_file_name: str) -> None:
        """Delete an experiment plot.

        Args:
            experiment_id: Experiment UUID.
            plot_file_name: Plot file name.
        """
        self.base_api.experiment_plot(experiment_id, plot_file_name).delete()

    def experiment_devices(self) -> List:
        """Return list of experiment devices.

        Returns:
            A list of experiment devices.
        """
        return self.base_api.experiment_devices()

    def analysis_results(
            self,
            backend_name: Optional[str] = None,
            device_components: Optional[List[str]] = None,
            experiment_uuid: Optional[str] = None,
            result_type: Optional[str] = None,
            quality: Optional[List[str]] = None
    ) -> List[Dict]:
        """Return a list of analysis results.

        Args:
            backend_name: Name of the backend.
            device_components: A list of device components used for filtering.
            experiment_uuid: Experiment UUID used for filtering.
            result_type: Analysis result type used for filtering.
            quality: Quality value used for filtering.

        Returns:
            A list of analysis results.
        """
        return self.base_api.analysis_results(
            backend_name, device_components, experiment_uuid, result_type, quality)

    def analysis_result_upload(self, result: Dict) -> Dict:
        """Upload an analysis result.

        Args:
            result: The analysis result to upload.

        Returns:
            Analysis result data.
        """
        return self.base_api.analysis_result_upload(result)

    def analysis_result_update(self, result_id: str, new_data: Dict) -> Dict:
        """Update an analysis result.

        Args:
            result_id: Analysis result ID.
            new_data: New analysis result data.

        Returns:
            Analysis result data.
        """
        return self.base_api.analysis_result(result_id).update(new_data)

    def analysis_result_delete(self, result_id: str) -> Dict:
        """Delete an analysis result.

        Args:
            result_id: Analysis result ID.

        Returns:
            Analysis result data.
        """
        return self.base_api.analysis_result(result_id).delete()

    def analysis_result_get(self, result_id: str) -> Dict:
        """Retrieve an analysis result.

        Args:
            result_id: Analysis result ID.

        Returns:
            Analysis result data.
        """
        return self.base_api.analysis_result(result_id).get()

    def device_components(self, backend_name: Optional[str]) -> List[Dict]:
        """Return device components for the backend.

        Args:
            backend_name: Name of the backend.

        Returns:
            A list of device components.
        """
        return self.base_api.device_components(backend_name)
