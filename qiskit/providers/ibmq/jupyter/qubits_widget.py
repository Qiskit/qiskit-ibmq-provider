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
# pylint: disable=invalid-name

"""Widget for qubit properties tab."""

from typing import Union

import ipywidgets as wid
from qiskit.test.mock.fake_backend import FakeBackend
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend


def qubits_tab(backend: Union[IBMQBackend, FakeBackend]) -> wid.VBox:
    """The qubit properties widget.

    Args:
        backend: Display qubit properties for this backend.

    Returns:
        A widget containing qubit information.
    """
    props = backend.properties()
    update_date = props.last_update_date
    date_str = update_date.strftime("%a %d %B %Y at %H:%M %Z")
    header_html = "<div><font style='font-weight:bold'>{key}</font>: {value}</div>"
    header_html = header_html.format(key='last_update_date',
                                     value=date_str)
    update_date_widget = wid.HTML(value=header_html)

    qubit_html = "<table>"
    qubit_html += """<style>
table {
    width: auto !important;
    font-family:IBM Plex Sans, Arial, sans-serif !important;
}

th, td {
    text-align: left !important;
    padding: 8px !important;
}

tr:nth-child(even) {background-color: #f6f6f6 !important;}
</style>"""

    qubit_html += "<tr><th></th><th>Frequency</th><th>T1</th><th>T2</th>"
    qubit_footer = "</table>"

    gate_error_title = ""

    for index, qubit_data in enumerate(props.qubits):
        name = 'Q%s' % index
        gate_data = [gate for gate in props.gates if gate.qubits == [index]]

        cali_data = dict.fromkeys(['T1', 'T2', 'frequency', 'readout_error'], 'Unknown')
        for nduv in qubit_data:
            if nduv.name == 'readout_error':
                cali_data[nduv.name] = str(round(nduv.value*100, 3))
            elif nduv.name in cali_data.keys():
                cali_data[nduv.name] = str(round(nduv.value, 3)) + ' ' + nduv.unit

        gate_names = []
        gate_error = []
        for gd in gate_data:
            if gd.gate in ['rz', 'id']:
                continue
            for gd_param in gd.parameters:
                if gd_param.name == 'gate_error':
                    gate_names.append(gd.gate.upper())
                    gate_error.append(str(round(gd_param.value*100, 3)))

        if not gate_error_title:
            for gname in gate_names:
                gate_error_title += f"<th>{gname}</th>"
            qubit_html += gate_error_title + "<th>Readout error</th></tr>"

        qubit_html += f"<tr><td><font style='font-weight:bold'>{name}</font></td>"
        qubit_html += f"<td>{cali_data['frequency']}</td>" \
                      f"<td>{cali_data['T1']}</td><td>{cali_data['T2']}</td>"
        for gerror in gate_error:
            qubit_html += f"<td>{gerror}</td>"
        qubit_html += f"<td>{cali_data['readout_error']}</td>"

    qubit_html += qubit_footer

    qubit_widget = wid.HTML(value=qubit_html, layout=wid.Layout(width='100%'))

    out = wid.VBox(children=[update_date_widget, qubit_widget],
                   layout=wid.Layout(max_height='500px',
                                     margin='10px',
                                     overflow='hidden scroll',))

    return out
