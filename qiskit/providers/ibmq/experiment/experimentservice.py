# -*- coding: utf-8 -*-

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

"""IBM Quantum Experience experiment service."""

from typing import Optional, List, Dict, Union

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .experiment import Experiment
from .analysis_results import AnalysisResult
from ..utils.converters import local_to_utc
from ..api.clients.experiment import ExperimentClient


class ExperimentService:
    """Provides experiment related services."""

    def __init__(
            self,
            provider: 'accountprovider.AccountProvider',
            access_token: str
    ) -> None:
        """IBMQBackendService constructor.

        Args:
            provider: IBM Quantum Experience account provider.
            access_token: IBM Quantum Experience access token.
        """
        super().__init__()

        self._provider = provider
        self._api_client = ExperimentClient(access_token, provider.credentials)

    def backends(self) -> List[Dict]:
        """Return a list of backends.

        Returns:
            A list of backends.
        """
        return self._api_client.experiment_devices()

    def experiments(self, backend_name: Optional[str] = None) -> List[Experiment]:
        """Retrieve all experiments, with optional filtering.

        Args:
            backend_name: Backend name used for filtering.

        Returns:
            A list of experiments.
        """
        raw_data = self._api_client.experiments(backend_name)
        experiments = []
        # TODO get analysis results for the experiment.
        for exp in raw_data:
            experiments.append(Experiment.from_remote_data(exp))
        return experiments

    def upload_experiment(self, experiment: Experiment) -> None:
        """Upload a new experiment.

        Args:
            experiment: The experiment to upload.
        """
        data = {
            'device_name': experiment.backend_name,
            'type': experiment.type,
            'extra': experiment.extra,
        }
        if experiment.start_datetime:
            data['start_time'] = local_to_utc(experiment.start_datetime).isoformat()
        if experiment.tags:
            data['tags'] = experiment.tags
        if experiment.uuid:
            data['uuid'] = experiment.uuid
        response_data = self._api_client.experiment_upload(data)
        experiment.update_from_remote_data(response_data)

    def retrieve_experiment(self, experiment_id) -> Experiment:
        """Retrieve an experiment.

        Args:
            experiment_id: Experiment uuid.

        Returns:
            Retrieved experiment.
        """
        raw_data = self._api_client.experiment_get(experiment_id)
        experiment = Experiment.from_remote_data(raw_data)
        # TODO get analysis results for the experiment.
        return experiment

    def update_experiment(self, experiment: Experiment) -> None:
        """Update an experiment.

        Note:
            Only the following experiment attributes can be updated:

                * end_datetime

        Args:
            experiment: Experiment to be updated.
        """
        data = {}
        if experiment.end_datetime:
            data['end_time'] = experiment.end_datetime.isoformat()

        if not data:    # Nothing to update.
            return

        response = self._api_client.experiment_update(experiment.uuid, data)
        experiment.update_from_remote_data(response)

    def delete_experiment(self, experiment: Union[Experiment, str]) -> None:
        """Delete an experiment.

        Args:
            experiment: The ``Experiment`` object or the experiment UUID.

        Note:
            This method prompts for confirmation and requires a response before proceeding.
        """
        confirmation = input('\nAre you sure you want to delete the experiment? [y/N]: ')
        if confirmation not in ('y', 'Y'):
            return
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid
        self._api_client.experiment_delete(experiment)

    def analysis_results(self, backend_name: Optional[str] = None) -> List[AnalysisResult]:
        """Retrieve all analysis results, with optional filtering.

        Args:
            backend_name: Backend name used for filtering.

        Returns:
            A list of analysis results.
        """
        response = self._api_client.analysis_results(backend_name)
        results = []
        for result in response:
            results.append(AnalysisResult.from_remote_data(result))
        return results

    def upload_analysis_result(self, result: AnalysisResult) -> None:
        """Upload an analysis result.

        Args:
            result: The analysis result to upload.
        """
        data = {
            # 'device_name': 'NOV001',
            'device_components': result.device_components,
            'experiment_uuid': result.experiment_uuid,
            'fit': result.fit.to_dict(),
            'type': result.type
        }
        if result.chisq:
            data['chisq'] = result.chisq
        if result.quality:
            data['quality'] = result.quality.value
        if result.tags:
            data['tags'] = result.tags
        if result.uuid:
            data['uuid'] = result.uuid
        response = self._api_client.analysis_result_upload(data)
        result.update_from_remote_data(response)

    def update_analysis_result(self, result: AnalysisResult) -> None:
        """Update an analysis result.

        Args:
            result: The analysis result to upload.
        """
        data = {
            'fit': result.fit.to_dict(),
            'chisq': result.chisq,
            'quality': result.quality.value,
        }
        if result.tags:
            data['tags'] = result.tags
        response = self._api_client.analysis_result_update(result.uuid, data)
        result.update_from_remote_data(response)

    def upload_plot(self, experiment: Union[Experiment, str], plot_file_name: str) -> Dict:
        """Upload an experiment plot.

        Args:
            experiment: The ``Experiment`` object or the experiment UUID.
            plot_file_name: Name of the plot file.

        Returns:
            A dictionary with name and size of the uploaded plot file.
        """
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid
        return self._api_client.experiment_plot_upload(experiment, plot_file_name)

    def plots(self):
        raise NotImplementedError
