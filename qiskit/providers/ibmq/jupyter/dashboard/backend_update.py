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

"""A module for the async backend widget updates"""
import time
import threading
from typing import List

def update_backend_info(device_list: List,
                        interval: int = 30) -> None:
    """Updates the device list from another thread
    """
    my_thread = threading.currentThread()
    current_interval = 0
    started = False
    val_str = "<font size='4' face='monospace'>{pend}</font>"
    stat_str = "<font size='4' style='color:{color}' face='monospace'>{msg}</font>"
    while getattr(my_thread, "do_run", False):
        if current_interval == interval or started is False:
            for backend in device_list.children:
                try:
                    status = backend._backend.status()
                except Exception:  # pylint: disable=broad-except
                    pass
                else:
                    stat_msg = status.status_msg
                    pending = str(status.pending_jobs)

                    color = '#000000'
                    if stat_msg == 'active':
                        color = '#34bc6e'
                    if stat_msg in ['maintenance', 'internal']:
                        color = '#FFB000'

                    status_wid = backend.children[0].children[1].children[0].children[1].children[1]
                    if status_wid.value.split('>')[1].split("<")[0] != stat_msg:
                        status_wid.value = stat_str.format(color=color, msg=stat_msg)

                    pend_wid = backend.children[0].children[1].children[1].children[1].children[1]
                    if pend_wid.value.split('>')[1].split("<")[0] != pending:
                        pend_wid.value = val_str.format(pend=pending)

                if not getattr(my_thread, "do_run", False):
                    break

            started = True
            current_interval = 0
        time.sleep(1)
        current_interval += 1
