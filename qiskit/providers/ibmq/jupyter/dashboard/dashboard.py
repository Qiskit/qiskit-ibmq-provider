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

"""The core IBM Quantum Experience dashboard launcher."""

import threading
from typing import List, Tuple, Dict, Any, Optional

import ipywidgets as wid
from IPython.display import display, Javascript
from IPython.core.magic import line_magic, Magics, magics_class
from qiskit.tools.events.pubsub import Subscriber
from qiskit.exceptions import QiskitError
from qiskit.providers.ibmq.job.exceptions import IBMQJobApiError
from qiskit.providers.ibmq.job.ibmqjob import IBMQJob

from ... import IBMQ
from .job_widgets import (make_clear_button,
                          make_labels, create_job_widget)
from .backend_widget import make_backend_widget
from .backend_update import update_backend_info
from .watcher_monitor import _job_monitor
from .utils import BackendWithProviders


class AccordionWithThread(wid.Accordion):
    """An ``Accordion`` that will close an attached thread."""

    def __init__(self,
                 children: Optional[List] = None,
                 **kwargs: Any):
        """AccordionWithThread constructor.

        Args:
            children: A list of widgets to be attached to the accordion.
            **kwargs: Additional keywords to be passed to ``ipywidgets.Accordion``.
        """
        children = children or []
        super(AccordionWithThread, self).__init__(children=children, **kwargs)
        self._thread = None
        # Devices VBox.
        self._device_list = None  # type: Optional[wid.VBox]

    def __del__(self):
        """Object disposal."""
        if hasattr(self, '_thread'):
            try:
                self._thread.do_run = False
                self._thread.join()
            except Exception:  # pylint: disable=broad-except
                pass
        self.close()


def _add_device_to_list(backend: BackendWithProviders,
                        device_list: wid.VBox) -> None:
    """Add the backend to the device list widget.

    Args:
        backend: Backend to add.
        device_list: Widget showing the devices.
    """
    device_pane = make_backend_widget(backend)
    device_list.children = list(device_list.children) + [device_pane]


class IQXDashboard(Subscriber):
    """An IBM Quantum Experience dashboard.

    This dashboard shows both device and job information.
    """

    def __init__(self):
        """IQXDashboard constructor."""
        super().__init__()

        # A list of job widgets. Each represents a job and has 5 children:
        # close button, Job ID, backend, status, and estimated start time.
        self.jobs = []  # type: List

        self._init_subscriber()
        self.dashboard = None  # type: Optional[AccordionWithThread]

        # Backend dictionary. The keys are the backend names and the values
        # are named tuples of ``IBMQBackend`` instances and a list of provider names.
        self.backend_dict = None  # type: Optional[Dict[str, BackendWithProviders]]

        # Jobs tab on the dashboard.
        self.job_viewer = None  # type: Optional[wid.VBox]
        self._clear_jobs_button = make_clear_button(self)  # type: wid.GridBox
        self._jobs_labels = make_labels()  # type: wid.HBox
        self.refresh_jobs_board()

    def _get_backends(self) -> None:
        """Get all the backends accessible with this account."""

        ibmq_backends = {}
        for pro in IBMQ.providers():
            pro_name = "{hub}/{group}/{project}".format(hub=pro.credentials.hub,
                                                        group=pro.credentials.group,
                                                        project=pro.credentials.project)
            for back in pro.backends():
                if not back.configuration().simulator:
                    if back.name() not in ibmq_backends.keys():
                        ibmq_backends[back.name()] = \
                            BackendWithProviders(backend=back, providers=[pro_name])
                    else:
                        ibmq_backends[back.name()].providers.append(pro_name)

        self.backend_dict = ibmq_backends

    def refresh_jobs_board(self) -> None:
        """Refresh the job viewer."""
        if self.job_viewer is not None:
            self.job_viewer.children = [self._clear_jobs_button,
                                        self._jobs_labels] + list(reversed(self.jobs))

    def refresh_device_list(self) -> None:
        """Refresh the list of devices."""
        for _wid in self.dashboard._device_list.children:
            _wid.close()
        self.dashboard._device_list.children = []
        for back in self.backend_dict.values():
            _thread = threading.Thread(target=_add_device_to_list,
                                       args=(back, self.dashboard._device_list))
            _thread.start()

    def start_dashboard(self) -> None:
        """Starts the dashboard."""
        self.dashboard = build_dashboard_widget()
        self.job_viewer = self.dashboard.children[0].children[1]
        self._get_backends()
        self.refresh_device_list()
        self.dashboard._thread = threading.Thread(target=update_backend_info,
                                                  args=(self.dashboard._device_list,))
        self.dashboard._thread.do_run = True
        self.dashboard._thread.start()
        self.refresh_jobs_board()

    def stop_dashboard(self) -> None:
        """Stops the dashboard."""
        if self.dashboard:
            self.dashboard._thread.do_run = False
            self.dashboard._thread.join()
            self.dashboard.close()
        self.dashboard = None

    def update_single_job(self, update_info: Tuple) -> None:
        """Update a single job instance.

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
            # update estimated start time.
            if update_info[2] == 0:
                est_start = '-'
            else:
                est_start = str(update_info[2])
            job_wid.children[4].value = est_start

    def cancel_job(self, job_id: str) -> None:
        """Cancel a job in the watcher.

        Args:
            job_id: ID of the job to cancel.

        Raises:
            Exception: If job ID is not found.
        """
        do_pop = False
        ind = None
        for idx, job in enumerate(self.jobs):
            if job.job_id == job_id:
                do_pop = True
                ind = idx
                break
        if not do_pop:
            raise Exception('Job is not found.')
        if self.jobs[ind].children[3].value not in ['CANCELLED',
                                                    'DONE',
                                                    'ERROR']:
            try:
                self.jobs[ind].job.cancel()
                status = self.jobs[ind].job.status()
            except IBMQJobApiError:
                pass
            else:
                self.update_single_job((self.jobs[ind].job_id,
                                        status.name, 0,
                                        status.value))

    def clear_done(self) -> None:
        """Clear the done jobs from the list."""
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

    def _init_subscriber(self) -> None:
        """Initializes a subscriber that listens to job start events."""

        def _add_job(job: IBMQJob) -> None:
            """Callback function when a job start event is received.

            When a job starts, this function creates a job widget and adds
            the widget to the list of jobs the dashboard keeps tracking.

            Args:
                job: Job to start watching.
            """
            status = job.status()
            queue_info = job.queue_info()
            position = queue_info.position if queue_info else None
            est_time = queue_info.estimated_start_time if queue_info else None
            job_widget = create_job_widget(self, job,
                                           job.backend().name(),
                                           status.name,
                                           position,
                                           est_time)
            self.jobs.append(job_widget)
            _job_monitor(job, status, self)

            if len(self.jobs) > 50:
                self.clear_done()
            else:
                self.refresh_jobs_board()

        self.subscribe("ibmq.job.start", _add_job)


def build_dashboard_widget() -> AccordionWithThread:
    """Build the dashboard widget.

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

    acc = AccordionWithThread(children=[tabs],
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
    """A class for enabling/disabling the IBM Quantum Experience dashboard."""

    @line_magic
    def iqx_dashboard(self, line='', cell=None) -> None:
        """A Jupyter magic function to enable the dashboard."""
        # pylint: disable=unused-argument
        pro = IBMQ.providers()
        if not pro:
            try:
                IBMQ.load_account()
            except Exception:
                raise QiskitError(
                    "Could not load IBM Quantum Experience account from the local file.")
            else:
                pro = IBMQ.providers()
                if not pro:
                    raise QiskitError(
                        "No providers found.  Must load your IBM Quantum Experience account.")
        _IQX_DASHBOARD.stop_dashboard()
        _IQX_DASHBOARD.start_dashboard()

    @line_magic
    def disable_ibmq_dashboard(self, line='', cell=None) -> None:
        """A Jupyter magic function to disable the dashboard."""
        # pylint: disable=unused-argument
        _IQX_DASHBOARD.stop_dashboard()


_IQX_DASHBOARD = IQXDashboard()
"""The Jupyter IBM Quantum Experience dashboard instance."""
