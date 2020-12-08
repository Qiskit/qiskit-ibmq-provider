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

"""Utilities for working with IBM Quantum Experience backends."""

from typing import List, Optional

from ..backendreservation import BackendReservation
from ..utils.converters import utc_to_local


def convert_reservation_data(
        raw_reservations: List,
        backend_name: Optional[str] = None
) -> List[BackendReservation]:
    """Convert a list of raw reservation data to ``BackendReservation`` objects.

    Args:
        raw_reservations: Raw reservation data.
        backend_name: Name of the backend.

    Returns:
        A list of ``BackendReservation`` objects.
    """
    reservations = []
    for raw_res in raw_reservations:
        creation_datetime = raw_res.get('creationDate', None)
        creation_datetime = utc_to_local(creation_datetime) if creation_datetime else None
        backend_name = backend_name or raw_res.get('backendName', None)
        reservations.append(BackendReservation(
            backend_name=backend_name,
            start_datetime=utc_to_local(raw_res['initialDate']),
            end_datetime=utc_to_local(raw_res['endDate']),
            mode=raw_res.get('mode', None),
            reservation_id=raw_res.get('id', None),
            creation_datetime=creation_datetime,
            hub_info=raw_res.get('hubInfo', None)))
    return reservations
