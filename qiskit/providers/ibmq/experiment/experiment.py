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

"""IBM Quantum Experience experiment."""

import logging
from datetime import datetime
from typing import Dict, Optional, List, Union

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .analysis_result import AnalysisResult
from .constants import ExperimentShareLevel
from .utils import requires_experiment_uuid
from ..utils.converters import str_to_utc, convert_tz
from ..api.exceptions import RequestsApiError

logger = logging.getLogger(__name__)


class Experiment:
    """Class representing an experiment."""

    def __init__(
            self,
            provider: 'accountprovider.AccountProvider',
            backend_name: str,
            experiment_type: str,
            extra: Optional[Dict] = None,
            tags: Optional[List[str]] = None,
            start_datetime: Optional[datetime] = None,
            end_datetime: Optional[datetime] = None,
            experiment_uuid: Optional[str] = None,
            plot_names: Optional[List[str]] = None,
            analysis_results: Optional[List[AnalysisResult]] = None,
            hub: Optional[str] = None,
            group: Optional[str] = None,
            project: Optional[str] = None,
            share_level: Optional[Union[ExperimentShareLevel, str]] = None,
            owner: Optional[str] = None,
            notes: Optional[str] = None
    ):
        """Experiment constructor.

        Args:
            provider: the account provider.
            backend_name: Name of the backend.
            experiment_type: Experiment type.
            extra: Extra information about the experiment.
            tags: Tags for the experiment.
            start_datetime: Timestamp when the experiment started. If no timezone
                information is present, local timezone is assumed.
            end_datetime: Timestamp when the experiment ended. If no timezone
                information is present, local timezone is assumed.
            experiment_uuid: Unique identifier of the experiment.
            plot_names: A list of plot names for this experiment.
            analysis_results: A list of analysis results associated with this experiment.
            hub: The hub to which this experiment belongs. If not specified the
                hub from the provider is used.
            group: The group to which this experiment belongs. If not specified the
                group from the provider is used.
            project: The project to which this experiment belongs. If not specified the
                project from the provider is used.
            share_level: The level at which the experiment is shared. This determines who can
                view the experiment (but not update it). This defaults to "private"
                for new experiments. Possible values include:

                - private: The experiment is only visible to its owner (default)
                - project: The experiment is shared within its project
                - group: The experiment is shared within its group
                - hub: The experiment is shared within its hub
                - public: The experiment is shared publicly regardless of provider

            owner: The user ID for the owner of the experiment. This is set by the
                server when the experiment is uploaded and should not be set by a user.
            notes: Notes about the experiment.

        Raises:
            ExperimentError: If the provider does not offer experiment services.
        """
        self._backend_name = backend_name
        self._uuid = experiment_uuid
        self._start_datetime = convert_tz(start_datetime, to_utc=True)
        self.end_datetime = end_datetime
        self.extra = extra or {}
        self.tags = tags or []
        self.type = experiment_type
        self.share_level = share_level  # type: ignore[assignment]
        self.notes = notes
        self._owner = owner
        self._analysis_results = analysis_results
        self._plot_names = plot_names or []
        self._retrieved_plots = False
        self._hub = hub or provider.credentials.hub
        self._group = group or provider.credentials.group
        self._project = project or provider.credentials.project

        self._creation_datetime = None
        self._updated_datetime = None

        self._api_client = provider.experiment._api_client  # type: ignore[has-type]
        self._provider = provider

    def update_from_remote_data(self, remote_data: Dict) -> None:
        """Update the attributes of this instance using remote data.

        Args:
            remote_data: Remote data used to update this instance.
        """
        self._creation_datetime = str_to_utc(remote_data['created_at'])
        self._backend_name = remote_data.get('device_name', None)
        self.end_datetime = str_to_utc(remote_data.get('end_time'))
        self.extra = remote_data.get('extra', {})
        self._start_datetime = str_to_utc(remote_data.get('start_time', None))
        self.tags = remote_data.get('tags', [])
        self.type = remote_data['type']
        self.share_level = ExperimentShareLevel(remote_data['visibility'])
        self.notes = remote_data['notes']
        self._owner = remote_data['owner']
        self._updated_datetime = str_to_utc(remote_data.get('updated_at', None))
        self._uuid = remote_data['uuid']
        self._plot_names = remote_data.get('plot_names', [])
        self._hub = remote_data.get('hub_id')
        self._group = remote_data.get('group_id')
        self._project = remote_data.get('project_id')

    @requires_experiment_uuid
    def refresh(self) -> None:
        """Update this experiment instance with remote data."""
        self.update_from_remote_data(self._api_client.experiment_get(self.uuid))

    @property
    def backend_name(self) -> str:
        """Return the experiment's backend name."""
        return self._backend_name

    @property
    def uuid(self) -> str:
        """Return the experiment's uuid."""
        return self._uuid

    @property
    def hub(self) -> str:
        """Return the experiment's hub."""
        return self._hub

    @property
    def group(self) -> str:
        """Return the experiment's group."""
        return self._group

    @property
    def project(self) -> str:
        """Return the experiment's project."""
        return self._project

    @property
    def share_level(self) -> Optional[ExperimentShareLevel]:
        """Return the experiment share_level."""
        return self._share_level

    @share_level.setter
    def share_level(self, share_level: Union[ExperimentShareLevel, str]) -> None:
        """Update the experiment share_level.

        Args:
            share_level: Experiment share_level.
        """
        if isinstance(share_level, str):
            share_level = ExperimentShareLevel(share_level.lower())
        self._share_level = share_level

    @property
    def owner(self) -> str:
        """Return the experiment's owner."""
        return self._owner

    @property
    def start_datetime(self) -> datetime:
        """Return the timestamp when the experiment started."""
        return convert_tz(self._start_datetime, to_utc=False)

    @property
    def creation_datetime(self) -> Optional[datetime]:
        """Return the timestamp when the experiment was created."""
        return convert_tz(self._creation_datetime, to_utc=False)

    @property
    def updated_datetime(self) -> Optional[datetime]:
        """Return the timestamp when the experiment was last updated."""
        return convert_tz(self._updated_datetime, to_utc=False)

    @property
    def end_datetime(self) -> Optional[datetime]:
        """Return the timestamp when the experiment ended."""
        return convert_tz(self._end_datetime, to_utc=False)

    @end_datetime.setter
    def end_datetime(self, end_dt: Optional[datetime]) -> None:
        """Update the experiment update timestamp.

        Args:
            end_dt: Timestamp when the experiment ended. If no
                timezone information is present, local timezone is assumed.
        """
        self._end_datetime = convert_tz(end_dt, to_utc=True)

    @property
    def plot_names(self) -> List:
        """Return names of plots associated with this experiment."""
        if not self._plot_names and not self._retrieved_plots:
            self.refresh()
            self._retrieved_plots = True
        return self._plot_names

    @property
    def analysis_results(self) -> List:
        """Return analysis results associated with this experiment."""
        if self._analysis_results is None:
            try:
                self._analysis_results = self._provider.experiment.analysis_results(
                    experiment_id=self.uuid, limit=None)
            except RequestsApiError as api_err:
                logger.warning("Unable to retrieve analysis results for this experiment: %s",
                               str(api_err))
                self._analysis_results = None

        return self._analysis_results

    @analysis_results.setter
    def analysis_results(self, results: List[AnalysisResult]) -> None:
        """Assign analysis results to this experiment.

        Args:
            results: A list of analysis results to be assigned.
        """
        self._analysis_results = results

    @classmethod
    def from_remote_data(
            cls,
            provider: 'accountprovider.AccountProvider',
            remote_data: Dict
    ) -> 'Experiment':
        """Create an instance of this class from remote data.

        Args:
            provider: account provider.
            remote_data: Remote data to use.

        Returns:
            An instance of this class.
        """
        experiment = cls(
            provider=provider,
            backend_name=remote_data.get('device_name', None),
            experiment_type=remote_data['type'],
            extra=remote_data.get('extra', {}),
            tags=remote_data.get('tags', []),
            start_datetime=str_to_utc(remote_data.get('start_time', None)),
            end_datetime=str_to_utc(remote_data.get('end_time', None)),
            experiment_uuid=remote_data['uuid'],
            plot_names=remote_data.get('plot_names', []),
            hub=remote_data.get('hub_id'),
            group=remote_data.get('group_id'),
            project=remote_data.get('project_id'),
            share_level=remote_data['visibility'],
            owner=remote_data['owner'],
            notes=remote_data['notes'])
        experiment._creation_datetime = str_to_utc(remote_data['created_at'])
        experiment._updated_datetime = str_to_utc(remote_data.get('updated_at', None))
        return experiment

    def __repr__(self) -> str:
        attr_str = (
            'uuid="{}", backend_name="{}", type="{}", hub="{}", group="{}", '
            'project="{}", share_level="{}", owner="{}", notes="{}"').format(
                self.uuid, self.backend_name, self.type, self.hub, self.group, self.project,
                self.share_level, self.owner, self.notes)
        for attr in ['extra', 'tags']:
            val = getattr(self, attr)
            if val is not None:
                if isinstance(val, str):
                    attr_str += ', {}="{}"'.format(attr, val)
                else:
                    attr_str += ', {}={}'.format(attr, val)
        for dt_ in ['creation_datetime', 'updated_datetime', 'start_datetime', 'end_datetime']:
            val = getattr(self, dt_)
            if val is not None:
                attr_str += ', {}="{}"'.format(dt_, val.isoformat())

        return "<{}({})>".format(self.__class__.__name__, attr_str)
