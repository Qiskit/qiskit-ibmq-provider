# -*- coding: utf-8 -*-

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

from typing import Union, Tuple
import datetime
from math import ceil
import dateutil.parser
from dateutil import tz


def utc_to_local(utc_dt: Union[datetime.datetime, str]) -> datetime.datetime:
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
    if not isinstance(utc_dt, datetime.datetime):
        raise TypeError('Input `utc_dt` is not string or datetime.')
    utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)  # type: ignore[arg-type]
    local_dt = utc_dt.astimezone(tz.tzlocal())  # type: ignore[attr-defined]
    return local_dt


def local_to_utc(local_dt: Union[datetime.datetime, str]) -> datetime.datetime:
    """Convert a local ``datetime`` object or string to a UTC ``datetime``.

    Args:
        local_dt: Input local `datetime` or string.

    Returns:
        A ``datetime`` in UTC.

    Raises:
        TypeError: If the input parameter value is not valid.
    """
    if isinstance(local_dt, str):
        local_dt = dateutil.parser.parse(local_dt)
    if not isinstance(local_dt, datetime.datetime):
        raise TypeError('Input `local_dt` is not string or datetime.')
    local_dt = local_dt.replace(tzinfo=tz.tzlocal())
    utc_dt = local_dt.astimezone(tz.UTC)
    return utc_dt


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


def duration_difference(date_time_utc: datetime.datetime) -> str:
    """Compute the estimated duration until the given datetime.

    Args:
        date_time_utc: The input datetime, in UTC.

    Returns:
        String giving the estimated duration.
    """
    time_delta = date_time_utc.replace(tzinfo=None) - datetime.datetime.utcnow()
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
