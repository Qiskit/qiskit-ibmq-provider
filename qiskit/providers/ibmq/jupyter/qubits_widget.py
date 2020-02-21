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

"""Widget for qubit properties tab."""

from typing import Union

import ipywidgets as wid
from qiskit.test.mock.fake_backend import FakeBackend
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend

from ..utils.converters import utc_to_local


def qubits_tab(backend: Union[IBMQBackend, FakeBackend]) -> wid.VBox:
    """The qubit properties widget.

    Args:
        backend: Display qubit properties for this backend.

    Returns:
        A widget containing qubit information.
    """
    props = backend.properties().to_dict()

    update_date = utc_to_local(props['last_update_date'])
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
    qubit_html += "<th>U1 error</th><th>U2 error</th><th>U3 error</th>"
    qubit_html += "<th>Readout error</th></tr>"
    qubit_footer = "</table>"

    for qub in range(len(props['qubits'])):
        name = 'Q%s' % qub
        qubit_data = props['qubits'][qub]
        gate_data = [g for g in props['gates'] if g['qubits'] == [qub]]
        t1_info = qubit_data[0]
        t2_info = qubit_data[1]
        freq_info = qubit_data[2]
        readout_info = qubit_data[3]

        freq = str(round(freq_info['value'], 3))+' '+freq_info['unit']
        T1 = str(round(t1_info['value'],
                       3))+' ' + t1_info['unit']
        T2 = str(round(t2_info['value'],
                       3))+' ' + t2_info['unit']

        for gd in gate_data:
            if gd['gate'] == 'u1':
                U1 = str(round(gd['parameters'][0]['value']*100, 3))
                break

        for gd in gate_data:
            if gd['gate'] == 'u2':
                U2 = str(round(gd['parameters'][0]['value']*100, 3))
                break
        for gd in gate_data:
            if gd['gate'] == 'u3':
                U3 = str(round(gd['parameters'][0]['value']*100, 3))
                break

        readout_error = round(readout_info['value']*100, 3)
        qubit_html += "<tr><td><font style='font-weight:bold'>%s</font></td><td>%s</td>"
        qubit_html += "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        qubit_html = qubit_html % (name, freq, T1, T2, U1, U2, U3, readout_error)
    qubit_html += qubit_footer

    qubit_widget = wid.HTML(value=qubit_html, layout=wid.Layout(width='100%'))

    out = wid.VBox(children=[update_date_widget, qubit_widget],
                   layout=wid.Layout(max_height='500px',
                                     margin='10px',
                                     overflow='hidden scroll',))

    return out
