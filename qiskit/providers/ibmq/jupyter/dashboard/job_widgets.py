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

"""A module of widgets for job tracking."""

from typing import Optional
from datetime import datetime

import ipywidgets as widgets

from qiskit.providers.ibmq.job.ibmqjob import IBMQJob
from qiskit.providers.ibmq.utils.converters import utc_to_local


def make_clear_button(watcher: 'IQXDashboard') -> widgets.GridBox:
    """Makes the clear button.

    Args:
        watcher: The watcher widget instance.

    Returns:
        The clear button widget.
    """
    clear = widgets.Button(
        description='Clear',
        button_style='primary',
        layout=widgets.Layout(width='70px',
                              grid_area='right',
                              padding="0px 0px 0px 0px"))

    def on_clear_button_clicked(_):
        """Clear finished jobs."""
        watcher.clear_done()

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

    id_label = widgets.HTML(value="{}".format(job_id),
                            layout=widgets.Layout(width='190px'))
    backend_label = widgets.HTML(value="{}".format(backend),
                                 layout=widgets.Layout(width='165px'))

    queue_str = ' ({})'.format(queue_pos) if status == 'QUEUED' and queue_pos else ''
    status_label = widgets.HTML(value="{}{}".format(status, queue_str),
                                layout=widgets.Layout(width='125px'))

    est_time = utc_to_local(est_start_time).strftime("%H:%M %Z (%m/%d)") if est_start_time else '-'
    est_time_label = widgets.HTML(value="{}".format(est_time),
                                  layout=widgets.Layout(width='125px'))

    close_button = widgets.Button(button_style='', icon='close',
                                  layout=widgets.Layout(width='30px',
                                                        margin="0px 5px 0px 0px"))
    close_button.style.button_color = 'white'

    def cancel_on_click(_):
        """Cancel the job."""
        watcher.cancel_job(job_id)
    close_button.on_click(cancel_on_click)

    job_grid = widgets.HBox(children=[close_button, id_label, backend_label,
                                      status_label, est_time_label],
                            layout=widgets.Layout(min_width='690px',
                                                  max_width='690px'))
    job_grid.job_id = job_id
    job_grid.job = job
    return job_grid
