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

"""IBM Quantum Experience experiment."""

from datetime import datetime
from typing import Dict, Optional, List

from qiskit.providers.ibmq import accountprovider  # pylint: disable=unused-import

from .exceptions import ExperimentError
from .utils import requires_experiment_uuid
from ..utils.converters import str_to_utc, convert_tz


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
            plot_names: Optional[List[str]] = None
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
        """
        self._backend_name = backend_name
        self._uuid = experiment_uuid
        self._start_datetime = convert_tz(start_datetime, to_utc=True)
        self.end_datetime = end_datetime
        self.extra = extra or {}
        self.tags = tags or []
        self.type = experiment_type
        self.analysis_results = []
        self._plot_names = plot_names or []
        self.retrieved_plots = False

        self._creation_datetime = None
        self._updated_datetime = None

        try:
            self._api_client = provider.experiment._api_client
        except AttributeError:
            raise ExperimentError(
                "Provider {} does not offer experiment service.".format(provider))

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
        self._updated_datetime = str_to_utc(remote_data.get('updated_at', None))
        self._uuid = remote_data['uuid']
        self._plot_names = remote_data.get('plot_names', [])

    @requires_experiment_uuid
    def refresh(self):
        """Update this experiment instance with remote data."""
        self.update_from_remote_data(self._api_client.experiment_get(self.uuid))

    @requires_experiment_uuid
    def retrieve_plot(self, plot_name: str):
        """Retrieve a plot.

        Args:
            plot_name: Name of the plot.

        Returns:

        """
        return self._api_client.experiment_plot_get(self.uuid, plot_name)

    @property
    def backend_name(self) -> str:
        """Return the experiment's backend name."""
        return self._backend_name

    @property
    def uuid(self) -> str:
        """Return the experiment's uuid."""
        return self._uuid

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
        if not self._plot_names and not self.retrieved_plots:
            self.refresh()
            self.retrieved_plots = True
        return self._plot_names

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
            plot_names=remote_data.get('plot_names', []))
        experiment._creation_datetime = str_to_utc(remote_data['created_at'])
        experiment._updated_datetime = str_to_utc(remote_data.get('updated_at', None))
        return experiment

    def __repr__(self):
        attr_str = 'uuid="{}", backend_name="{}", type="{}"'.format(
            self.uuid, self.backend_name, self.type)
        for attr in ['extra', 'tags', 'plot_names']:
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


