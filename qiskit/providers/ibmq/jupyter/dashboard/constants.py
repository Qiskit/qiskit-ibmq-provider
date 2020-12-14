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
