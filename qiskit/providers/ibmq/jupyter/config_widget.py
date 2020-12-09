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
# pylint: disable=protected-access

"""Widget for the backend configuration tab."""

from typing import Union

import ipywidgets as wid
from qiskit.test.mock.fake_backend import FakeBackend
from qiskit.providers.ibmq.visualization.interactive import iplot_gate_map
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.utils.converters import duration_difference

from .utils import get_next_reservation


def config_tab(backend: Union[IBMQBackend, FakeBackend]) -> wid.GridBox:
    """The backend configuration widget.

    Args:
        backend: Display configuration widget for this backend.

    Returns:
        A widget containing backend configuration information.
    """
    status = backend.status().to_dict()
    config = backend.configuration().to_dict()
    next_resrv = get_next_reservation(backend)
    if next_resrv:
        reservation_str = "in {} ({}m)".format(duration_difference(next_resrv.start_datetime),
                                               next_resrv.duration)
    else:
        reservation_str = '-'

    config_dict = {**status, **config}
    config_dict['reservation'] = reservation_str

    upper_list = ['n_qubits']

    if 'quantum_volume' in config.keys():
        if config['quantum_volume']:
            upper_list.append('quantum_volume')

    upper_list.extend(['operational',
                       'status_msg', 'pending_jobs', 'reservation',
                       'backend_version', 'basis_gates',
                       'max_shots', 'max_experiments'])

    lower_list = list(set(config_dict.keys()).difference(upper_list))
    # Remove gates because they are in a different tab
    lower_list.remove('gates')
    # Look for hamiltonian
    if 'hamiltonian' in lower_list:
        htex = config_dict['hamiltonian']['h_latex']
        config_dict['hamiltonian'] = "$$%s$$" % htex

    upper_str = "<table>"
    upper_str += """<style>
table {
    border-collapse: collapse;
    width: auto;
    font-family:IBM Plex Sans, Arial, sans-serif !important;
}

th, td {
    text-align: left;
    padding: 8px;
}

tr:nth-child(even) {background-color: #f6f6f6;}
</style>"""

    footer = "</table>"

    # Upper HBox widget data

    upper_str += "<tr><th>Property</th><th>Value</th></tr>"
    for key in upper_list:
        upper_str += "<tr><td><font style='font-weight:bold'>%s</font></td><td>%s</td></tr>" % (
            key, config_dict[key])
    upper_str += footer

    upper_table = wid.HTMLMath(
        value=upper_str, layout=wid.Layout(width='100%', grid_area='left'))

    img_child = []
    if not config['simulator']:
        img_child = [iplot_gate_map(backend, as_widget=True)]

    image_widget = wid.HBox(children=img_child,
                            layout=wid.Layout(grid_area='right',
                                              max_height='350px',
                                              margin='0px 0px 0px 0px',
                                              display='flex-inline',
                                              align_items='center',
                                              justify_content='center',
                                              width='auto'))

    lower_str = "<table>"
    lower_str += """<style>
table {
    border-collapse: collapse;
    width: auto;
}

th, td {
    text-align: left;
    padding: 8px !important;
}

tr:nth-child(even) {background-color: #f6f6f6;}
</style>"""
    lower_str += "<tr><th></th><th></th></tr>"
    for key in lower_list:
        if key != 'name':
            lower_str += "<tr><td>%s</td><td>%s</td></tr>" % (
                key, config_dict[key])
    lower_str += footer

    lower_table = wid.HTMLMath(value=lower_str,
                               layout=wid.Layout(width='auto',
                                                 grid_area='bottom'))

    grid = wid.GridBox(children=[upper_table, image_widget, lower_table],
                       layout=wid.Layout(max_height='500px',
                                         margin='10px',
                                         overflow='hidden scroll',
                                         grid_template_rows='auto auto',
                                         grid_template_columns='33% 21% 21% 21%',
                                         grid_template_areas='''
                                         "left right right right"
                                         "bottom bottom bottom bottom"
                                         ''',
                                         grid_gap='0px 0px'))

    return grid
