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
# pylint: disable=import-error, unused-argument, attribute-defined-outside-init
# pylint: disable=protected-access
"""The core IBMQ dashboard launcher
"""

import threading
from typing import List, Tuple, Dict
import ipywidgets as wid
from IPython.display import display, Javascript
from IPython.core.magic import line_magic, Magics, magics_class
from qiskit.tools.events.pubsub import Subscriber
from qiskit.exceptions import QiskitError
from qiskit.providers.ibmq.job.exceptions import IBMQJobApiError
from ... import IBMQ
from ...ibmqbackend import IBMQBackend
from .job_widgets import (make_clear_button,
                          make_labels, create_job_widget)
from .backend_widget import make_backend_widget
from .backend_update import update_backend_info
from .watcher_monitor import _job_monitor


class Accordion_with_thread(wid.Accordion):  # pylint: disable=invalid-name
    """An Accordion that will close an attached thread
    """
    def __init__(self,
                 children: Tuple = (),
                 **kwargs):
        super(Accordion_with_thread, self).__init__(children=children, **kwargs)
        self._thread = None

    def __del__(self):
        """Object disposal"""
        if hasattr(self, '_thread'):
            try:
                self._thread.do_run = False
                self._thread.join()
            except Exception:  # pylint: disable=broad-except
                pass
        self.close()


def _add_device_to_list(backend: IBMQBackend,
                        device_list: List):
    device_pane = make_backend_widget(backend)
    device_list.children = list(device_list.children) + [device_pane]


class IQXDashboard(Subscriber):
    """An IQX dashboard.
    """
    def __init__(self):
        super().__init__()
        self.jobs: List = []
        self._init_subscriber()
        self.dashboard: Accordion_with_thread = None
        self.backend_dict: Dict = None
        self.job_viewer: wid.VBox = None
        self._clear_jobs_button: wid.GridBox = make_clear_button(self)
        self._jobs_labels: wid.HBox = make_labels()
        self.refresh_jobs_board()

    def _get_backends(self):
        ibmq_backends = {}
        for pro in IBMQ.providers():
            pro_name = "{hub}/{group}/{project}".format(hub=pro.credentials.hub,
                                                        group=pro.credentials.group,
                                                        project=pro.credentials.project)
            for back in pro.backends():
                if not back.configuration().simulator:
                    if back.name() not in ibmq_backends.keys():
                        ibmq_backends[back.name()] = [back, [pro_name]]
                    else:
                        ibmq_backends[back.name()][1].append(pro_name)

        self.backend_dict = ibmq_backends

    def refresh_jobs_board(self):
        """Refreshes the job viewer.
        """
        if self.job_viewer is not None:
            self.job_viewer.children = [self._clear_jobs_button,
                                        self._jobs_labels] + list(reversed(self.jobs))

    def refresh_device_list(self):
        """Refresh the list of devices
        """
        for _wid in self.dashboard._device_list.children:
            _wid.close()
        self.dashboard._device_list.children = []
        for back in self.backend_dict.values():
            _thread = threading.Thread(target=_add_device_to_list,
                                       args=(back, self.dashboard._device_list))
            _thread.start()

    def start_dashboard(self):
        """Starts the job viewer
        """
        self.dashboard = build_dashboard_widget()
        self.job_viewer = self.dashboard.children[0].children[1]
        self._get_backends()
        self.refresh_device_list()
        self.dashboard._thread = threading.Thread(target=update_backend_info,
                                                  args=(self.dashboard._device_list,))
        self.dashboard._thread.do_run = True
        self.dashboard._thread.start()
        self.refresh_jobs_board()

    def stop_dashboard(self):
        """Stops the job viewer.
        """
        if self.dashboard:
            self.dashboard._thread.do_run = False
            self.dashboard._thread.join()
            self.dashboard.close()
        self.dashboard = None

    def update_single_job(self, update_info: Tuple):
        """Update a single job instance

        Args:
            update_info: Updated job info containing job ID,
                         status string, est time, and status value.
        """
        job_id = update_info[0]
        found_job = False
        ind = None
        for idx, job in enumerate(self.jobs):
            if job.job_id == job_id:
                found_job = True
                ind = idx
                break
        if found_job:
            job_wid = self.jobs[ind]
            # update status
            if update_info[1] == 'DONE':
                stat = "<font style='color:#34BC6E'>{}</font>".format(update_info[1])
            elif update_info[1] == 'ERROR':
                stat = "<font style='color:#DC267F'>{}</font>".format(update_info[1])
            elif update_info[1] == 'CANCELLED':
                stat = "<font style='color:#FFB000'>{}</font>".format(update_info[1])
            else:
                stat = update_info[1]
            job_wid.children[3].value = stat
            # update queue
            if update_info[2] == 0:
                queue = '-'
            else:
                queue = str(update_info[2])
            job_wid.children[4].value = queue

    def cancel_job(self, job_id: str):
        """Cancels a job in the watcher

        Args:
            job_id: Job id to remove.

        Raises:
            Exception: Job id not found.
        """
        do_pop = False
        ind = None
        for idx, job in enumerate(self.jobs):
            if job.job_id == job_id:
                do_pop = True
                ind = idx
                break
        if not do_pop:
            raise Exception('job_id not found')
        if 'CANCELLED' not in self.jobs[ind].children[3].value:
            try:
                self.jobs[ind].job.cancel()
                status = self.jobs[ind].job.status()
            except IBMQJobApiError:
                pass
            else:
                self.update_single_job((self.jobs[ind].job_id,
                                        status.name, 0,
                                        status.value))

    def clear_done(self):
        """Clears the done jobs from the list.
        """
        _temp_jobs = []
        do_refresh = False
        for job in self.jobs:
            job_str = job.children[3].value
            if not (('DONE' in job_str) or ('CANCELLED' in job_str) or ('ERROR' in job_str)):
                _temp_jobs.append(job)
            else:
                job.close()
                do_refresh = True
        if do_refresh:
            self.jobs = _temp_jobs
            self.refresh_jobs_board()

    def _init_subscriber(self):

        def _add_job(job):
            status = job.status()
            job_widget = create_job_widget(self, job,
                                           job.backend(),
                                           status.name,
                                           job.queue_position(),
                                           status.value)
            self.jobs.append(job_widget)
            _job_monitor(job, status, self)

            if len(self.jobs) > 50:
                self.clear_done()
            else:
                self.refresh_jobs_board()

        self.subscribe("ibmq.job.start", _add_job)


def build_dashboard_widget() -> Accordion_with_thread:
    """Builds the dashboard widget

    Returns:
        Dashboard widget.
    """
    tabs = wid.Tab(layout=wid.Layout(width='760px',
                                     max_height='650px')
                   )

    devices = wid.VBox(children=[],
                       layout=wid.Layout(width='740px',
                                         height='100%')
                       )

    device_list = wid.Box(children=[devices], layout=wid.Layout(width='auto',
                                                                max_height='600px'
                                                                ))

    jobs_box = wid.VBox(layout=wid.Layout(max_width='740px',
                                          min_width='740px',
                                          justify_content='flex-start'))
    tabs.children = [device_list, jobs_box]
    tabs.set_title(0, 'Devices')
    tabs.set_title(1, 'Jobs')

    acc = Accordion_with_thread(children=[tabs],
                                layout=wid.Layout(width='auto',
                                                  max_height='700px',
                                                  ))

    acc._device_list = acc.children[0].children[0].children[0]

    acc.set_title(0, 'IQX Dashboard')
    acc.selected_index = None
    acc.layout.visibility = 'hidden'
    display(acc)
    acc._dom_classes = ['job_widget']
    display(Javascript("""$('div.job_widget')
        .detach()
        .appendTo($('#header'))
        .css({
            'z-index': 999,
             'position': 'fixed',
            'box-shadow': '5px 5px 5px -3px black',
            'opacity': 0.95,
            'float': 'left,'
        })
        """))
    acc.layout.visibility = 'visible'
    return acc


@magics_class
class IQXDashboardMagic(Magics):
    """A class for enabling/disabling the job watcher.
    """
    @line_magic
    def iqx_dashboard(self, line='', cell=None):
        """A Jupyter magic function to enable job watcher.
        """
        pro = IBMQ.providers()
        if not pro:
            try:
                IBMQ.load_account()
            except Exception:
                raise QiskitError("Could not load IBMQ account from local file.")
            else:
                pro = IBMQ.providers()
                if not pro:
                    raise QiskitError("No providers found.  Must load your IBMQ account.")
        _IQX_DASHBOARD.stop_dashboard()
        _IQX_DASHBOARD.start_dashboard()

    @line_magic
    def disable_ibmq_dashboard(self, line='', cell=None):
        """A Jupyter magic function to disable job watcher.
        """
        _IQX_DASHBOARD.stop_dashboard()


# The Jupyter IBMQ dashboard instance
_IQX_DASHBOARD = IQXDashboard()
