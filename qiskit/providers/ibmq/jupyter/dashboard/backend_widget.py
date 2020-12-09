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

"""Module for constructing backend widgets."""

import ipywidgets as wid

from qiskit.providers.ibmq.utils.converters import duration_difference

from ...visualization.interactive import iplot_gate_map
from .provider_buttons import provider_buttons
from .utils import BackendWithProviders
from .constants import (RESERVATION_STR, RESERVATION_NONE, STAT_FONT_TITLE,
                        STAT_FONT_VALUE, STAT_FONT_VALUE_COLOR)
from ..utils import get_next_reservation


def make_backend_widget(backend_item: BackendWithProviders) -> wid.HBox:
    """ Construct a backend widget for a given device.

    Args:
        backend_item: A ``BackendWithProviders`` instance containing the
            backend instance and a list of providers from which the backend can be accessed.

    Returns:
        The widget with backend information.
    """
    backend = backend_item.backend
    backend_providers = backend_item.providers

    status = backend.status()
    config = backend.configuration()
    props = backend.properties().to_dict()
    next_resrv = get_next_reservation(backend)

    name_str = "<font size='5' face='monospace'>%s</font>"
    backend_name = wid.HTML(value=name_str % backend.name())

    qubits_wid = wid.HTML(value=STAT_FONT_TITLE.format("Qubits:"))
    qubits_val_wid = wid.HTML(value=STAT_FONT_VALUE.format(config.n_qubits))

    status_wid = wid.HTML(value=STAT_FONT_TITLE.format("Status:"))

    color = '#000000'
    status_msg = status.status_msg
    if status_msg == 'active':
        color = '#34BC6E'
        if next_resrv:
            status_msg += ' [R]'
    if status_msg in ['maintenance', 'internal']:
        color = '#FFB000'

    status_val_wid = wid.HTML(value=STAT_FONT_VALUE_COLOR.format(color=color, msg=status_msg))

    left_labels = wid.VBox(children=[qubits_wid, status_wid])
    left_values = wid.VBox(children=[qubits_val_wid, status_val_wid],
                           layout=wid.Layout(margin="1px 0px 0px 0px"))

    left_stats = wid.HBox(children=[left_labels, left_values],
                          layout=wid.Layout(width='175px')
                          )

    version_wid = wid.HTML(value=STAT_FONT_TITLE.format("Version:"))
    version_val_wid = wid.HTML(value=STAT_FONT_VALUE.format(config.backend_version),
                               layout=wid.Layout(margin="3px 0px 0px 0px"))

    queue_wid = wid.HTML(value=STAT_FONT_TITLE.format("Queue:"))
    queue_val_wid = wid.HTML(value=STAT_FONT_VALUE.format(status.pending_jobs),
                             layout=wid.Layout(margin="5px 0px 0px 0px"))

    right_labels = wid.VBox(children=[version_wid, queue_wid])
    right_values = wid.VBox(children=[version_val_wid, queue_val_wid])

    right_stats = wid.HBox(children=[right_labels, right_values],
                           layout=wid.Layout(width='auto',
                                             margin="0px 0px 0px 20px"))

    stats = wid.HBox(children=[left_stats, right_stats])

    # Backend reservation.
    reservation_title = wid.HTML(value=STAT_FONT_TITLE.format("Reservation:"))
    if next_resrv:
        start_dt_str = duration_difference(next_resrv.start_datetime)
        reservation_val = RESERVATION_STR.format(
            start_dt=start_dt_str, duration=next_resrv.duration)
    else:
        reservation_val = RESERVATION_NONE
    reservation_val_wid = wid.HTML(value=reservation_val)
    reservation_wid = wid.HBox(children=[reservation_title, reservation_val_wid])

    providers_label = wid.HTML(value=STAT_FONT_TITLE.format("Providers:"))

    providers_list = provider_buttons(backend_providers)

    device_stats = wid.VBox(children=[backend_name, stats, reservation_wid,
                                      providers_label, providers_list],
                            layout=wid.Layout(width='auto',
                                              margin="0px 20px 0px 0px"))

    n_qubits = config.n_qubits

    qubit_size = 15
    line_width = 3
    if n_qubits < 10:
        qubit_size = 18
        line_width = 4
    if n_qubits >= 27:
        qubit_size = 12
        line_width = 3
    if n_qubits > 50:
        qubit_size = 12
        line_width = 3

    _gmap = iplot_gate_map(backend, figsize=(150, 150),
                           qubit_size=qubit_size,
                           line_width=line_width,
                           qubit_color='#031981',
                           line_color='#031981',
                           label_qubits=False,
                           as_widget=True)

    gmap = wid.Box(children=[_gmap],
                   layout=wid.Layout(width='auto',
                                     justify_content='center',
                                     align_content='center',
                                     ))

    # Get basic device stats
    t1_units = props['qubits'][0][0]['unit']
    avg_t1 = round(sum([q[0]['value'] for q in props['qubits']])/n_qubits, 1)
    avg_t2 = round(sum([q[1]['value'] for q in props['qubits']])/n_qubits, 1)

    if n_qubits != 1:
        sum_cx_err = 0
        num_cx = 0
        for gate in props['gates']:
            if gate['gate'] == 'cx':
                for param in gate['parameters']:
                    if param['name'] == 'gate_error':
                        # Value == 1.0 means gate effectively off
                        if param['value'] != 1.0:
                            sum_cx_err += param['value']
                            num_cx += 1
        if num_cx:
            avg_cx_err = round(sum_cx_err/(num_cx)*100, 2)
        else:
            avg_cx_err = 100.0

    avg_meas_err = 0
    for qub in props['qubits']:
        for item in qub:
            if item['name'] == 'readout_error':
                avg_meas_err += item['value']
    avg_meas_err = round(avg_meas_err/n_qubits*100, 2)

    t12_label = wid.HTML(value="<font size='2'>Avg. T<sub>1</sub> / T<sub>2</sub></font>:")
    t12_str = "<font size='3' face='monospace'>{t1}/{t2}</font><font size='2'> {units}</font>"
    t12_wid = wid.HTML(value=t12_str.format(t1=avg_t1, t2=avg_t2, units=t1_units))

    meas_label = wid.HTML(value="<font size='2'>Avg. Readout Err.:</font>")
    meas_str = "<font size='3' face='monospace'>{merr}</font><font size='2'> %</font>"
    meas_wid = wid.HTML(value=meas_str.format(merr=avg_meas_err))

    cx_str = "<font size='3' face='monospace'>{cx_err}</font><font size='2'> %</font>"
    if n_qubits != 1:
        cx_label = wid.HTML(value="<font size='2'>Avg. CX Err.:</font>")
        cx_wid = wid.HTML(value=cx_str.format(cx_err=avg_cx_err))

    quant_vol = 'None'
    try:
        quant_vol = config.quantum_volume
    except AttributeError:
        pass
    qv_label = wid.HTML(value="<font size='2'>Quantum Volume:</font>")
    qv_str = "<font size='3' face='monospace'>{qv}</font><font size='2'></font>"
    qv_wid = wid.HTML(value=qv_str.format(qv=quant_vol),
                      layout=wid.Layout(margin="-1px 0px 0px 0px"))

    if n_qubits != 1:
        left_wids = [t12_label, cx_label, meas_label, qv_label]
        right_wids = [t12_wid, cx_wid, meas_wid, qv_wid]

    else:
        left_wids = [t12_label, meas_label, qv_label]
        right_wids = [t12_wid, meas_wid, qv_wid]

    left_wid = wid.VBox(children=left_wids,
                        layout=wid.Layout(margin="2px 0px 0px 0px"))
    right_wid = wid.VBox(children=right_wids,
                         layout=wid.Layout(margin="0px 0px 0px 3px"))

    stats = wid.HBox(children=[left_wid, right_wid])

    gate_map = wid.VBox(children=[gmap, stats],
                        layout=wid.Layout(width='230px',
                                          justify_content='center',
                                          align_content='center',
                                          margin="-25px 0px 0px 0px"))

    out = wid.HBox(children=[device_stats, gate_map],
                   layout=wid.Layout(width='auto',
                                     height='auto',
                                     padding="5px 5px 5px 5px",
                                     justify_content='space-between',
                                     max_width='700px',
                                     border='1px solid #212121'))

    # Attach information to the backend panel for later updates.
    out._backend = backend  # pylint: disable=protected-access
    out._status_val_wid = status_val_wid
    out._queue_val_wid = queue_val_wid
    out._reservation_val_wid = reservation_val_wid
    return out
