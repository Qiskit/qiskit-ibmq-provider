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
# pylint: disable=invalid-name

"""Widget for backend gates tab."""

import math
from typing import Union

import ipywidgets as wid
from qiskit.test.mock.fake_backend import FakeBackend
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend


def gates_tab(backend: Union[IBMQBackend, FakeBackend]) -> wid.GridBox:
    """Construct the multiple qubit gate error widget.

    Args:
        backend: The backend to display.

    Returns:
        A widget with gate information.
    """
    props = backend.properties().to_dict()
    update_date = props['last_update_date']
    date_str = update_date.strftime("%a %d %B %Y at %H:%M %Z")

    multi_qubit_gates = [g for g in props['gates'] if len(g['qubits']) > 1]

    header_html = "<div><font style='font-weight:bold'>{key}</font>: {value}</div>"
    header_html = header_html.format(key='last_update_date',
                                     value=date_str)

    update_date_widget = wid.HTML(value=header_html,
                                  layout=wid.Layout(grid_area='top'))

    gate_html = "<table>"
    gate_html += """<style>
table {
    border-collapse: collapse;
    font-family:IBM Plex Sans, Arial, sans-serif !important;

}

th, td {
    text-align: left;
    padding: 8px !important;
}

tr:nth-child(even) {background-color: #f6f6f6;};
</style>"""

    gate_html += "<tr><th></th><th>Type</th><th>Gate error</th></tr>"
    gate_footer = "</table>"

    # Split gates into two columns
    left_num = math.ceil(len(multi_qubit_gates)/3)
    mid_num = math.ceil((len(multi_qubit_gates)-left_num)/2)

    left_table = gate_html

    for qub in range(left_num):
        gate = multi_qubit_gates[qub]
        qubits = gate['qubits']
        ttype = gate['gate']
        error = round(gate['parameters'][0]['value']*100, 3)

        left_table += "<tr><td><font style='font-weight:bold'>%s</font>"
        left_table += "</td><td>%s</td><td>%s</td></tr>"
        left_table = left_table % ("{}{}_{}".format(ttype, qubits[0], qubits[1]),
                                   ttype, error)
    left_table += gate_footer

    middle_table = gate_html

    for qub in range(left_num, left_num+mid_num):
        gate = multi_qubit_gates[qub]
        qubits = gate['qubits']
        ttype = gate['gate']
        error = round(gate['parameters'][0]['value']*100, 3)

        middle_table += "<tr><td><font style='font-weight:bold'>%s</font>"
        middle_table += "</td><td>%s</td><td>%s</td></tr>"
        middle_table = middle_table % ("{}{}_{}".format(ttype, qubits[0], qubits[1]),
                                       ttype, error)
    middle_table += gate_footer

    right_table = gate_html

    for qub in range(left_num+mid_num, len(multi_qubit_gates)):
        gate = multi_qubit_gates[qub]
        qubits = gate['qubits']
        ttype = gate['gate']
        error = round(gate['parameters'][0]['value']*100, 3)

        right_table += "<tr><td><font style='font-weight:bold'>%s</font>"
        right_table += "</td><td>%s</td><td>%s</td></tr>"
        right_table = right_table % ("{}{}_{}".format(ttype, qubits[0], qubits[1]),
                                     ttype, error)
    right_table += gate_footer

    left_table_widget = wid.HTML(value=left_table,
                                 layout=wid.Layout(grid_area='left'))
    middle_table_widget = wid.HTML(value=middle_table,
                                   layout=wid.Layout(grid_area='middle'))
    right_table_widget = wid.HTML(value=right_table,
                                  layout=wid.Layout(grid_area='right'))

    grid = wid.GridBox(children=[update_date_widget, left_table_widget,
                                 middle_table_widget, right_table_widget],
                       layout=wid.Layout(width='100%',
                                         max_height='500px',
                                         margin='10px',
                                         overflow='hidden scroll',
                                         grid_template_rows='auto auto',
                                         grid_template_columns='33% 33% 33%',
                                         grid_template_areas='''
                                                             "top top top"
                                                             "left middle right"
                                                             ''',
                                         grid_gap='0px 0px'))

    return grid
