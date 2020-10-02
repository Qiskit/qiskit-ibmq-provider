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

"""IBM Quantum Experience experiment analysis result."""

from typing import Optional, Union, Dict, List, NamedTuple
from datetime import datetime

from ..utils.converters import str_to_utc, convert_tz
from .constants import ResultQuality
from ..exceptions import IBMQInputValueError


# TODO Use variable annotation syntax when Python 3.5 support is dropped.
DeviceComponent = NamedTuple('DeviceComponent',
                             [('backend_name', str), ('type', str), ('uuid', str)])
"""Named tuple representing a device component."""


class Fit:
    """Class representing a fit value."""

    def __init__(self, value: float, variance: Optional[float] = None):
        """Fit constructor.

        Args:
            value: Value of the fit.
            variance: Variance of the fit.
        """
        self.value = value
        self.variance = variance

    def to_dict(self) -> Dict:
        """Return the dictionary representation of the object."""
        return {'value': self.value, 'variance': self.variance}


class AnalysisResult:
    """Class representing an analysis result for an experiment."""

    def __init__(
            self,
            experiment_uuid: str,
            device_components: List[str],
            fit: Union[Fit, Dict[str, float]],
            result_type: str,
            chisq: Optional[float] = None,
            quality: Union[ResultQuality, str] = ResultQuality.NO_INFORMATION,
            tags: Optional[List[str]] = None,
            result_uuid: Optional[str] = None,
            backend_name: Optional[str] = None,
    ):
        """AnalysisResult constructor.

        Args:
            experiment_uuid: Unique identifier of the experiment.
            device_components: Device component types.
            fit: Fit value. This can be an instance of the :class:`Fit` class, or
                a dictionary with the keys ``value`` and optionally ``variance``.
            result_type: Result type.
            chisq: chi^2 decimal value of the fit.
            quality: Quality of the measurement value.
            tags: Tags for this result.
            result_uuid: Unique identifier for the result.
            backend_name: Name of the backend on which the experiment was run.

        Raises:
            IBMQInputValueError: If an input argument is invalid.
        """
        if not device_components:
            raise IBMQInputValueError('device_components must not be empty.')

        self.experiment_uuid = experiment_uuid
        self.fit = fit  # type: ignore[assignment]
        self.type = result_type
        self.chisq = chisq
        self.quality = quality  # type: ignore[assignment]
        self.tags = tags or []
        self._uuid = result_uuid
        self.device_components = device_components
        self.backend_name = backend_name
        self._creation_datetime = None
        self._updated_datetime = None

    def update_from_remote_data(self, remote_data: Dict) -> None:
        """Update the attributes of this instance using remote data.

        Args:
            remote_data: Remote data used to update this instance.
        """
        self.chisq = remote_data['chisq']
        self.device_components = remote_data['device_components']
        self.backend_name = remote_data['device_name']
        self.experiment_uuid = remote_data['experiment_uuid']
        self.fit = remote_data['fit']
        self.quality = ResultQuality(remote_data['quality'])
        self.tags = remote_data['tags'] or []
        self.type = remote_data['type']
        self._creation_datetime = str_to_utc(remote_data['created_at'])
        self._updated_datetime = str_to_utc(remote_data['updated_at'])
        self._uuid = remote_data['uuid']

    @property
    def uuid(self) -> str:
        """Return UUID of this analysis result."""
        return self._uuid

    @property
    def fit(self) -> Fit:
        """Return the fit value for the experiment."""
        return self._fit

    @fit.setter
    def fit(self, fit_val: Union[Fit, Dict[str, float]]) -> None:
        """Update the analysis result fit value.

        Args:
            fit_val: Analysis result fit value.
        """
        if not isinstance(fit_val, Fit):
            fit_val = Fit(**fit_val)
        self._fit = fit_val

    @property
    def creation_datetime(self) -> datetime:
        """Return the timestamp when the experiment was created."""
        return convert_tz(self._creation_datetime, to_utc=False)

    @property
    def updated_datetime(self) -> datetime:
        """Return the timestamp when the experiment was last updated."""
        return convert_tz(self._updated_datetime, to_utc=False)

    @property
    def quality(self) -> ResultQuality:
        """Return the analysis result quality."""
        return self._quality

    @quality.setter
    def quality(self, quality: Union[ResultQuality, str]) -> None:
        """Update the analysis result quality.

        Args:
            quality: Analysis result quality.
        """
        if isinstance(quality, str):
            quality = ResultQuality(quality)
        self._quality = quality

    @classmethod
    def from_remote_data(cls, remote_data: Dict) -> 'AnalysisResult':
        """Create an instance of this class from remote data.

        Args:
            remote_data: Remote data to use.

        Returns:
            An instance of this class.
        """
        obj = cls(experiment_uuid=remote_data['experiment_uuid'],
                  fit=remote_data['fit'],
                  result_type=remote_data['type'],
                  chisq=remote_data['chisq'],
                  quality=remote_data['quality'],
                  tags=remote_data['tags'],
                  result_uuid=remote_data['uuid'],
                  device_components=remote_data['device_components'],
                  backend_name=remote_data['device_name']
                  )
        obj._creation_datetime = str_to_utc(remote_data['created_at'])
        obj._updated_datetime = str_to_utc(remote_data['updated_at'])
        return obj

    def __repr__(self) -> str:
        attr_str = 'uuid="{}"'.format(self.uuid)
        for attr in ['type', 'quality', 'experiment_uuid', 'backend_name',
                     'chisq', 'tags', 'device_components']:
            val = getattr(self, attr)
            if val is not None:
                if isinstance(val, str):
                    attr_str += ', {}="{}"'.format(attr, val)
                else:
                    attr_str += ', {}={}'.format(attr, val)
        attr_str += ', fit={}'.format(self.fit.to_dict())
        for dt_ in ['creation_datetime', 'updated_datetime']:
            val = getattr(self, dt_)
            if val is not None:
                attr_str += ', {}="{}"'.format(dt_, val.isoformat())

        return "<{}({})>".format(self.__class__.__name__, attr_str)
