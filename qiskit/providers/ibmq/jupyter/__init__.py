# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2012.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""
================================================================
Jupyter Tools (:mod:`qiskit.providers.ibmq.jupyter`)
================================================================

.. currentmodule:: qiskit.providers.ibmq.jupyter

A Collection of Jupyter magic functions and tools
that extend the functionality of Qiskit for the IBM
Quantum devices.

Note:
    To use these tools locally, you'll need to install the
    additional dependencies for the visualization functions::

        pip install qiskit-ibmq-provider[visualization]

Detailed information on a single backend
========================================

.. jupyter-execute::
    :hide-code:
    :hide-output:

    from qiskit.test.ibmq_mock import mock_get_backend
    mock_get_backend('FakeVigo')

.. jupyter-execute::

    from qiskit import IBMQ
    import qiskit.providers.ibmq.jupyter

    IBMQ.load_account()
    provider = IBMQ.get_provider(hub='ibm-q')
    backend = provider.get_backend('ibmq_vigo')

.. jupyter-execute::
    :hide-code:
    :hide-output:

    backend.jobs = lambda *args, **kwargs: []

.. jupyter-execute::

    backend


IBM Quantum Experience (IQX) dashboard
======================================

.. code-block:: python

    from qiskit import IBMQ
    import qiskit.providers.ibmq.jupyter

    %iqx_dashboard

"""
import sys

if ('ipykernel' in sys.modules) and ('spyder' not in sys.modules):

    from IPython import get_ipython          # pylint: disable=import-error
    from .dashboard.dashboard import IQXDashboardMagic
    from qiskit.providers.fake_provider.fake_backend import FakeBackend
    from ..ibmqbackend import IBMQBackend
    from .backend_info import backend_widget

    _IP = get_ipython()
    if _IP is not None:
        _IP.register_magics(IQXDashboardMagic)
        HTML_FORMATTER = _IP.display_formatter.formatters['text/html']
        # Make backend_widget the html repr for IBM Quantum backends
        HTML_FORMATTER.for_type(IBMQBackend, backend_widget)
        HTML_FORMATTER.for_type(FakeBackend, backend_widget)
