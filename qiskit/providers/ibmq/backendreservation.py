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

"""Reservation information related to a backend."""

from typing import Optional, Any
from datetime import datetime


class BackendReservation:
    """Reservation information for a backend.

    Represent a reservation for a backend. This instance is returned by
    the :meth:`IBMQBackend.reservations` method. Some of the attributes are
    only available if you're the owner of the reservation.

    Attributes:
        backend_name: The name of the backend.
        start_datetime: Starting datetime of the reservation, in local timezone.
        end_datetime: Ending datetime of the reservation, in local timezone.
        duration: Duration of the reservation, in minutes.
        mode: Reservation mode. Only available if it's your reservation.
        reservation_id: Reservation ID. Only available if it's your reservation.
        creation_datetime: Reservation creation datetime. Only available if it's your reservation.
        hub: Hub used to make the reservation.
        group: Group used to make the reservation.
        project: Project used to make the reservation.
    """

    def __init__(
            self,
            backend_name: str,
            start_datetime: datetime,
            end_datetime: datetime,
            creation_datetime: Optional[datetime] = None,
            mode: Optional[str] = None,
            reservation_id: Optional[str] = None,
            hub_info: Optional[dict] = None
    ) -> None:
        """BackendReservation constructor.

        Args:
            backend_name: The name of the backend.
            start_datetime: Starting datetime of the reservation, in local timezone.
            end_datetime: Ending datetime of the reservation, in local timezone.
            mode: Reservation mode.
            reservation_id: Reservation ID.
            creation_datetime: Reservation creation datetime.
            hub_info: Hub/group/project used to make the reservation.
        """
        self.backend_name = backend_name
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.duration = int((end_datetime - start_datetime).seconds / 60)
        self.mode = mode
        self.reservation_id = reservation_id
        self.creation_datetime = creation_datetime
        if hub_info:
            self.hub = hub_info['hub']['name']
            self.group = hub_info['group']['name']
            self.project = hub_info['project']['name']
        else:
            self.hub = self.group = self.project = None

    def __repr__(self) -> str:
        out_str = "<{}(backend_name={}, start_datetime={}, end_datetime={}".format(
            self.__class__.__name__, self.backend_name, self.start_datetime.isoformat(),
            self.end_datetime.isoformat())
        for attr in ['mode', 'duration', 'reservation_id', 'creation_datetime',
                     'hub', 'group', 'project']:
            val = getattr(self, attr)
            if isinstance(val, datetime):
                val = val.isoformat()
            if val is not None:
                out_str += ", {}={}".format(attr, val)
        out_str += ')>'
        return out_str

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, BackendReservation) and self.backend_name == other.backend_name:
            if self.reservation_id and self.reservation_id == other.reservation_id:
                return True
            if self.start_datetime == other.start_datetime and \
                    self.end_datetime == other.end_datetime:
                return True
        return False
