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

"""Module that defines constants used by the dashboard."""

STAT_FONT_VALUE = "<font size='4' face='monospace'>{}</font>"
"""Font used for backend stat values."""
STAT_FONT_VALUE_COLOR = "<font size='4' style='color:{color}' face='monospace'>{msg}</font>"
"""Font used for backend stat values with color."""
STAT_FONT_TITLE = "<font size='3'>{}</font>"
"""Font used for backend stat titles."""

RESERVATION_STR = STAT_FONT_VALUE.format("in {start_dt} ({duration}m)")
"""String used to format reservation information. ``start_dt`` is time until
reservation starts. ``duration`` is reservation duration."""
RESERVATION_NONE = STAT_FONT_VALUE.format('-')
"""String used when there is no reservation."""

EXP_JOB_STATUS_LIST = ['DONE', 'ERROR', 'CANCELLED']
""" Expired jobs status list """
EXP_JOB_STATUS_COLORS_LIST = ['#34BC6E', '#DC267F', '#FFB000']
""" Colors associated with expired job statuses """

LIST_STYLE_WIDGET = """
<style>
    .row_item {
        display: flex;
        z-index: 999;
        box-shadow: 5px 5px 5px -3px black;
        opacity: 0.95;
        float: left;
        letter-spacing: 1px;
        padding: 3px;
    }

    .row_item p {
        padding: 2px 0px 2px 7px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

</style>"""
"""tabular list styling for the dashboard"""
LIST_COL_DIV = "<div style='background-color: lightgrey; width: 2px'></div>"
""" separator element (div) in a dashboard table row """
DASH_JOB_HTML = """<div class='rt_program_entry'>
        <p style='width: 190px; color: {4};'>{0}</p>{div}
        <p style='width: 165px; color: {5};'>{1}</p>{div}
        <p style='width: 125px; color: {6};'>{2}</p>{div}
        <p style='width: 125px; color: {7};'>{3}</p>
    </div>"""
