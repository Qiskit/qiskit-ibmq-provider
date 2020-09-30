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

from typing import Optional, List, Dict, Union, Tuple, Any
from datetime import datetime

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .experiment import Experiment
from .analysis_result import AnalysisResult, DeviceComponent
from .exceptions import ExperimentNotFoundError, AnalysisResultNotFoundError, PlotNotFoundError
from .constants import ResultQuality
from ..utils.converters import local_to_utc_str
from ..api.clients.experiment import ExperimentClient
from ..api.exceptions import RequestsApiError


class ExperimentService:
    """Provides experiment related services.

    This class is the main interface to invoke IBM Quantum Experience
    experiment services, which allow you to create, delete, update, query, and
    retrieve experiments, experiment plots, and analysis results. The
    ``experiment`` attribute of
    :class:`~qiskit.providers.ibmq.accountprovider.AccountProvider` is an
    instance of this class, and the main syntax for using the services is
    ``provider.experiment.<action>``. For example::

        from qiskit import IBMQ
        provider = IBMQ.load_account()

        # Retrieve all experiments.
        experiments = provider.experiment.experiments()

        # Retrieve experiments with filtering.
        experiment_filtered = provider.experiment.experiments(backend_name='foo')

        # Retrieve a specific experiment using its ID.
        experiment = provider.experiment.retrieve_experiment(EXPERIMENT_ID)

        # Upload a new experiment.
        from qiskit.providers.ibmq.experiment import Experiment
        new_exp = Experiment(
            provider=provider,
            backend_name=backend_name,
            experiment_type='test',
            tags=['qiskit-test']
        )
        provider.experiment.upload_experiment(new_exp)

        # Update an experiment.
        new_exp.end_datetime = datetime.now()
        provider.experiment.update_experiment(new_exp)

        # Delete an experiment.
        provider.experiment.delete_experiment(EXPERIMENT_ID)

    Similar syntax applies to analysis results and experiment plots. Classes
    :class:`Experiment` and :class:`AnalysisResult` encapsulate data of an
    experiment and an analysis result, respectively.
    """

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
            type: Optional[str] = None,  # pylint: disable=redefined-builtin
            start_datetime: Optional[datetime] = None,
            end_datetime: Optional[datetime] = None,
            device_components: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
            tags_operator: Optional[str] = "OR",
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
            device_components: Filter by device components. An experiment must have analysis
                results with device components matching the given list exactly to be included.
            tags: Filter by tags assigned to experiments.
            tags_operator: Logical operator to use when filtering by job tags. Valid
                values are "AND" and "OR":

                    * If "AND" is specified, then an experiment must have all of the tags
                      specified in `tags` to be included.
                    * If "OR" is specified, then an experiment only needs to have any
                      of the tags specified in `tags` to be included.

        Returns:
            A list of experiments.

        Raises:
            ValueError: If an invalid `tags_operator` value is specified.
        """
        start_time_filters = []
        if start_datetime:
            st_filter = 'ge:{}'.format(local_to_utc_str(start_datetime))
            start_time_filters.append(st_filter)
        if end_datetime:
            st_filter = 'le:{}'.format(local_to_utc_str(end_datetime))
            start_time_filters.append(st_filter)

        tags_filter = None
        if tags:
            if tags_operator.upper() == 'OR':
                tags_filter = 'any:' + ','.join(tags)
            elif tags_operator.upper() == 'AND':
                tags_filter = 'contains:' + ','.join(tags)
            else:
                raise ValueError('{} is not a valid `tags_operator`. Valid values are '
                                 '"AND" and "OR".'.format(tags_operator))

        raw_data = self._api_client.experiments(
            backend_name, type, start_time_filters, device_components, tags_filter)
        experiments = []
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

        Raises:
            ExperimentNotFoundError: If the experiment is not found.
            RequestsApiError: If an unexpected error occurred when retrieving
                experiment from the server.
        """
        try:
            raw_data = self._api_client.experiment_get(experiment_id)
        except RequestsApiError as err:
            if err.status_code == 404:
                raise ExperimentNotFoundError(err.message)
            raise
        experiment = Experiment.from_remote_data(self._provider, raw_data)
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
            experiment: The ``Experiment`` object or the experiment ID.

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

    def analysis_results(
            self,
            backend_name: Optional[str] = None,
            device_components: Optional[List[str]] = None,
            experiment_id: Optional[str] = None,
            result_type: Optional[str] = None,
            quality: Optional[List[Tuple[str, Union[str, ResultQuality]]]] = None
    ) -> List[AnalysisResult]:
        """Retrieve all analysis results, with optional filtering.

        Args:
            backend_name: Backend name used for filtering.
            device_components: Filter by device components. An analysis result's
                device components must match this list exactly for it to be included.
            experiment_id: Experiment ID used for filtering.
            result_type: Analysis result type used for filtering.
            quality: Quality value used for filtering. Each element in this list is a tuple
                of an operator and a value. The operator is one of
                ``lt``, ``le``, ``gt``, ``ge``, and ``eq``. The value is one of the
                :class:`ResultQuality` values. For example,
                ``analysis_results(quality=[('ge', 'Computer Bad'), ('lt', 'Computer Good')])``
                will return all analysis results with a quality of ``Computer Bad`` and
                ``No Information``.

        Returns:
            A list of analysis results.
        """
        qualit_list = []
        if quality:
            for op, qual in quality:
                if isinstance(qual, ResultQuality):
                    qual = qual.value
                qual_str = qual if op == 'eq' else "{}:{}".format(op, qual)
                qualit_list.append(qual_str)
        response = self._api_client.analysis_results(
            backend_name=backend_name, device_components=device_components,
            experiment_uuid=experiment_id, result_type=result_type, quality=qualit_list)
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
        }  # type: Dict[str, Any]
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

        Raises:
            AnalysisResultNotFoundError: If the analysis result is not found.
            RequestsApiError: If an unexpected error occurred when retrieving
                analysis result from the server.
        """
        try:
            data = self._api_client.analysis_result_get(result_id)
        except RequestsApiError as err:
            if err.status_code == 404:
                raise AnalysisResultNotFoundError(err.message)
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

    def update_plot(
            self,
            experiment: Union[Experiment, str],
            plot: Union[str, bytes],
            plot_name: str
    ) -> Dict:
        """Update an experiment plot.

        Args:
            experiment: The ``Experiment`` object or the experiment UUID.
            plot: Name of the plot file or plot data to upload.
            plot_name: Name of the plot to update.

        Returns:
            A dictionary with name and size of the uploaded plot.
        """
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid

        return self._api_client.experiment_plot_update(experiment, plot, plot_name)

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
            return
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

        Raises:
            PlotNotFoundError: If the plot is not found.
            RequestsApiError: If an unexpected error occurred when retrieving
                plot from the server.
        """
        if isinstance(experiment, Experiment):
            experiment = experiment.uuid
        try:
            data = self._api_client.experiment_plot_get(experiment, plot_name)
        except RequestsApiError as err:
            if err.status_code == 404:
                raise PlotNotFoundError(err.message)
            raise
        if file_name:
            with open(file_name, 'wb') as file:
                num_bytes = file.write(data)
            return num_bytes
        return data

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
