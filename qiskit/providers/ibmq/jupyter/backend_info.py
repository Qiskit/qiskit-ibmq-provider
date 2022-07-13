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

"""Interactive backend widget."""

import threading
from typing import Union

import ipyvuetify as vue
from IPython.display import display  # pylint: disable=import-error
from qiskit.providers.fake_provider.fake_backend import FakeBackend
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from .config_widget import config_tab
from .qubits_widget import qubits_tab
from .gates_widget import gates_tab
from .jobs_widget import jobs_tab
from .live_data_widget import LiveDataVisualization
from ..visualization.interactive import iplot_error_map


def _async_job_loader(tab: vue.TabItem, backend: Union[IBMQBackend, FakeBackend]) -> None:
    """Asynchronous job loader.

    Args:
        tab: Tab item.
        backend: Backend to use.
    """
    tab.children = [jobs_tab(backend)]


def backend_widget(backend: Union[IBMQBackend, FakeBackend]) -> None:
    """Display backend information as a widget.

    Args:
        backend: Display information about this backend.
    """
    vue.theme.dark = False
    cred = backend._credentials
    last_tab = vue.TabItem(children=[])
    livedata = LiveDataVisualization()
    card = vue.Card(height=600, outlined=True,
                    children=[
                        vue.Toolbar(flat=True, color="#002d9c",
                                    children=[
                                        vue.ToolbarTitle(children=['{} @ ({}/{}/{})'.format(
                                            backend.name(),
                                            cred.hub,
                                            cred.group,
                                            cred.project)],
                                                         style_="color:white")]),
                        vue.Tabs(vertical=True,
                                 children=[
                                     vue.Tab(children=['Configuration']),
                                     vue.Tab(children=['Qubits']),
                                     vue.Tab(children=['Non-local Gates']),
                                     vue.Tab(children=['Error map']),
                                     vue.Tab(children=['Live Data']),
                                     vue.Tab(children=['Job Summary']),
                                     vue.TabItem(children=[config_tab(backend)]),
                                     vue.TabItem(children=[qubits_tab(backend)]),
                                     vue.TabItem(children=[gates_tab(backend)]),
                                     vue.TabItem(
                                         children=[
                                             iplot_error_map(
                                                 backend, figsize=(None, None), as_widget=True
                                             )
                                         ]
                                     ),
                                     vue.TabItem(
                                         children=[
                                             livedata.create_visualization(
                                                 backend, figsize=(11, 9), show_title=False
                                             )
                                         ]
                                     ),
                                     last_tab])
                    ])

    # Load job data async for a bit better performance
    thread = threading.Thread(target=_async_job_loader,
                              args=(last_tab, backend))
    thread.start()

    display(card)
