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

"""Client for accessing an individual IBM Quantum Experience account."""

import asyncio
import logging
import time

from typing import List, Dict, Any, Optional, Union
# Disabled unused-import because datetime is used only for type hints.
from datetime import datetime  # pylint: disable=unused-import

from qiskit.providers.ibmq.apiconstants import (API_JOB_FINAL_STATES, ApiJobStatus,
                                                ApiJobShareLevel)
from qiskit.providers.ibmq.utils.utils import RefreshQueue
from qiskit.providers.ibmq.credentials import Credentials

from ..exceptions import (RequestsApiError, WebsocketError,
                          WebsocketTimeoutError, UserTimeoutExceededError)
from ..rest import Api, Account
from ..session import RetrySession
from ..exceptions import ApiIBMQProtocolError
from .base import BaseClient
from .websocket import WebsocketClient

logger = logging.getLogger(__name__)


class ExperimentClient(BaseClient):
    """Client for accessing an individual IBM Quantum Experience account."""

    def __init__(
            self,
            access_token: str,
            credentials: Credentials,
    ) -> None:
        """AccountClient constructor.

        Args:
            access_token: IBM Quantum Experience access token.
            credentials: Account credentials.
        """
        self._session = RetrySession(credentials.experiment_url, access_token,
                                     **credentials.connection_parameters())
        self.base_api = Api(self._session)

    def experiments(self, backend_name: Optional[str]) -> List[Dict]:
        """Retrieve experiments, with optional filtering.

        Args:
            backend_name: Name of the backend.

        Returns:
            A list of experiments.
        """
        return self.base_api.experiments(backend_name)

    def experiment_get(self, experiment_id: str) -> Dict[str, Any]:
        """Get a specific experiment.

        Args:
            experiment_id: Experiment uuid.

        Returns:
            Experiment data.
        """
        return self.base_api.experiment(experiment_id).retrieve()

    def experiment_upload(self, data):
        """Upload an experiment.

        Args:
            data: Experiment data.

        Returns:
            JSON response.
        """
        return self.base_api.experiment_upload(data)

    def experiment_update(self, experiment_id, new_data):
        """Update an experiment.

        Args:
            experiment_id: Experiment uuid.
            new_data: New experiment data.

        Returns:
            JSON response.
        """
        return self.base_api.experiment(experiment_id).update(new_data)

    def experiment_delete(self, experiment_id):
        """Delete an experiment.

        Args:
            experiment_id: Experiment uuid.
        """
        return self.base_api.experiment(experiment_id).delete()

    def experiment_plot_upload(self, experiment_id: str, plot_file_name: str):
        """Upload an experiment plot.

        Args:
            experiment_id: Experiment uuid.
            plot_file_name: Plot file name.

        Returns:
            JSON response.
        """
        return self.base_api.experiment(experiment_id).upload_plot(plot_file_name)

    def experiment_devices(self) -> List:
        """Return list of experiment devices.

        Returns:
            A list of experiment devices.
        """
        return self.base_api.experiment_devices()

    def analysis_results(self, backend_name: Optional[str]) -> List[Dict]:
        """Return a list of analysis results.

        Args:
            backend_name: Name of the backend.

        Returns:
            A list of analysis results.
        """
        return self.base_api.analysis_results(backend_name)

    def analysis_result_upload(self, result) -> Dict:
        """Upload an analysis result.

        Args:
            result: The analysis result to upload.

        Returns:
            JSON response.
        """
        return self.base_api.analysis_result_upload(result)

    def analysis_result_update(self, result_id, new_data):
        """Update an analysis result.

        Args:
            result_id: Analysis result ID.
            new_data: New analysis result data.

        Returns:
            JSON response.
        """
        return self.base_api.analysis_result(result_id).update(new_data)
