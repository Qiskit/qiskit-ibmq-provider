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

"""A module for the async backend widget updates."""

import time
import threading
from datetime import datetime

import ipywidgets as wid
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend

from .utils import get_next_reservation


def update_backend_info(device_list: wid.VBox,
                        interval: int = 30) -> None:
    """Updates the device list from another thread.

    Args:
        device_list: Widget showing the devices.
        interval: How often to refresh the backend information.
    """
    my_thread = threading.currentThread()
    current_interval = 0
    started = False
    reservation_interval = 12*60*60
    cur_rsvr_interval = 0
    val_str = "<font size='4' face='monospace'>{pend}</font>"
    stat_str = "<font size='4' style='color:{color}' face='monospace'>{msg}</font>"
    reservation_str = "<font size='4' face='monospace'>{start_dt} ({duration}m)</font>"
    while getattr(my_thread, "do_run", False):
        if current_interval == interval or started is False:
            for backend_pane in device_list.children:
                # Each backend_pane is a backend widget. See ``make_backend_widget()``
                # for more information on how the widget is constructed and its child widgets.
                try:
                    status = backend_pane._backend.status()
                except Exception:  # pylint: disable=broad-except
                    pass
                else:
                    stat_msg = status.status_msg
                    pending = str(status.pending_jobs)

                    color = '#000000'
                    if stat_msg == 'active':
                        color = '#34bc6e'
                    if stat_msg in ['maintenance', 'internal', 'dedicated']:
                        color = '#FFB000'

                    reservation_wid = backend_pane._reservation_val_wid
                    if reservation_wid:
                        reservation_dt = \
                            reservation_wid.value.split('>')[1].split("<")[0].split('(')[0]
                        now = datetime.now().replace(microsecond=0).isoformat()
                        if reservation_dt <= now:   # Reservation started in the past.
                            stat_msg = _update_reservation_value(
                                backend_pane._backend, reservation_wid, reservation_str, stat_msg)
                        else:
                            stat_msg += ' [R]'
                    elif cur_rsvr_interval >= reservation_interval:
                        # TODO need to add reservation panel
                        cur_rsvr_interval = 0
                        stat_msg = _update_reservation_value(
                            backend_pane._backend, reservation_wid, reservation_str, stat_msg)

                    status_wid = backend_pane._status_val_wid
                    if status_wid.value.split('>')[1].split("<")[0] != stat_msg:
                        # If the status message has changed.
                        status_wid.value = stat_str.format(color=color, msg=stat_msg)

                    pend_wid = backend_pane.children[0].children[1].children[1].children[1].children[1]
                    if pend_wid.value.split('>')[1].split("<")[0] != pending:
                        # If the number of pending jobs has changed.
                        pend_wid.value = val_str.format(pend=pending)

                if not getattr(my_thread, "do_run", False):
                    break

            started = True
            current_interval = 0
        time.sleep(1)
        current_interval += 1
        cur_rsvr_interval += 1


def _update_reservation_value(
        backend: IBMQBackend,
        reservation_wid: wid.HTML,
        reservation_str: str,
        stat_msg: str
) -> str:
    """Update reservation information.

    Args:
        backend: Backend whose reservation information is to be updated.
        reservation_wid: Reservation widget.
        reservation_str: String on the reservation widget.
        stat_msg: Status message.

    Returns:
        Updated status message.
    """
    next_resrv = get_next_reservation(backend)
    if next_resrv:
        if stat_msg == 'active':
            stat_msg += ' [R]'
        start_dt = next_resrv.start_datetime.replace(tzinfo=None)
        reservation_wid.value = reservation_str.format(
            start_dt=start_dt.isoformat(), duration=next_resrv.duration)
    else:
        reservation_wid.value = ''

    return stat_msg
