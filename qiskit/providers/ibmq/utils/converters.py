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

from typing import Union
import datetime
import dateutil


def utc_to_local(utc_dt: Union[datetime.datetime, str]) -> datetime.datetime:
    """Convert a UTC ``datetime`` object or string to a local timezone ``datetime``.

    Args:
        utc_dt: Input UTC `datetime`.

    Returns:
        A ``datetime`` with the local timezone.

    Raises:
        TypeError: If the input parameter value is not valid.
    """
    if isinstance(utc_dt, str):
        utc_dt = dateutil.parser.parse(utc_dt)
    if not isinstance(utc_dt, datetime.datetime):
        TypeError('Input is not string or datetime.')
    utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)  # type: ignore[arg-type]
    local_tz = datetime.datetime.now().astimezone().tzinfo
    local_dt = utc_dt.astimezone(local_tz)  # type: ignore[attr-defined]
    return local_dt
