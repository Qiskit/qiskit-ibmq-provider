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

"""Experiment constants."""

import enum


class ResultQuality(enum.Enum):
    """Possible values for analysis result quality."""

    HUMAN_BAD = 'Human Bad'
    COMPUTER_BAD = 'Computer Bad'
    NO_INFORMATION = 'No Information'
    COMPUTER_GOOD = 'Computer Good'
    HUMAN_GOOD = 'Human Good'
