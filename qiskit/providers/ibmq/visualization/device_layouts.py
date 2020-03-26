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

"""Device layout information."""

DEVICE_LAYOUTS = {}

DEVICE_LAYOUTS[1] = [[0, 0]]

DEVICE_LAYOUTS[5] = [[1, 0], [0, 1], [1, 1], [1, 2], [2, 1]]

DEVICE_LAYOUTS[15] = [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4],
                      [0, 5], [0, 6], [1, 7], [1, 6], [1, 5],
                      [1, 4], [1, 3], [1, 2], [1, 1], [1, 0]]

DEVICE_LAYOUTS[16] = [[1, 0], [0, 0], [0, 1], [0, 2], [0, 3],
                      [0, 4], [0, 5], [0, 6], [0, 7], [1, 7],
                      [1, 6], [1, 5], [1, 4], [1, 3], [1, 2], [1, 1]]

DEVICE_LAYOUTS[20] = [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4],
                      [1, 0], [1, 1], [1, 2], [1, 3], [1, 4],
                      [2, 0], [2, 1], [2, 2], [2, 3], [2, 4],
                      [3, 0], [3, 1], [3, 2], [3, 3], [3, 4]]

DEVICE_LAYOUTS[27] = [[1, 0], [1, 1], [2, 1], [3, 1], [1, 2],
                      [3, 2], [0, 3], [1, 3], [3, 3], [4, 3],
                      [1, 4], [3, 4], [1, 5], [2, 5], [3, 5],
                      [1, 6], [3, 6], [0, 7], [1, 7], [3, 7],
                      [4, 7], [1, 8], [3, 8], [1, 9], [2, 9],
                      [3, 9], [3, 10]]

DEVICE_LAYOUTS[28] = [[0, 2], [0, 3], [0, 4], [0, 5], [0, 6],
                      [1, 2], [1, 6],
                      [2, 0], [2, 1], [2, 2], [2, 3], [2, 4],
                      [2, 5], [2, 6], [2, 7], [2, 8],
                      [3, 0], [3, 4], [3, 8],
                      [4, 0], [4, 1], [4, 2], [4, 3], [4, 4],
                      [4, 5], [4, 6], [4, 7], [4, 8]]

DEVICE_LAYOUTS[53] = [[0, 2], [0, 3], [0, 4], [0, 5], [0, 6],
                      [1, 2], [1, 6],
                      [2, 0], [2, 1], [2, 2], [2, 3], [2, 4],
                      [2, 5], [2, 6], [2, 7], [2, 8],
                      [3, 0], [3, 4], [3, 8],
                      [4, 0], [4, 1], [4, 2], [4, 3], [4, 4],
                      [4, 5], [4, 6], [4, 7], [4, 8],
                      [5, 2], [5, 6],
                      [6, 0], [6, 1], [6, 2], [6, 3], [6, 4],
                      [6, 5], [6, 6], [6, 7], [6, 8],
                      [7, 0], [7, 4], [7, 8],
                      [8, 0], [8, 1], [8, 2], [8, 3], [8, 4],
                      [8, 5], [8, 6], [8, 7], [8, 8],
                      [9, 2], [9, 6]]
