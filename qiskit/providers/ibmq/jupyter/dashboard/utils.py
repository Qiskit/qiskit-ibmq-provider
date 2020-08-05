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

"""Utility functions for the IBM Quantum Experience dashboard."""

from typing import Optional
from collections import namedtuple
from datetime import datetime, timedelta

from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.backendreservation import BackendReservation


BackendWithProviders = namedtuple('BackendWithProviders', ['backend', 'providers'])
"""Named tuple used to pass a backend and its providers."""


def get_next_reservation(
        backend: IBMQBackend,
        time_period_hr: int = 24
) -> Optional[BackendReservation]:
    """Get the next reservation within the input time period for the backend.

    Args:
        backend: Backend for which the reservation is to be returned.
        time_period_hr: Time period to search for reservations.

    Returns:
        The next reservation for the backend.
    """
    reservations = backend.reservations(
        start_datetime=datetime.now(),
        end_datetime=datetime.now() + timedelta(hours=time_period_hr))
    if reservations:
        next_reservation = min(reservations, key=lambda rsvr: rsvr.start_datetime)
        return next_reservation
    return None
