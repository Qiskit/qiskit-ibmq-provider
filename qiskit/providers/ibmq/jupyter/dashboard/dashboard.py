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

from typing import List, Tuple, Dict, Any, Optional

import threading
import ipywidgets as wid
from IPython.core.magic import line_magic, Magics, magics_class
from IPython.display import display, Javascript

from qiskit.tools.events.pubsub import Subscriber
from qiskit.providers.ibmq.job.exceptions import IBMQJobApiError
from qiskit.providers.job import JobV1 as Job
from qiskit.exceptions import QiskitError

from .runtime_program_widget import make_labels as make_program_labels, create_program_widget
from .constants import EXP_JOB_STATUS_LIST, EXP_JOB_STATUS_COLORS_LIST
from .utils import BackendWithProviders, JobType, get_job_type
from .backend_widget import make_backend_widget
from .backend_update import update_backend_info
from .watcher_monitor import _job_monitor

from ... import IBMQ
from .job_widgets import (
    make_clear_button,
    make_labels,
    make_rt_labels,
    updated_widget_str,
    create_job_widget)


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
        self.jobs = []     # type: List
        self.rt_jobs = []  # type: List

        self._init_subscriber()
        self.dashboard = None  # type: Optional[AccordionWithThread]

        # Backend dictionary. The keys are the backend names and the values
        # are named tuples of ``IBMQBackend`` instances and a list of provider names.
        self.backend_dict = None  # type: Optional[Dict[str, BackendWithProviders]]

        # Runtime program dictionary. keys = RuntimeProgram.id, vals=RuntimeProgram.name
        self.rt_program_name_lookup: Dict = {}

        # Jobs tab on the dashboard.
        self.job_viewer = None  # type: Optional[wid.VBox]
        self._clear_jobs_button = make_clear_button(self, JobType.IBMQ)  # type: wid.GridBox
        self._jobs_labels = make_labels()  # type: wid.HBox
        # Runtime Jobs tab on the dashboard
        self.rt_job_viewer = None  # type: Optional[wid.VBox]
        self._clear_rt_jobs_button = make_clear_button(self, JobType.Runtime)  # type: wid.GridBox
        self._rt_jobs_labels = make_rt_labels()  # type: wid.HBox

        self.refresh_jobs_board(JobType.Runtime)
        self.refresh_jobs_board(JobType.IBMQ)

        # Runtime Display

        # A list of runtime programs. Each has a name and description.
        self.runtime_programs = {}
        # Runtime tab on the dashboard.
        self.runtime_viewer = None  # type: Optional[wid.VBox]
        self.runtime_labels = make_program_labels()  # type: wid.HBox
        self._get_runtime_programs()
        self.refresh_runtime_programs()

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

    def _get_runtime_programs(self) -> None:
        """Get all the runtime programs on this account."""

        programs = {}
        self.rt_program_name_lookup = {}
        for pro in IBMQ.providers():
            # Store the programs in a dictionary.
            # A dictionary here is to allow them to be filtered/sectioned in later
            # implementions
            pro_name = "{hub}/{group}/{project}".format(hub=pro.credentials.hub,
                                                        group=pro.credentials.group,
                                                        project=pro.credentials.project)
            programs[pro_name] = pro.runtime.programs()

            # Fill in the lookup dictionary.
            # This dictionary is to reduce API calls for showing `name`
            # prop of Jobs' parent program on the Dashboard UI
            for prog in programs[pro_name]:
                self.rt_program_name_lookup[prog.program_id] = prog.name
        self.runtime_programs = programs

    def refresh_jobs_board(self, job_type: JobType) -> None:
        """Refresh the job viewer.

        Args:
            job_type: the job type
        """
        if job_type == JobType.IBMQ and self.job_viewer is not None:
            self.job_viewer.children = [self._clear_jobs_button,
                                        self._jobs_labels] + list(reversed(self.jobs))
        elif job_type == JobType.Runtime and self.rt_job_viewer is not None:
            self.rt_job_viewer.children = [self._clear_rt_jobs_button,
                                           self._rt_jobs_labels] + list(reversed(self.rt_jobs))

    def refresh_runtime_programs(self) -> None:
        """Refresh the runtime viewer."""
        if self.runtime_viewer is not None:

            self.runtime_viewer.children = [self.runtime_labels]

            # TODO: Integrate the keys here (hub info) into view
            # as sections
            for _, programs in self.runtime_programs.items():
                for pro in programs:
                    program_pane = create_program_widget(pro)
                    self.runtime_viewer.children += (program_pane, )

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
        # Build the dashboard and initialize tab views
        self.dashboard = build_dashboard_widget()
        self.job_viewer = self.dashboard.children[0].children[1]
        self.runtime_viewer = self.dashboard.children[0].children[2]
        self.rt_job_viewer = self.dashboard.children[0].children[3]
        # Fetch backend device info
        self._get_backends()
        self.refresh_device_list()
        self.dashboard._thread = threading.Thread(target=update_backend_info,
                                                  args=(self.dashboard._device_list,))
        self.dashboard._thread.do_run = True
        self.dashboard._thread.start()
        # Update jobs info
        self.refresh_jobs_board(JobType.Runtime)
        self.refresh_jobs_board(JobType.IBMQ)
        # Update runtime program info
        self.refresh_runtime_programs()

    def stop_dashboard(self) -> None:
        """Stops the dashboard."""
        if self.dashboard:
            self.dashboard._thread.do_run = False
            self.dashboard._thread.join()
            self.dashboard.close()
        self.dashboard = None

    def update_single_job(self, job_type: JobType, update_info: Tuple) -> None:
        """Update a single job instance.

        Args:
            job_type: The job type
            update_info: Updated job info.
                For an IBMQ Job, contains:
                    job ID (str)
                    status (str)
                    est time (int)
                For a Runtime job, contains:
                    job ID (str)
                    status (str)
        """
        # Get constant-place fields from update info
        job_id = update_info[0]
        status = update_info[1]
        # Establish which jobs list to use (Runtime or IBMQ)
        jobs_list = self.rt_jobs if job_type == JobType.Runtime else self.jobs
        # Find job widget with correct `job_id`
        jobw = next((job for job in jobs_list if getattr(job, 'job_id') == job_id), None)
        backend = jobw.job.backend()
        if jobw is None:
            return
        # Set the widget's job status (used for convenience)
        jobw.status = status
        # Adjust the UI display
        btn, _, css = jobw.children
        if job_type == JobType.IBMQ:
            # update estimated start time.
            if update_info[2] == 0:
                est_start = '-'
            else:
                est_start = str(update_info[2])
            # update status
            for target_status, color in zip(EXP_JOB_STATUS_LIST, EXP_JOB_STATUS_COLORS_LIST):
                if target_status == status:
                    # rebuild the job widget
                    # note: `children` stored as tuple so must rebuild entirely
                    jobw.children = [
                        btn,
                        wid.HTML(updated_widget_str(
                            [job_id, backend, status, est_start],
                            ['black', 'black', color, 'black'])),
                        css]
        else:
            # retrieve remaining input fields `created_at`
            program_name = self.rt_program_name_lookup.get(jobw.job.program_id, '-')
            created_at = jobw.job.creation_date.strftime("%m/%d/%y, %H:%M") \
                if jobw.job.creation_date else ''
            # update status
            for target_status, color in zip(EXP_JOB_STATUS_LIST, EXP_JOB_STATUS_COLORS_LIST):
                if target_status == status:
                    # rebuild the job widget
                    # note: `children` stored as tuple so must rebuild entirely
                    jobw.children = [
                        btn,
                        wid.HTML(updated_widget_str(
                            [job_id, program_name, status, created_at],
                            ['black', 'black', color, 'black'])),
                        css]

    def cancel_job(self, job_id: str, job_type: JobType) -> None:
        """Cancel a job in the watcher.

        Args:
            job_id: ID of the job to cancel.
            job_type: the job type

        Raises:
            Exception: If job ID is not found.
        """
        # Establish which jobs widget list to use (Runtime or IBMQ)
        jobs_wlist = self.rt_jobs if job_type == JobType.Runtime else self.jobs
        # Find job widget with correct `job_id`
        jobw = next((job for job in jobs_wlist if getattr(job, 'job_id') == job_id), None)
        if jobw is None:
            raise Exception('Job is not found.')
        # If the job status is not active, Cancel.
        if jobw.status not in ['CANCELLED', 'DONE', 'ERROR']:
            try:
                jobw.job.cancel()
                status = jobw.job.status()
            except IBMQJobApiError:
                pass
            else:
                self.update_single_job(job_type, (job_id, status.name, 0, status.value))

    def clear_done(self, job_type: JobType) -> None:
        """Clear the done jobs from the list.

        Args:
            job_type: the job type
        """
        # Determine the list of job widgets to use
        jobs = self.jobs if job_type == JobType.IBMQ else self.rt_jobs

        active_jobs = []
        do_refresh = False
        # Find the active jobs
        for job in jobs:
            if job.status not in ['DONE', 'CANCELLED', 'ERROR']:
                active_jobs.append(job)
            else:
                # Close the job and ensure the UI is refreshed
                job.close()
                do_refresh = True
        # Refresh the UI with the active jobs
        if do_refresh:
            if job_type == JobType.IBMQ:
                self.jobs = active_jobs
            else:
                self.rt_jobs = active_jobs
        self.refresh_jobs_board(job_type)

    def _init_subscriber(self) -> None:
        """Initializes a subscriber that listens to job start events."""

        def _add_job(job: Job) -> None:
            """Callback function when a job start event is received.

            When a job starts, this function creates a job widget and adds
            the widget to the list of jobs the dashboard keeps tracking.

            Args:
                job: Job to start watching.
            """
            # Get job status and type
            status = job.status()
            job_type = get_job_type(job)

            # Create a widget for the new job and add to list
            if job_type == JobType.IBMQ:
                queue_info = job.queue_info()
                position = queue_info.position if queue_info else None
                est_time = queue_info.estimated_start_time if queue_info else None
                job_widget = create_job_widget(self, job,
                                               job.backend().name(),
                                               status.name,
                                               queue_pos=position,
                                               est_start_time=est_time)
                self.jobs.append(job_widget)
                jobs = self.jobs
            else:
                # The job is a runtime job.
                prog_name = self.rt_program_name_lookup.get(job.program_id, '-')
                job_widget = create_job_widget(self, job,
                                               job._backend.name(),
                                               status.name,
                                               program_name=prog_name)
                self.rt_jobs.append(job_widget)
                jobs = self.rt_jobs

            # Add a monitor for the new job
            _job_monitor(job, status, self)

            # Clean and refresh UI
            if len(jobs) > 50:
                self.clear_done(job_type)
            else:
                self.refresh_jobs_board(job_type)

        # Listen for new jobs (IBMQJob, RuntimeJob)
        self.subscribe("ibmq.job.start", _add_job)
        self.subscribe("ibmq.runtimejob.start", _add_job)


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

    rt_programs_box = wid.VBox(layout=wid.Layout(max_width='740px',
                                                 min_width='740px',
                                                 justify_content='flex-start'))

    rt_jobs_box = wid.VBox(layout=wid.Layout(max_width='740px',
                                             min_width='740px',
                                             justify_content='flex-start'))

    tabs.children = [device_list, jobs_box, rt_programs_box, rt_jobs_box]
    tabs.set_title(0, 'Devices')
    tabs.set_title(1, 'Jobs')
    tabs.set_title(2, 'Programs (Runtime)')
    tabs.set_title(3, 'Jobs (Runtime)')

    acc = AccordionWithThread(children=[tabs],
                              layout=wid.Layout(width='auto',
                                                max_height='700px',
                                                ))

    acc._device_list = acc.children[0].children[0].children[0]

    acc.set_title(0, 'IBM Quantum dashboard')
    acc.selected_index = None
    acc.layout.visibility = 'hidden'
    display(acc)
    acc._dom_classes = ['job_widget', 'rt_programs', 'rt_jobs']
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
