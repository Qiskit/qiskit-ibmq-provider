# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utilities related to conversion."""

from typing import Union, Tuple, Any, Optional
from datetime import datetime, timedelta, timezone
from math import ceil

import dateutil.parser
from dateutil import tz


def utc_to_local(utc_dt: Union[datetime, str]) -> datetime:
    """Convert a UTC ``datetime`` object or string to a local timezone ``datetime``.

    Args:
        utc_dt: Input UTC `datetime` or string.

    Returns:
        A ``datetime`` with the local timezone.

    Raises:
        TypeError: If the input parameter value is not valid.
    """
    if isinstance(utc_dt, str):
        utc_dt = dateutil.parser.parse(utc_dt)
    if not isinstance(utc_dt, datetime):
        raise TypeError('Input `utc_dt` is not string or datetime.')
    utc_dt = utc_dt.replace(tzinfo=timezone.utc)  # type: ignore[arg-type]
    local_dt = utc_dt.astimezone(tz.tzlocal())  # type: ignore[attr-defined]
    return local_dt


def local_to_utc(local_dt: Union[datetime, str]) -> datetime:
    """Convert a local ``datetime`` object or string to a UTC ``datetime``.

    Args:
        local_dt: Input local ``datetime`` or string.

    Returns:
        A ``datetime`` in UTC.

    Raises:
        TypeError: If the input parameter value is not valid.
    """
    if isinstance(local_dt, str):
        local_dt = dateutil.parser.parse(local_dt)
    if not isinstance(local_dt, datetime):
        raise TypeError('Input `local_dt` is not string or datetime.')

    # Input is considered local if it's ``utcoffset()`` is ``None`` or none-zero.
    if local_dt.utcoffset() is None or local_dt.utcoffset() != timedelta(0):
        local_dt = local_dt.replace(tzinfo=tz.tzlocal())
        return local_dt.astimezone(tz.UTC)
    return local_dt  # Already in UTC.


def local_to_utc_str(local_dt: Union[datetime, str], suffix: str = 'Z') -> str:
    """Convert a local ``datetime`` object or string to a UTC string.

    Args:
        local_dt: Input local ``datetime`` or string.
        suffix: ``Z`` or ``+``, indicating whether the suffix should be ``Z`` or
            ``+00:00``.

    Returns:
        UTC datetime in ISO format.
    """
    utc_dt_str = local_to_utc(local_dt).isoformat()
    if suffix == 'Z':
        utc_dt_str = utc_dt_str.replace('+00:00', 'Z')
    return utc_dt_str


def convert_tz(input_dt: Optional[datetime], to_utc: bool) -> Optional[datetime]:
    """Convert input timestamp timezone.

    Args:
        input_dt: Timestamp to be converted.
        to_utc: True if to convert to UTC, otherwise to local timezone.

    Returns:
        Converted timestamp, or ``None`` if input is ``None``.
    """
    if input_dt is None:
        return None
    if to_utc:
        return local_to_utc(input_dt)
    return utc_to_local(input_dt)


def utc_to_local_all(data: Any) -> Any:
    """Recursively convert all ``datetime`` in the input data from local time to UTC.

    Note:
        Only lists and dictionaries are traversed.

    Args:
        data: Data to be converted.

    Returns:
        Converted data.
    """
    if isinstance(data, datetime):
        return utc_to_local(data)
    elif isinstance(data, list):
        return [utc_to_local_all(elem) for elem in data]
    elif isinstance(data, dict):
        return {key: utc_to_local_all(elem) for key, elem in data.items()}
    return data


def str_to_utc(utc_dt: Optional[str]) -> Optional[datetime]:
    """Convert a UTC string to a ``datetime`` object with UTC timezone.

    Args:
        utc_dt: Input UTC string in ISO format.

    Returns:
        A ``datetime`` with the UTC timezone, or ``None`` if the input is ``None``.
    """
    if not utc_dt:
        return None
    parsed_dt = dateutil.parser.isoparse(utc_dt)
    return parsed_dt.replace(tzinfo=timezone.utc)


def seconds_to_duration(seconds: float) -> Tuple[int, int, int, int, int]:
    """Converts seconds in a datetime delta to a duration.

    Args:
        seconds: Number of seconds in time delta.

    Returns:
        A tuple containing the duration in terms of days,
        hours, minutes, seconds, and milliseconds.
    """
    days = int(seconds // (3600 * 24))
    hours = int((seconds // 3600) % 24)
    minutes = int((seconds // 60) % 60)
    seconds = seconds % 60
    millisec = 0
    if seconds < 1:
        millisec = int(ceil(seconds*1000))
        seconds = 0
    else:
        seconds = int(seconds)
    return days, hours, minutes, seconds, millisec


def duration_difference(date_time: datetime) -> str:
    """Compute the estimated duration until the given datetime.

    Args:
        date_time: The input local datetime.

    Returns:
        String giving the estimated duration.
    """
    time_delta = date_time.replace(tzinfo=None) - datetime.now()
    time_tuple = seconds_to_duration(time_delta.total_seconds())
    # The returned tuple contains the duration in terms of
    # days, hours, minutes, seconds, and milliseconds.
    time_str = ''
    if time_tuple[0]:
        time_str += '{} days'.format(time_tuple[0])
        time_str += ' {} hrs'.format(time_tuple[1])
    elif time_tuple[1]:
        time_str += '{} hrs'.format(time_tuple[1])
        time_str += ' {} min'.format(time_tuple[2])
    elif time_tuple[2]:
        time_str += '{} min'.format(time_tuple[2])
        time_str += ' {} sec'.format(time_tuple[3])
    elif time_tuple[3]:
        time_str += '{} sec'.format(time_tuple[3])
    return time_str
