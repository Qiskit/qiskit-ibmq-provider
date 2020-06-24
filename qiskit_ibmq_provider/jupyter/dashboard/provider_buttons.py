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

"""Module for creating provider buttons in the dashboard."""

import time
import threading
from typing import List, Any

import ipyvuetify as vue
import ipywidgets as wid
import pyperclip


def _copy_text_thread(button: vue.Btn) -> None:
    """A function that signals button text was copied to clipboard.

    Args:
        button: Button whose text is to be copied.
    """
    old_text = button.children[0]
    hub, group, project = old_text.split('/')
    pyperclip.copy("IBMQ.get_provider(hub='{hub}', group='{group}', project='{project}')"
                   .format(hub=hub, group=group, project=project))
    button.children = ['Copied to clipboard.']
    time.sleep(1)
    button.children = [old_text]


def _copy_text(*args: Any) -> None:
    """Copy the text on the input button."""
    thread = threading.Thread(target=_copy_text_thread, args=(args[0],))
    thread.start()


def provider_buttons(providers: List[str]) -> wid.VBox:
    """Generate a collection of provider buttons for a backend.

    When one of these buttons is clicked, the code to get the particular
    provider is copied to the clipboard.

    Args:
        providers: A list of provider names.

    Returns:
        A widget with provider buttons.
    """
    vbox_buttons = []
    for pro in providers:
        button = wid.Box(children=[vue.Btn(color='#f5f5f5', small=True,
                                           children=[pro],
                                           style_="font-family: Arial,"
                                                  "sans-serif; font-size:10px;")],
                         layout=wid.Layout(margin="0px 0px 2px 0px",
                                           width='350px'))

        button.children[0].on_event('click', _copy_text)
        vbox_buttons.append(button)

    return wid.VBox(children=vbox_buttons,
                    layout=wid.Layout(width='350px',
                                      max_width='350px'))
