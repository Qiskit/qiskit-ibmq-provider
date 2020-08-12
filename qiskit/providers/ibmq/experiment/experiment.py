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

from ..utils.converters import str_to_utc, convert_tz


class Experiment:

    def __init__(
            self,
            backend_name: str,
            experiment_type: str,
            extra: Optional[Dict] = None,
            tags: Optional[List[str]] = None,
            start_datetime: Optional[datetime] = None,
            end_datetime: Optional[datetime] = None,
            experiment_uuid: Optional[str] = None
    ):
        """Experiment constructor.

        Args:
            backend_name: Name of the backend.
            experiment_type: Experiment type.
            extra: Extra information about the experiment.
            tags: Tags for the experiment.
            start_datetime: Timestamp when the experiment started. If no timezone
                information is present, local timezone is assumed.
            end_datetime: Timestamp when the experiment ended. If no timezone
                information is present, local timezone is assumed.
            experiment_uuid: Unique identifier of the experiment.
        """
        self._backend_name = backend_name
        self._uuid = experiment_uuid
        self._start_datetime = convert_tz(start_datetime, to_utc=True)
        self.end_datetime = end_datetime
        self.extra = extra or {}
        self.tags = tags or []
        self.type = experiment_type
        self.analysis_results = []

        self._creation_datetime = None
        self._updated_datetime = None

    def update_from_remote_data(self, remote_data: Dict) -> None:
        """Update the attributes of this instance using remote data.

        Args:
            remote_data: Remote data used to update this instance.
        """
        self._creation_datetime = str_to_utc(remote_data['created_at'])
        self._backend_name = remote_data['device_name']
        self.end_datetime = str_to_utc(remote_data['end_time'])
        self.extra = remote_data['extra'] or {}
        self._start_datetime = str_to_utc(remote_data['start_time'])
        self.tags = remote_data['tags'] or []
        self.type = remote_data['type']
        self._updated_datetime = str_to_utc(remote_data['updated_at'])
        self._uuid = remote_data['uuid']

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
    def end_datetime(self, dt: Optional[datetime]) -> None:
        """Update the experiment update timestamp.

        Args:
            dt: Timestamp when the experiment ended. If no
                timezone information is present, local timezone is assumed.
        """
        self._end_datetime = convert_tz(dt, to_utc=True)

    @classmethod
    def from_remote_data(cls, remote_data: Dict) -> 'Experiment':
        """Create an instance of this class from remote data.

        Args:
            remote_data: Remote data to use.

        Returns:
            An instance of this class.
        """
        experiment = cls(
            backend_name=remote_data['device_name'],
            experiment_type=remote_data['type'],
            extra=remote_data.get('extra', None),
            tags=remote_data.get('tags', None),
            start_datetime=str_to_utc(remote_data['start_time']),
            end_datetime=str_to_utc(remote_data['end_time']),
            experiment_uuid=remote_data['uuid'])
        experiment._creation_datetime = str_to_utc(remote_data['created_at'])
        experiment._updated_datetime = str_to_utc(remote_data['updated_at'])
        return experiment

    def __repr__(self):
        attr_str = 'uuid="{}", backend_name="{}", type="{}"'.format(
            self.uuid, self.backend_name, self.type)
        for attr in ['extra', 'tags']:
            val = getattr(self, attr)
            if val is not None:
                if isinstance(val, str):
                    attr_str += ', {}="{}"'.format(attr, val)
                else:
                    attr_str += ', {}={}'.format(attr, val)
        for dt in ['creation_datetime', 'updated_datetime', 'start_datetime', 'end_datetime']:
            val = getattr(self, dt)
            if val is not None:
                attr_str += ', {}="{}"'.format(dt, val.isoformat())

        return "<{}({})>".format(self.__class__.__name__, attr_str)
