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

"""An interactive backend error map.
"""
import numpy as np
import seaborn as sns

HELIX_LIGHT_CMAP = sns.cubehelix_palette(start=2.5,
                                         rot=0.4,
                                         hue=2,
                                         gamma=1,
                                         light=0.9,
                                         dark=0.15,
                                         reverse=True,
                                         as_cmap=True)

HELIX_DARK_CMAP = sns.cubehelix_palette(start=2.5,
                                        rot=0.4,
                                        hue=2,
                                        gamma=0.95,
                                        light=0.95,
                                        dark=0.25,
                                        reverse=True,
                                        as_cmap=True)


def _sns_to_plotly(cmap, pl_entries=255):
    hgt = 1.0/(pl_entries-1)
    pl_colorscale = []

    for k in range(pl_entries):
        clr = list(map(np.uint8, np.array(cmap(k*hgt)[:3])*255))
        pl_colorscale.append([k*hgt, 'rgb'+str((clr[0], clr[1], clr[2]))])

    return pl_colorscale


HELIX_LIGHT = _sns_to_plotly(HELIX_LIGHT_CMAP)
HELIX_DARK = _sns_to_plotly(HELIX_DARK_CMAP)
