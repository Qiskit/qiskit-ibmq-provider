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

import datetime
import dateutil
from ..notifications.exceptions import exception_widget

def utc_to_local(utc_dt):
    """Takes a UTC datetime object or string and
    converts it to a local timezone datetime.

    Parameters:
        utc_dt (datetime or str): Input UTC datetime.

    Returns:
        datetime: Local date and time.
    """
    if isinstance(utc_dt, str):
        utc_dt = dateutil.parser.parse(utc_dt)
    if not isinstance(utc_dt, datetime.datetime):
        exception_widget(TypeError('Input is not string or datetime.'))
    utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
    local_tz = datetime.datetime.now().astimezone().tzinfo
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt
