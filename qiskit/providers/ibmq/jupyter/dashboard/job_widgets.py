# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""A module of widgets for job tracking."""

from typing import Optional
from datetime import datetime
import ipywidgets as widgets

# pylint:disable=unused-import
from qiskit.providers.ibmq.jupyter.dashboard.dashboard import IQXDashboard
from qiskit.providers.ibmq.runtime.runtime_job import RuntimeJob
from qiskit.providers.ibmq.job.ibmqjob import IBMQJob


def make_rt_jobs_clear_button(watcher: 'IQXDashboard') -> widgets.GridBox:
    """Makes the clear button.

    Args:
        watcher: The watcher widget instance.

    Returns:
        The clear button widget.
    """
    clear = widgets.Button(
        description='Clear',
        layout=widgets.Layout(width='70px',
                              grid_area='right',
                              padding="0px 0px 0px 0px"))

    clear.style.button_color = '#e5d1ff'

    def on_clear_button_clicked(_):
        """Clear finished jobs."""
        watcher.clear_rt_jobs_done()

    clear.on_click(on_clear_button_clicked)

    clear_button = widgets.GridBox(children=[clear],
                                   layout=widgets.Layout(
                                       width='100%',
                                       grid_template_columns='20% 20% 20% 20% 20%',
                                       grid_template_areas='''
                                       ". . . . right "
                                        '''))
    return clear_button


def make_jobs_clear_button(watcher: 'IQXDashboard') -> widgets.GridBox:
    """Makes the clear button.

    Args:
        watcher: The watcher widget instance.

    Returns:
        The clear button widget.
    """
    clear = widgets.Button(
        description='Clear',
        layout=widgets.Layout(width='70px',
                              grid_area='right',
                              padding="0px 0px 0px 0px"))

    clear.style.button_color = '#e5d1ff'

    def on_clear_button_clicked(_):
        """Clear finished jobs."""
        watcher.clear_jobs_done()

    clear.on_click(on_clear_button_clicked)

    clear_button = widgets.GridBox(children=[clear],
                                   layout=widgets.Layout(
                                       width='100%',
                                       grid_template_columns='20% 20% 20% 20% 20%',
                                       grid_template_areas='''
                                       ". . . . right "
                                        '''))
    return clear_button


def make_labels() -> widgets.HBox:
    """Makes the labels widget.

    Returns:
        The labels widget.
    """
    labels0 = widgets.HTML(value="<h5>Job ID</h5>",
                           layout=widgets.Layout(width='190px'))
    labels1 = widgets.HTML(value='<h5>Backend</h5>',
                           layout=widgets.Layout(width='165px'))
    labels2 = widgets.HTML(value='<h5>Status</h5>',
                           layout=widgets.Layout(width='125px'))
    labels3 = widgets.HTML(value='<h5>Est. Start Time</h5>',
                           layout=widgets.Layout(width='100px'))

    labels = widgets.HBox(children=[labels0, labels1, labels2, labels3],
                          layout=widgets.Layout(width='700px',
                                                margin='0px 0px 0px 35px'))
    return labels


def make_rt_labels() -> widgets.HBox:
    """Makes the labels widget.

    Returns:
        The labels widget.
    """
    labels0 = widgets.HTML(value="<h5>Job ID</h5>",
                           layout=widgets.Layout(width='190px'))
    labels1 = widgets.HTML(value='<h5>Program Name</h5>',
                           layout=widgets.Layout(width='165px'))
    labels2 = widgets.HTML(value='<h5>Status</h5>',
                           layout=widgets.Layout(width='125px'))
    labels3 = widgets.HTML(value='<h5>Created at</h5>',
                           layout=widgets.Layout(width='100px'))

    labels = widgets.HBox(children=[labels0, labels1, labels2, labels3],
                          layout=widgets.Layout(width='700px',
                                                margin='0px 0px 0px 35px'))
    return labels


def create_job_widget(watcher: 'IQXDashboard',
                      job: IBMQJob,
                      backend: str,
                      status: str = '',
                      queue_pos: Optional[int] = None,
                      est_start_time: Optional[datetime] = None) -> widgets.HBox:
    """Create a widget corresponding to a particular job instance.

    Args:
        watcher: The job watcher instance.
        job: The job.
        backend: Name of the backend the job is running on.
        status: The job status.
        queue_pos: Queue position, if any.
        est_start_time: Estimated start time, if any.

    Returns:
        The job widget.
    """
    job_id = job.job_id()

    queue_str = ' ({})'.format(queue_pos) if status == 'QUEUED' and queue_pos else ''
    est_time = est_start_time.strftime("%H:%M %Z (%m/%d)") if est_start_time else '-'
    div = "<div style='background-color: lightgrey; width: 2px'></div>"
    labels_str = """<div class='rt_program_entry'>
        <p style='width: 190px;'>{0}</p>{div}
        <p style='width: 165px;'>{1}</p>{div}
        <p style='width: 125px;'>{2}</p>{div}
        <p style='width: 125px;'>{3}</p>
    </div>""".format(
        job_id,
        backend,
        "{}{}".format(status, queue_str),
        est_time,
        div=div
    )
    labels = widgets.HTML(value=labels_str)
    styles = widgets.HTML(value="""<style>
                                    .rt_program_entry {
                                    display: flex;
                                    z-index: 999;
                                    box-shadow: 5px 5px 5px -3px black;
                                    opacity: 0.95;
                                    float: left;
                                    letter-spacing: 1px;
                                    padding: 3px;
                                    }

                                    .rt_program_entry p {
                                        padding: 2px 0px 2px 7px;
                                        white-space: nowrap;
                                        overflow: hidden;
                                        text-overflow: ellipsis;
                                    }

                                    .rt_program_clear_btn {
                                        color: white;
                                    }

                                    </style>""")

    close_button = widgets.Button(button_style='', icon='close',
                                  layout=widgets.Layout(width='30px',
                                                        margin="10px 5px 0px 0px"))
    close_button.style.button_color = '#e5d1ff'

    def cancel_on_click(_):
        """Cancel the job."""
        watcher.cancel_job(job_id)
    close_button.on_click(cancel_on_click)

    job_grid = widgets.HBox(children=[close_button, labels, styles],
                            layout=widgets.Layout(min_width='690px',
                                                  max_width='690px'))
    job_grid.job_id = job_id
    job_grid.job = job
    job_grid.status = status
    return job_grid


def create_job_widget_runtime(watcher: 'IQXDashboard',
                              job: RuntimeJob,
                              status: str = '',
                              program_name: str = '') -> widgets.HBox:
    """Create a widget corresponding to a particular job instance.

    Args:
        watcher: The job watcher instance.
        job: The job.
        status: The job status.
        program_name: the name of the jobs' parent program
    Returns:
        The job widget.
    """
    job_id = job.job_id()

    close_button = widgets.Button(button_style='', icon='close',
                                  layout=widgets.Layout(width='30px',
                                                        margin="10px 5px 0px 0px"))
    close_button.style.button_color = '#e5d1ff'

    created_at = job.creation_date.strftime("%m/%d/%y, %H:%M") if job.creation_date else ''

    div = "<div style='background-color: lightgrey; width: 2px'></div>"
    labels_str = """<div class='rt_program_entry'>
        <p style='width: 190px;'>{0}</p>{div}
        <p style='width: 165px;'>{1}</p>{div}
        <p style='width: 125px;'>{2}</p>{div}
        <p style='width: 125px;'>{3}</p>
    </div>""".format(
        job_id,
        program_name,
        status,
        created_at,
        div=div
    )
    labels = widgets.HTML(value=labels_str)
    styles = widgets.HTML(value="""<style>
                                    .rt_program_entry {
                                    display: flex;
                                    z-index: 999;
                                    box-shadow: 5px 5px 5px -3px black;
                                    opacity: 0.95;
                                    float: left;
                                    letter-spacing: 1px;
                                    padding: 3px;
                                    }

                                    .rt_program_entry p {
                                        padding: 2px 0px 2px 7px;
                                        white-space: nowrap;
                                        overflow: hidden;
                                        text-overflow: ellipsis;
                                    }

                                    .rt_program_clear_btn {
                                        color: white;
                                    }

                                    </style>""")

    # TODO: Get verification that this won't break for runtime jobs.
    def cancel_on_click(_):
        """Cancel the job."""
        watcher.cancel_rt_job(job_id)
    close_button.on_click(cancel_on_click)

    job_grid = widgets.HBox(children=[close_button, labels, styles],
                            layout=widgets.Layout(min_width='690px',
                                                  max_width='690px'))
    job_grid.job_id = job_id
    job_grid.job = job
    job_grid.status = status
    return job_grid
