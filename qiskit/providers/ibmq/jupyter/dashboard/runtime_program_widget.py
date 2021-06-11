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

"""A module of widgets for runtime programs."""


import ipywidgets as widgets

# from qiskit.providers.ibmq.job.ibmqjob import IBMQJob
from qiskit.providers.ibmq.runtime import RuntimeProgram


def make_labels() -> widgets.HBox:
    """Makes the labels widget.

    Returns:
        The labels widget.
    """
    labels0 = widgets.HTML(value="<h5>Name</h5>",
                           layout=widgets.Layout(width='190px'))
    labels1 = widgets.HTML(value='<h5>Description</h5>',
                           layout=widgets.Layout(width='250px'))
    labels = widgets.HBox(children=[labels0, labels1],
                          layout=widgets.Layout(width='700px',
                                                margin='0px 0px 0px 35px'))
    return labels


def create_program_widget(program: RuntimeProgram) -> widgets.HBox:
    """Create a widget corresponding to a particular job instance.

    Args:
        program: the program

    Returns:
        The program widget.
    """

    div = "<div style='background-color: lightgrey; width: 2px'></div>"
    labels_str = """<div class='rt_program_entry'>
        <p style='width: 170px;'>{}</p>{}
        <p style='width: 475px;'>{}</p>
    </div>""".format(
        program.program_id,
        div,
        program.description
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

    grid = widgets.HBox(children=[labels, styles],
                        layout=widgets.Layout(min_width='690px',
                                              max_width='690px'))
    grid.program = program

    return grid
