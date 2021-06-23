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

from abc import abstractmethod
from typing import Callable, List, Tuple, Dict, Optional

import threading
import ipywidgets as wid
from IPython.core.magic import line_magic, Magics, magics_class
from IPython.display import display, Javascript
from ipywidgets import widgets
from ipywidgets import Layout, VBox, Accordion, HBox

from qiskit.tools.events.pubsub import Subscriber
from qiskit.providers.ibmq.job.exceptions import IBMQJobApiError
from qiskit.providers.ibmq.exceptions import IBMQNotAuthorizedError
from qiskit.providers.job import JobV1 as Job
from qiskit.exceptions import QiskitError

from .runtime_program_widget import make_labels as make_program_labels, create_program_widget
from .constants import EXP_JOB_STATUS_LIST, EXP_JOB_STATUS_COLORS_LIST
from .utils import BackendWithProviders, JobType, get_job_type
from .backend_widget import make_backend_widget
from .backend_update import update_backend_info
from .watcher_monitor import job_monitor

from ... import IBMQ
from .job_widgets import (
    make_clear_button,
    make_labels,
    updated_widget_str,
    create_job_widget)


def _add_device_to_list(backend: BackendWithProviders,
                        device_list: wid.VBox) -> None:
    """Add the backend to the device list widget.

    Args:
        backend: Backend to add.
        device_list: Widget showing the devices.
    """
    device_pane = make_backend_widget(backend)
    device_list.children = list(device_list.children) + [device_pane]


def update_job(jobs_wlist: List[HBox],
               update_info: Tuple,
               name_lookup: Dict = None) -> None:
    """Update a single job instance.

    Args:
        jobs_wlist: the list of job widgets
        update_info: the update info
        name_lookup: the runtime program lookup table (key=ID, val=Name).
    """
    # Get constant-place fields from update info
    job_id = update_info[0]
    status = update_info[1]
    # Find job widget with correct `job_id`
    jobw = next((job for job in jobs_wlist if getattr(job, 'job_id') == job_id), None)
    backend = jobw.job.backend()
    if jobw is None:
        return
    job_type = get_job_type(jobw.job)
    # Set the widget's job status (used for convenience)
    jobw.status = status
    # Adjust the UI display
    btn, _, css = jobw.children
    if job_type == JobType.Circuit:
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
                        job_type,
                        [job_id, backend.name(), status, est_start],
                        ['black', 'black', color, 'black'])),
                    css]
    else:
        # retrieve remaining input fields `created_at`
        program_name = name_lookup.get(jobw.job.program_id, '-') if name_lookup else '-'
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
                        job_type,
                        [job_id, backend.name(), program_name, status, created_at],
                        ['black', 'black', 'black', color, 'black'])),
                    css]


def cancel_job(jobs_wlist: List[HBox], job_id: str, name_lookup: Dict = None) -> None:
    """Cancel a job in the watcher.

    Args:
        jobs_wlist: the list of job widgets
        job_id: ID of the job to cancel.
        name_lookup: the runtime program lookup table (key=ID, val=Name).

    Raises:
        Exception: If job ID is not found.
    """
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
            update_job(jobs_wlist, (job_id, status.name, 0, status.value), name_lookup)


def clear_done(jobs_wlist: List[HBox], refresh: Callable[[List], None]) -> None:
    """Clear the done jobs from the list.

    Args:
        jobs_wlist: the job widgets
        refresh: callback function to handle resulting jobs
    """
    active_jobs = []
    do_refresh = False
    # Find the active jobs
    for job in jobs_wlist:
        if job.status not in ['DONE', 'CANCELLED', 'ERROR']:
            active_jobs.append(job)
        else:
            # Close the job and ensure the UI is refreshed
            job.close()
            do_refresh = True
    # Refresh the UI with the active jobs
    if do_refresh:
        refresh(active_jobs)


class DashItem():
    """A UI item on the dashboard"""
    def __init__(self, title: str):
        """Create a dashboard item. (designed for Accordion)

        The item will have a tab which uses `title`
        and a vertical content box (`box`).

        Args:
            title: the title of the tab
        """
        self.title = title
        self.box = VBox(layout=Layout(width='760px',
                                      max_height='650px'))

    # pylint: disable=invalid-name
    def ui(self) -> widgets.Widget:
        """Get the content box (widget) for the dashboard item.

        Returns:
           the content box
        """
        return self.box

    @abstractmethod
    def refresh(self) -> None:
        """Refresh the UI"""
        pass

    def start(self) -> None:
        """Start (load and display) the UI"""
        pass

    def stop(self) -> None:
        """Stop and take down the UI"""
        pass


class JobUI(DashItem, Subscriber):
    """Dashboard item for a job (generic)."""

    def __init__(self, title: str):
        """Create a dashboard item for the job.

        Args:
            title: the tab title
        """
        # Initialize superclasses (DashItem, Subscriber)
        super().__init__('%s Jobs' % title)
        Subscriber.__init__(self)
        # Setup variables
        self.jobs = []  # type: List
        self._clear_button = None  # type: wid.GridBox
        self._labels = None  # type: wid.HBox

    def _add_job(self, job: Job) -> None:
        """Callback function when a job start event is received.

        When a job starts, this function creates a job widget and adds
        the widget to the list of jobs the dashboard keeps tracking.

        Args:
            job: Job to start watching.
        """
        prog_name = '-'
        # Use program name lookup, if applicable
        try:
            prog_name = getattr(self, 'program_name_lookup').get(job.program_id, '-')
        except AttributeError:
            pass

        job_widget = create_job_widget(self, job,
                                       program_name=prog_name)

        self.jobs.append(job_widget)

        # Add a monitor for the new job
        job_monitor(job, self)

        # Clean and refresh UI
        if len(self.jobs) > 50:
            self.clear_done()
        else:
            self.refresh()

    @abstractmethod
    def update_job(self, update_info: Tuple) -> None:
        """Update the job widget with new info.

        Args:
            update_info: the info
        """
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> None:
        """Cancel the job.

        Args:
            job_id: the job id
        """
        pass

    @abstractmethod
    def clear_done(self) -> None:
        """Clear out inactive jobs"""
        pass

    @abstractmethod
    def _init_subscriber(self) -> None:
        """Setup the listener for new jobs"""
        pass

    @abstractmethod
    def _remove_subscriber(self) -> None:
        """Setup the listener for new jobs"""
        pass

    def start(self) -> None:
        """Starts the widget"""
        self._init_subscriber()
        self.refresh()

    def stop(self) -> None:
        """Stops the widget"""
        try:
            self._remove_subscriber()
        except ValueError:
            pass


class CircuitJobUI(JobUI):
    """A dashboard item for a circuit job"""

    def __init__(self):
        super().__init__('Circuit')
        self.jobs = []  # type: List
        self._clear_button = make_clear_button(self)  # type: wid.GridBox
        self._labels = make_labels(JobType.Circuit)  # type: wid.HBox
        self.refresh()

    def refresh(self, jobs: List[HBox] = None):  # pylint: disable=arguments-differ
        """Refresh the job viewer.

        Args:
            jobs: the list of jobs
        """
        if not jobs:
            jobs = self.jobs
        self.box.children = [self._clear_button, self._labels] + list(reversed(jobs))

    def update_job(self, update_info: Tuple) -> None:
        update_job(self.jobs, update_info)

    def cancel_job(self, job_id: str) -> None:
        cancel_job(self.jobs, job_id)

    def clear_done(self) -> None:
        clear_done(self.jobs, self.refresh)

    def _init_subscriber(self) -> None:
        self.subscribe("ibmq.job.start", self._add_job)

    def _remove_subscriber(self) -> None:
        self.unsubscribe("ibmq.job.start", self._add_job)


class RuntimeJobUI(JobUI):
    """A dashboard item for a runtime job"""

    def __init__(self, program_name_lookup: Dict = None):
        """Create a dashboard item for a runtime job.

        Args:
            program_name_lookup: the lookup dict for runtime program names (key=id, val=name)
        """
        super().__init__('Runtime')
        self.jobs = []  # type: List
        self._clear_button = make_clear_button(self)  # type: wid.GridBox
        self._labels = make_labels(JobType.Runtime)  # type: wid.HBox
        # Runtime program dictionary. keys = RuntimeProgram.id, vals=RuntimeProgram.name
        self.program_name_lookup = program_name_lookup or {}
        self.refresh()

    def refresh(self, jobs: List[HBox] = None):  # pylint: disable=arguments-differ
        """Refresh the job viewer.

        Args:
            jobs: the list of jobs
        """
        if not jobs:
            jobs = self.jobs
        self.box.children = [self._clear_button, self._labels] + list(reversed(jobs))

    def update_job(self, update_info: Tuple) -> None:
        update_job(self.jobs, update_info, self.program_name_lookup)

    def cancel_job(self, job_id: str) -> None:
        cancel_job(self.jobs, job_id, self.program_name_lookup)

    def clear_done(self) -> None:
        clear_done(self.jobs, self.refresh)

    def _init_subscriber(self) -> None:
        self.subscribe("ibmq.runtimejob.start", self._add_job)

    def _remove_subscriber(self) -> None:
        self.unsubscribe("ibmq.runtimejob.start", self._add_job)

    def set_program_names(self, program_names_lookup: Dict[str, str]):
        """Set the lookup table.

        Args:
            program_names_lookup (Dict[str, str]): the program names lookup table
        """
        self.program_name_lookup = program_names_lookup


class RuntimeProgramUI(DashItem):
    """A dashboard item for a runtime program"""

    def __init__(self):
        super().__init__('Runtime Program')
        # A list of runtime programs.
        self.runtime_programs = []
        # Runtime tab on the dashboard.
        self._labels = make_program_labels()  # type: wid.HBox
        # Program name lookup
        self.program_name_lookup = {}
        # callback for when program names are fetched
        self._on_fetch_program_names = None

    def refresh(self) -> None:
        self.box.children = [self._labels]
        for program in self.runtime_programs:
            program_pane = create_program_widget(program)
            self.box.children += (program_pane, )

    def start(self) -> None:
        self._get_runtime_programs()
        self.refresh()

    def stop(self) -> None:
        self.runtime_programs = []

    def _get_runtime_programs(self) -> None:
        """Get all the runtime programs on this account."""

        programs = []
        self.program_name_lookup = {}
        providers = IBMQ.providers()

        if len(providers) > 0:
            try:
                # Get default provider's runtime programs
                programs = providers[0].runtime.programs()

                # Fill in the lookup dictionary.
                # This dictionary is to reduce API calls for showing `name`
                # prop of Jobs' parent program on the Dashboard UI
                for prog in programs:
                    self.program_name_lookup[prog.program_id] = prog.name
                self.runtime_programs = programs
                if self._on_fetch_program_names:
                    self._on_fetch_program_names(self.program_name_lookup)
            except IBMQNotAuthorizedError:
                # User does not have access to Qiskit Runtime
                pass

    def on_fetch_program_names(self, callback: Callable[[Dict[str, str]], None]) -> None:
        """Set a callback to be executed when program names are fetched

        Args:
            callback (Callable[[Dict[str, str]], None]): the callback
        """
        self._on_fetch_program_names = callback


class DevicesUI(DashItem):
    """A dashboard item for the backend devices list"""

    def __init__(self):
        super().__init__('Devices')
        # Backend dictionary. The keys are the backend names and the values
        # are named tuples of ``IBMQBackend`` instances and a list of provider names.
        self.backend_dict = None  # type: Optional[Dict[str, BackendWithProviders]]
        self._update_thread = None
        self.setup_device_ui()
        # Load the backends
        self._get_backends()
        # Refresh
        self.refresh()

    def setup_device_ui(self) -> None:
        """Setup the devices list UI"""
        self.box = wid.VBox(children=[],
                            layout=wid.Layout(width='740px', height='100%'))

    def refresh(self) -> None:
        for _wid in self.box.children:
            _wid.close()
        self.box.children = []
        for back in self.backend_dict.values():
            _thread = threading.Thread(target=_add_device_to_list,
                                       args=(back, self.box))
            _thread.start()

    def start(self) -> None:
        # Devices
        self.setup_device_ui()
        self._get_backends()
        self._update_thread = threading.Thread(target=update_backend_info,
                                               args=(self.box,))
        self._update_thread.do_run = True
        self._update_thread.start()
        self.refresh()

    def stop(self) -> None:
        try:
            for _wid in self.box.children:
                _wid.close()
        except AttributeError:
            pass
        self.box.children = []
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.do_run = False
            self._update_thread.join()

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


def accordion(items: List[DashItem]) -> Accordion:
    """Generate an accordion from a list of dashboard items

    Args:
        items: the dashboard items

    Returns:
        Accordion: the accordion
    """
    tabs = wid.Tab(layout=Layout(width='760px',
                                 max_height='650px'))
    for i, item in enumerate(items):
        tabs.children += (item.ui(), )
        tabs.set_title(i, item.title)

    acc = Accordion(children=[tabs],
                    layout=Layout(width='auto',
                                  max_height='700px',
                                  border='1px solid black'))
    acc.set_title(0, 'IBM Quantum Dashboard')
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


class IBMQDashboard:
    """The IBM Quantum Experience Dashboard"""

    def __init__(self) -> None:
        # Create views
        self.runtime_jobs = RuntimeJobUI()
        self.circuit_jobs = CircuitJobUI()
        self.runtime_progs = RuntimeProgramUI()
        self.devices = DevicesUI()
        # self.runtime_programs = RuntimeJobUI()
        self.views = [
            self.devices,
            self.circuit_jobs,
            self.runtime_jobs,
            self.runtime_progs,
        ]
        # perform other ops
        self.runtime_progs.on_fetch_program_names(self.runtime_jobs.set_program_names)
        # Add views to the viewport
        self.viewport = accordion(self.views)

    def start(self) -> None:
        """Starts all child views"""
        for view in self.views:
            view.start()
        self.update()

    def stop(self) -> None:
        """Stops all child views"""
        for view in self.views:
            view.stop()
        self.update()

    def refresh(self) -> None:
        """Refreshes all child views"""
        for view in self.views:
            view.refresh()
        self.update()

    def update(self):
        """Update the UI to reflect child views"""
        self.viewport.children[0].children = [view.ui() for view in self.views]


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
        _IQX_DASHBOARD.stop()
        _IQX_DASHBOARD.start()

    @line_magic
    def disable_ibmq_dashboard(self, line='', cell=None) -> None:
        """A Jupyter magic function to disable the dashboard."""
        # pylint: disable=unused-argument
        _IQX_DASHBOARD.stop()


_IQX_DASHBOARD = IBMQDashboard()
"""The Jupyter IBM Quantum Experience dashboard instance."""
