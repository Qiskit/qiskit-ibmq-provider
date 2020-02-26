# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""An exception notifications module"""
import traceback
import sys
from io import StringIO
import ipyvuetify as vue
from IPython.display import display


class SilentExit(SystemExit):
    """A silent exception for Jupyter notebooks
    """
    def __init__(self):  #pylint: disable=super-init-not-called
        sys.stderr = StringIO()
        self.__class__.__name__ = ''

    def __del__(self):
        sys.stderr.flush()
        sys.stderr = sys.__stderr__


def exception_widget(exc: Exception) -> None:
    """Create an exception notification widget.

    Raises sys.exit() silently.

    Parameters:
        exc: Input exception.

    Raises:
        SilentExit: Exits silently.
    """
    tback = traceback.TracebackException.from_exception(exc).format()
    trace_list = [string for string in tback if 'File' in string]
    if any(trace_list):
        tback = trace_list[-1].split('\n')[0]
    else:
        tback = ''
    exc_type = exc.__class__.__name__
    exc_msg = exc.args[0]

    title = vue.CardTitle(class_='headline body-1 font-weight-medium',
                          primary_title=True,
                          children=[vue.Icon(children=['warning'],
                                             style_='color:#ffffff;'
                                                    'margin: 0px 5px'
                                            ),
                                    exc_type],
                          style_='height:35px;'
                                 'background-color:#AA0114;'
                                 'color:#ffffff;'
                                 'padding: 0px 10px'
                         )
    subtitle = vue.CardSubtitle(children=[exc_msg],
                                class_='text--primary body-1 fontweight-medium',
                                style_="margin: 0px 0px; color:#212121"
                               )
    children = [title, subtitle]

    if tback:
        text = vue.CardText(children=[tback],
                            class_='font-weight-medium',
                            style_="margin: -15px 0px"
                           )
        children.append(text)

    exc_card = vue.Card(children=children,
                        style_='height: auto; min-height: 100px;',
                        )
    display(exc_card)
    raise SilentExit
