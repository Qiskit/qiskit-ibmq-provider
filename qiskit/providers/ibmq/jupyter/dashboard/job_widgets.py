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

from typing import List
import ipywidgets as widgets

from qiskit.providers.job import JobV1
from .utils import JobType, get_job_type
from .constants import LIST_COL_DIV, LIST_STYLE_WIDGET, DASH_JOB_HTML, \
    DASH_RT_JOB_HTML, CIRC_JOB_LABELS, RT_JOB_LABELS


# Represents an updated widget's HTML string
# pylint: disable=dangerous-default-value
def updated_widget_str(job_type: JobType,
                       fields: List[str] = [],
                       colors: List[str] = ['black'] * 4) -> str:
    """ Returns the job item's HTML, with the provided color injected into the status field

    Args:
        job_type: the job's type
        fields: the field values to go into the widget html template
        colors: the colors to style the fields' text with

    Returns:
        str: the widget's HTML string
    """
    html = DASH_RT_JOB_HTML if job_type == JobType.Runtime else DASH_JOB_HTML
    return html.format(
        *fields,
        *colors,
        div=LIST_COL_DIV
    )


def make_clear_button(watcher: 'IQXDashboard', job_type: JobType) -> widgets.GridBox:
    """Makes the clear button.

    Args:
        watcher: The watcher widget instance.
        job_type: the job type to have their list cleared

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
        watcher.clear_done(job_type)

    clear.on_click(on_clear_button_clicked)

    clear_button = widgets.GridBox(children=[clear],
                                   layout=widgets.Layout(
                                       width='100%',
                                       grid_template_columns='20% 20% 20% 20% 20%',
                                       grid_template_areas='''
                                       ". . . . right "
                                        '''))
    return clear_button


def make_labels(job_type: JobType) -> widgets.HBox:
    """Makes the labels widget.

    Returns:
        The labels widget.
    """

    labels = CIRC_JOB_LABELS if job_type == JobType.Circuit else RT_JOB_LABELS

    children = [widgets.HTML(value='<h5>%s</h5>' % label,
                             layout=widgets.Layout(width='%dpx' % width))
                for (label, width) in labels]

    width = sum(width for _, width in labels)

    labels = widgets.HBox(children=children,
                          layout=widgets.Layout(width='%dpx' % (width + 50),
                                                margin='0px 0px 0px 35px'))
    return labels


def make_rt_labels() -> widgets.HBox:
    """Makes the labels widget.

    Returns:
        The labels widget.
    """

    labels0 = widgets.HTML(value="<h5>Job ID</h5>",
                           layout=widgets.Layout(width='200px'))
    labels1 = widgets.HTML(value="<h5>Backend</h5>",
                           layout=widgets.Layout(width='125px'))
    labels2 = widgets.HTML(value='<h5>Program Name</h5>',
                           layout=widgets.Layout(width='175px'))
    labels3 = widgets.HTML(value='<h5>Status</h5>',
                           layout=widgets.Layout(width='100px'))
    labels4 = widgets.HTML(value='<h5>Created at</h5>',
                           layout=widgets.Layout(width='100px'))

    labels = widgets.HBox(children=[labels0, labels1, labels2, labels3, labels4],
                          layout=widgets.Layout(width='750px',
                                                margin='0px 0px 0px 35px'))
    return labels


def create_job_widget(watcher: 'IQXDashboard',
                      job: JobV1,
                      **kwargs) -> widgets.HBox:
    """Create a widget corresponding to a particular job instance.

    Args:
        watcher: The job watcher instance.
        job: The job.
        kwargs: additional information for IBMQJob. Consists of:
            queue_pos: Queue position
            est_start_time: Estimated start time

    Returns:
        The job widget.
    """
    # Get the job info
    job_id = job.job_id()
    status = job.status().name
    job_type = get_job_type(job)
    backend = job.backend().name()

    # Generate the fields to be displayed

    if job_type == JobType.Circuit:

        queue_pos = kwargs.get('queue_pos')
        est_start_time = kwargs.get('est_start_time')

        queue_str = ' ({})'.format(queue_pos) if status == 'QUEUED' and queue_pos else ''
        est_time = est_start_time.strftime("%H:%M %Z (%m/%d)") if est_start_time else '-'

        fields = [job_id, backend, "{}{}".format(status, queue_str), est_time]

    else:

        program_name = kwargs.get('program_name')
        created_at = job.creation_date.strftime("%m/%d/%y, %H:%M") if job.creation_date else ''

        fields = [job_id, backend, program_name, status, created_at]

    # Put the fields into an HTML string
    labels_str = updated_widget_str(job_type, fields, ['black'] * len(fields))
    # Generate HTML widgets
    labels = widgets.HTML(value=labels_str)
    styles = widgets.HTML(value=LIST_STYLE_WIDGET)

    # Create a close button to cancel the job
    close_button = widgets.Button(button_style='', icon='close',
                                  layout=widgets.Layout(width='30px',
                                                        margin="10px 5px 0px 0px"))
    close_button.style.button_color = '#e5d1ff'

    def cancel_on_click(_):
        """Cancel the job."""
        watcher.cancel_job(job_id, job_type)
    close_button.on_click(cancel_on_click)

    # Generate the widget grid with the button and HTML table widgets
    job_grid = widgets.HBox(children=list([close_button, labels, styles]),
                            layout=widgets.Layout(min_width='700px',
                                                  max_width='700px'))
    job_grid.job_id = job_id
    job_grid.job = job
    job_grid.status = status
    return job_grid
