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
from typing import List, Dict, Optional, Union

from qiskit.providers.ibmq.credentials import Credentials

from ..rest import Api
from ..session import RetrySession
from .base import BaseClient

logger = logging.getLogger(__name__)


class ExperimentClient(BaseClient):
    """Client for accessing IBM Quantum Experience experiment services."""

    def __init__(
            self,
            credentials: Credentials
    ) -> None:
        """ExperimentClient constructor.

        Args:
            credentials: Account credentials.
        """
        self._session = RetrySession(credentials.experiment_url, credentials.access_token,
                                     **credentials.connection_parameters())
        self.base_api = Api(self._session)

    def experiments(
            self,
            limit: Optional[int],
            marker: Optional[str],
            backend_name: Optional[str],
            experiment_type: Optional[str] = None,
            start_time: Optional[List] = None,
            device_components: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
            hub: Optional[str] = None,
            group: Optional[str] = None,
            project: Optional[str] = None,
            exclude_public: Optional[bool] = False,
            public_only: Optional[bool] = False,
            exclude_mine: Optional[bool] = False,
            mine_only: Optional[bool] = False,
            parent_id: Optional[str] = None,
            sort_by: Optional[str] = None
    ) -> str:
        """Retrieve experiments, with optional filtering.

        Args:
            limit: Number of experiments to retrieve.
            marker: Marker used to indicate where to start the next query.
            backend_name: Name of the backend.
            experiment_type: Experiment type.
            start_time: A list of timestamps used to filter by experiment start time.
            device_components: A list of device components used for filtering.
            tags: Tags used for filtering.
            hub: Filter by hub.
            group: Filter by hub and group.
            project: Filter by hub, group, and project.
            exclude_public: Whether or not to exclude experiments with a public share level.
            public_only: Whether or not to only return experiments with a public share level.
            exclude_mine: Whether or not to exclude experiments where I am the owner.
            mine_only: Whether or not to only return experiments where I am the owner.
            parent_id: Filter by parent experiment ID.
            sort_by: Sorting order.

        Returns:
            A list of experiments and the marker, if applicable.
        """
        resp = self.base_api.experiments(
            limit=limit,
            marker=marker,
            backend_name=backend_name,
            experiment_type=experiment_type,
            start_time=start_time,
            device_components=device_components,
            tags=tags,
            hub=hub, group=group, project=project,
            exclude_public=exclude_public, public_only=public_only,
            exclude_mine=exclude_mine, mine_only=mine_only,
            parent_id=parent_id,
            sort_by=sort_by)
        return resp

    def experiment_get(self, experiment_id: str) -> str:
        """Get a specific experiment.

        Args:
            experiment_id: Experiment uuid.

        Returns:
            Experiment data.
        """
        return self.base_api.experiment(experiment_id).retrieve()

    def experiment_upload(self, data: str) -> Dict:
        """Upload an experiment.

        Args:
            data: Experiment data.

        Returns:
            Experiment data.
        """
        return self.base_api.experiment_upload(data)

    def experiment_update(self, experiment_id: str, new_data: str) -> Dict:
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
            plot_name: str,
            sync_upload: bool = True
    ) -> Dict:
        """Upload an experiment plot.

        Args:
            experiment_id: Experiment UUID.
            plot: Plot file name or data to upload.
            plot_name: Name of the plot.
            sync_upload: By default the server will upload the plot file
                to backend storage asynchronously. Set this to False to use
                that behavior and not block the upload.

        Returns:
            JSON response.
        """
        return self.base_api.experiment(
            experiment_id).upload_plot(
                plot, plot_name, sync_upload=sync_upload)

    def experiment_plot_update(
            self,
            experiment_id: str,
            plot: Union[bytes, str],
            plot_name: str,
            sync_upload: bool = True
    ) -> Dict:
        """Update an experiment plot.

        Args:
            experiment_id: Experiment UUID.
            plot: Plot file name or data to upload.
            plot_name: Name of the plot.
            sync_upload: By default the server will upload the plot file
                to backend storage asynchronously. Set this to False to use
                that behavior and not block the upload.

        Returns:
            JSON response.
        """
        return self.base_api.experiment_plot(
            experiment_id, plot_name).update(
                plot, sync_upload=sync_upload)

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
        return self.base_api.experiment_devices()['devices']

    def analysis_results(
            self,
            limit: Optional[int],
            marker: Optional[str],
            backend_name: Optional[str] = None,
            device_components: Optional[List[str]] = None,
            experiment_uuid: Optional[str] = None,
            result_type: Optional[str] = None,
            quality: Optional[Union[str, List[str]]] = None,
            verified: Optional[bool] = None,
            tags: Optional[List[str]] = None,
            sort_by: Optional[str] = None
    ) -> str:
        """Return a list of analysis results.

        Args:
            limit: Number of analysis results to retrieve.
            marker: Marker used to indicate where to start the next query.
            backend_name: Name of the backend.
            device_components: A list of device components used for filtering.
            experiment_uuid: Experiment UUID used for filtering.
            result_type: Analysis result type used for filtering.
            quality: Quality value used for filtering.
            verified: Indicates whether this result has been verified.
            tags: Filter by tags assigned to analysis results.
            sort_by: Indicates how the output should be sorted.

        Returns:
            A list of analysis results and the marker, if applicable.
        """
        resp = self.base_api.analysis_results(
            limit=limit,
            marker=marker,
            backend_name=backend_name,
            device_components=device_components,
            experiment_uuid=experiment_uuid,
            result_type=result_type,
            quality=quality,
            verified=verified,
            tags=tags,
            sort_by=sort_by
        )
        return resp

    def analysis_result_upload(self, result: str) -> Dict:
        """Upload an analysis result.

        Args:
            result: The analysis result to upload.

        Returns:
            Analysis result data.
        """
        return self.base_api.analysis_result_upload(result)

    def analysis_result_update(self, result_id: str, new_data: str) -> Dict:
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

    def analysis_result_get(self, result_id: str) -> str:
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
        resp = self.base_api.device_components(backend_name)
        return resp['device_components']
