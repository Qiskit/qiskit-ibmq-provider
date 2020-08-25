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
from datetime import datetime

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .experiment import Experiment
from .analysis_result import AnalysisResult, DeviceComponent
from .exceptions import ExperimentNotFoundError
from ..utils.converters import local_to_utc_str
from ..api.clients.experiment import ExperimentClient
from ..api.exceptions import RequestsApiError


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

    def experiments(
            self,
            backend_name: Optional[str] = None,
            type: Optional[str] = None,
            start_datetime: Optional[datetime] = None,
            end_datetime: Optional[datetime] = None
    ) -> List[Experiment]:
        """Retrieve all experiments, with optional filtering.

        Args:
            backend_name: Backend name used for filtering.
            type: Experiment type used for filtering.
            start_datetime: Filter by the given start timestamp, in local time. This is used to
                find experiments whose start date/time is after (greater than or equal to) this
                local timestamp.
            end_datetime: Filter by the given end timestamp, in local time. This is used to
                find experiments whose start date/time is before (less than or equal to) this
                local timestamp.

        Returns:
            A list of experiments.
        """
        start_time_filters = []
        if start_datetime:
            st_filter = 'ge:{}'.format(local_to_utc_str(start_datetime))
            start_time_filters.append(st_filter)
        if end_datetime:
            st_filter = 'le:{}'.format(local_to_utc_str(end_datetime))
            start_time_filters.append(st_filter)

        raw_data = self._api_client.experiments(backend_name, type, start_time_filters)
        experiments = []
        # TODO get analysis results for the experiment.
        for exp in raw_data:
            experiments.append(Experiment.from_remote_data(self._provider, exp))
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
            data['start_time'] = local_to_utc_str(experiment.start_datetime)
        if experiment.tags:
            data['tags'] = experiment.tags
        if experiment.uuid:
            data['uuid'] = experiment.uuid
        response_data = self._api_client.experiment_upload(data)
        experiment.update_from_remote_data(response_data)

    def retrieve_experiment(self, experiment_id: str) -> Experiment:
        """Retrieve an experiment.

        Args:
            experiment_id: Experiment uuid.

        Returns:
            Retrieved experiment.
        """
        raw_data = self._api_client.experiment_get(experiment_id)
        experiment = Experiment.from_remote_data(self._provider, raw_data)
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

    def delete_experiment(self, experiment: Union[Experiment, str]) -> Optional[Experiment]:
        """Delete an experiment.

        Args:
            experiment: The ``Experiment`` object or the experiment UUID.

        Note:
            This method prompts for confirmation and requires a response before proceeding.

        Returns:
            Deleted experiment.
        """
        confirmation = input('\nAre you sure you want to delete the experiment? '
                             'Results and plots for the experiment will also be deleted. [y/N]: ')
        if confirmation not in ('y', 'Y'):
            return None
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid
        raw_data = self._api_client.experiment_delete(experiment)
        return Experiment.from_remote_data(self._provider, raw_data)

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

    def retrieve_analysis_result(self, result_id: str) -> AnalysisResult:
        """Retrieve an analysis result.

        Args:
            result_id: Analysis result UUID.

        Returns:
            Retrieved analysis result.
        """
        try:
            data = self._api_client.analysis_result_get(result_id)
        except RequestsApiError as err:
            if 'Analysis result not found' in err.message:
                raise ExperimentNotFoundError(err.message)
            raise
        return AnalysisResult.from_remote_data(data)

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

    def delete_analysis_result(
            self,
            result: Union[AnalysisResult, str]
    ) -> Optional[AnalysisResult]:
        """Delete an analysis result.

        Args:
            result: The ``AnalysisResult`` object or the analysis result UUID.

        Note:
            This method prompts for confirmation and requires a response before proceeding.

        Returns:
            The deleted analysis result.
        """
        confirmation = input('\nAre you sure you want to delete the analysis result? [y/N]: ')
        if confirmation not in ('y', 'Y'):
            return None
        if isinstance(result, AnalysisResult):
            result = result.uuid
        deleted = self._api_client.analysis_result_delete(result)
        return AnalysisResult.from_remote_data(deleted)

    def upload_plot(
            self,
            experiment: Union[Experiment, str],
            plot: Union[str, bytes],
            plot_name: Optional[str] = None
    ) -> Dict:
        """Upload an experiment plot.

        Args:
            experiment: The ``Experiment`` object or the experiment UUID.
            plot: Name of the plot file or plot data to upload.
            plot_name: Name of the plot. If ``None``, the plot file name, if
                given, or a generated name is used.

        Returns:
            A dictionary with name and size of the uploaded plot.
        """
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid

        if plot_name is None:
            if isinstance(plot, str):
                plot_name = plot
            else:
                plot_name = "plot_{}.svg".format(datetime.now().isoformat())
        return self._api_client.experiment_plot_upload(experiment, plot, plot_name)

    def delete_plot(
            self,
            experiment: Union[Experiment, str],
            plot_name: str
    ) -> None:
        """Delete an experiment plot.

        Note:
            This method prompts for confirmation and requires a response before proceeding.

        Args:
            experiment: The ``Experiment`` object or the experiment UUID.
            plot_name: Name of the plot.
        """
        confirmation = input('\nAre you sure you want to delete the experiment plot? [y/N]: ')
        if confirmation not in ('y', 'Y'):
            return None
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid
        self._api_client.experiment_plot_delete(experiment, plot_name)

    def retrieve_plot(
            self,
            experiment: Union[Experiment, str],
            plot_name: str,
            file_name: Optional[str] = None
    ) -> Union[int, bytes]:
        """Retrieve an experiment plot.

        Args:
            experiment: The ``Experiment`` object or the experiment UUID.
            plot_name: Name of the plot.
            file_name: Name of the local file to save the plot to. If ``None``,
                the content of the plot is returned instead.

        Returns:
            The size of the plot if `file_name` is specified. Otherwise the
            content of the plot in bytes.
        """
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid
        data = self._api_client.experiment_plot_get(experiment, plot_name)
        if file_name:
            with open(file_name, 'wb') as f:
                num_bytes = f.write(data)
            return num_bytes
        return data

    def plots(self):
        """Retrieve all plots."""
        raise NotImplementedError

    def device_components(self, backend_name: Optional[str] = None) -> List[DeviceComponent]:
        """Return the device components.

        Args:
            backend_name: Name of the backend whose components are to be retrieved.

        Returns:
            A list of device components.
        """
        raw_data = self._api_client.device_components(backend_name)
        components = []
        for data in raw_data:
            components.append(DeviceComponent(backend_name=data['device_name'],
                                              type=data['type'],
                                              uuid=data['uuid']))
        return components
