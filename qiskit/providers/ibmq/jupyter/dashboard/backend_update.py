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

import ipywidgets as wid
from qiskit.providers.ibmq.utils.converters import duration_difference

from ..utils import get_next_reservation
from .constants import RESERVATION_STR, RESERVATION_NONE, STAT_FONT_VALUE, STAT_FONT_VALUE_COLOR


def update_backend_info(device_list: wid.VBox,
                        interval: int = 30) -> None:
    """Updates the device list from another thread.

    Args:
        device_list: Widget showing the devices.
        interval: How often to refresh the backend information.
    """
    my_thread = threading.current_thread()
    current_interval = 0
    started = False
    reservation_interval = 10*60
    cur_rsvr_interval = 0
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

                    if cur_rsvr_interval >= reservation_interval:
                        cur_rsvr_interval = 0
                        next_resrv = get_next_reservation(backend_pane._backend)
                        reservation_wid = backend_pane._reservation_val_wid
                        if next_resrv:
                            start_dt_str = duration_difference(next_resrv.start_datetime)
                            new_resrv_val = RESERVATION_STR.format(
                                start_dt=start_dt_str, duration=next_resrv.duration)
                            if stat_msg == 'active':
                                stat_msg += ' [R]'
                        else:
                            new_resrv_val = RESERVATION_NONE

                        if reservation_wid.value != new_resrv_val:
                            reservation_wid.value = new_resrv_val

                    status_wid = backend_pane._status_val_wid
                    if status_wid.value.split('>')[1].split("<")[0] != stat_msg:
                        # If the status message has changed.
                        status_wid.value = STAT_FONT_VALUE_COLOR.format(color=color, msg=stat_msg)

                    pend_wid = backend_pane._queue_val_wid
                    if pend_wid.value.split('>')[1].split("<")[0] != pending:
                        # If the number of pending jobs has changed.
                        pend_wid.value = STAT_FONT_VALUE.format(pending)

                if not getattr(my_thread, "do_run", False):
                    break

            started = True
            current_interval = 0
        time.sleep(1)
        current_interval += 1
        cur_rsvr_interval += 1
