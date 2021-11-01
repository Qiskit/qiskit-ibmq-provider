# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBM Quantum Experience visualization library."""

import pkg_resources
# pylint: disable=not-an-iterable
INSTALLED_PACKAGES = [package.key for package in pkg_resources.working_set]

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

if ('ipykernel' in INSTALLED_PACKAGES) and ('spyder' not in INSTALLED_PACKAGES):
    if HAS_PLOTLY:
        from .error_map import iplot_error_map
        from .gate_map import iplot_gate_map
