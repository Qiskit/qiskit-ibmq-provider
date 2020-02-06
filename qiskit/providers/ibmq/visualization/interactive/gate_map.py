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

"""Interactive gate map"""

import plotly.graph_objects as go
from .plotly_wrapper import PlotlyWidget, PlotlyFigure
from ..device_layouts import DEVICE_LAYOUTS


def iplot_gate_map(backend, figsize=(None, None), label_qubits=True,
                   qubit_size=None, line_width=None, font_size=None,
                   qubit_color="#2f4b7c", qubit_labels=None,
                   line_color="#2f4b7c", font_color="white",
                   background_color='white',
                   as_widget=False):
    """Plots an interactive gate map of a device.

    Args:
        backend (BaseBackend): A backend instance,
        figsize (tuple): Output figure size (wxh) in inches.
        label_qubits (bool): Label the qubits.
        qubit_size (float): Size of qubit marker.
        line_width (float): Width of lines.
        font_size (int): Font size of qubit labels.
        qubit_color (list): A list of colors for the qubits
        qubit_labels (list): A list of qubit labels
        line_color (list): A list of colors for each line from coupling_map.
        font_color (str): The font color for the qubit labels.
        background_color (str): The background color, 'white' or 'black'.
        as_widget (bool): Display figure as ipywidget.

    Returns:
        PlotlyFigure or PlotlyWidget: The output figure.

    Example:
        .. jupyter-execute::

           from qiskit import IBMQ
           from qiskit.providers.ibmq.visualization import iplot_gate_map

           IBMQ.load_account()

           provider = IBMQ.get_provider(group='open', project='main')
           backend = provider.get_backend('ibmq_vigo')

           iplot_gate_map(backend, as_widget=True)
    """

    config = backend.configuration()
    n_qubits = config.n_qubits
    cmap = config.coupling_map

    # set coloring
    if isinstance(qubit_color, str):
        qubit_color = [qubit_color] * n_qubits
    if isinstance(line_color, str):
        line_color = [line_color] * len(cmap) if cmap else []

    if n_qubits in DEVICE_LAYOUTS.keys():
        grid_data = DEVICE_LAYOUTS[n_qubits]
    else:
        fig = go.Figure()
        fig.update_layout(showlegend=False,
                          plot_bgcolor=background_color,
                          paper_bgcolor=background_color,
                          width=figsize[0], height=figsize[1],
                          margin=dict(t=30, l=0, r=0, b=0))

        if as_widget:
            return PlotlyWidget(fig)
        return PlotlyFigure(fig)

    x_max = max([d[1] for d in grid_data])
    y_max = max([d[0] for d in grid_data])
    max_dim = max(x_max, y_max)

    offset = 0
    if cmap:
        if y_max / max_dim < 0.33:
            offset = 1
            if qubit_size is None:
                qubit_size = 24
            if font_size is None:
                font_size = 10
            if line_width is None:
                line_width = 4
            if figsize == (None, None):
                figsize = (400, 200)
        else:
            if qubit_size is None:
                qubit_size = 32
            if font_size is None:
                font_size = 14
            if line_width is None:
                line_width = 6
            if figsize == (None, None):
                figsize = (300, 300)
    else:
        if figsize == (None, None):
            figsize = (300, 300)
        if qubit_size is None:
            qubit_size = 30

    fig = go.Figure()

    # Add lines for couplings
    if cmap:
        for ind, edge in enumerate(cmap):
            is_symmetric = False
            if edge[::-1] in cmap:
                is_symmetric = True
            y_start = grid_data[edge[0]][0] + offset
            x_start = grid_data[edge[0]][1]
            y_end = grid_data[edge[1]][0] + offset
            x_end = grid_data[edge[1]][1]

            if is_symmetric:
                if y_start == y_end:
                    x_end = (x_end - x_start) / 2 + x_start
                    x_mid = x_end
                    y_mid = y_start

                elif x_start == x_end:
                    y_end = (y_end - y_start) / 2 + y_start
                    x_mid = x_start
                    y_mid = y_end

                else:
                    x_end = (x_end - x_start) / 2 + x_start
                    y_end = (y_end - y_start) / 2 + y_start
                    x_mid = x_end
                    y_mid = y_end
            else:
                if y_start == y_end:
                    x_mid = (x_end - x_start) / 2 + x_start
                    y_mid = y_end

                elif x_start == x_end:
                    x_mid = x_end
                    y_mid = (y_end - y_start) / 2 + y_start

                else:
                    x_mid = (x_end - x_start) / 2 + x_start
                    y_mid = (y_end - y_start) / 2 + y_start

            fig.add_trace(
                go.Scatter(x=[x_start, x_mid, x_end],
                           y=[-y_start, -y_mid, -y_end],
                           mode="lines",
                           hoverinfo='none',
                           line=dict(width=line_width,
                                     color=line_color[ind])))

    # Add the qubits themselves
    if qubit_labels is None:
        qubit_text = []
        qubit_str = "<b>Qubit {}"
        for num in range(n_qubits):
            qubit_text.append(qubit_str.format(num))

    if n_qubits > 50:
        if qubit_size is None:
            qubit_size = 20
        if font_size is None:
            font_size = 9

    fig.add_trace(go.Scatter(
        x=[d[1] for d in grid_data],
        y=[-d[0]-offset for d in grid_data],
        mode="markers+text",
        marker=go.scatter.Marker(size=qubit_size,
                                 color=qubit_color,
                                 opacity=1),
        text=[str(ii) for ii in range(n_qubits)] if label_qubits else None,
        textposition="middle center",
        textfont=dict(size=font_size, color=font_color),
        hoverinfo="text" if label_qubits else 'none',
        hovertext=qubit_text))

    fig.update_xaxes(visible=False)
    _range = None
    if offset:
        _range = [-3.5, 0.5]
    fig.update_yaxes(visible=False, range=_range)

    fig.update_layout(showlegend=False,
                      plot_bgcolor=background_color,
                      paper_bgcolor=background_color,
                      width=figsize[0], height=figsize[1],
                      margin=dict(t=30, l=0, r=0, b=0))

    if as_widget:
        return PlotlyWidget(fig)
    return PlotlyFigure(fig)
