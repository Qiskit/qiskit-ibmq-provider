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

"""Tests for Jupyter tools."""

from unittest import mock
from datetime import datetime, timedelta

from qiskit import transpile
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.ibmq.jupyter.qubits_widget import qubits_tab
from qiskit.providers.ibmq.jupyter.config_widget import config_tab
from qiskit.providers.ibmq.jupyter.gates_widget import gates_tab
from qiskit.providers.ibmq.jupyter.jobs_widget import jobs_tab
from qiskit.providers.ibmq.visualization.interactive.error_map import iplot_error_map
from qiskit.providers.ibmq.jupyter.dashboard.backend_widget import make_backend_widget
from qiskit.providers.ibmq.jupyter.dashboard.utils import BackendWithProviders
from qiskit.providers.ibmq.jupyter.dashboard.job_widgets import create_job_widget
from qiskit.providers.ibmq.jupyter.dashboard.watcher_monitor import _job_checker

from ..decorators import requires_provider
from ..ibmqtestcase import IBMQTestCase


class TestBackendInfo(IBMQTestCase):
    """Test backend information Jupyter widget."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.backends = _get_backends(provider)

    def test_config_tab(self):
        """Test config tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                tab_str = str(config_tab(backend))
                config = backend.configuration()
                status = backend.status()
                self.assertIn(config.backend_name, tab_str)
                self.assertIn(str(status.status_msg), tab_str)

    def test_qubits_tab(self):
        """Test qubits tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                tab_str = str(qubits_tab(backend))
                props = backend.properties().to_dict()
                q0_t1 = round(props['qubits'][0][0]['value'], 3)
                q0_t2 = round(props['qubits'][0][1]['value'], 3)
                self.assertIn(str(q0_t1), tab_str)
                self.assertIn(str(q0_t2), tab_str)

    def test_gates_tab(self):
        """Test gates tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                gates_tab(backend)

    def test_error_map_tab(self):
        """Test error map tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                iplot_error_map(backend)

    def test_jobs_tab(self):
        """Test jobs tab."""
        def _limit_jobs(**kwargs):
            kwargs['limit'] = 5
            kwargs['skip'] = 5
            kwargs['start_datetime'] = datetime.now() - timedelta(days=7)
            return original_backend_jobs(**kwargs)

        for backend in self.backends:
            with self.subTest(backend=backend):
                original_backend_jobs = backend.jobs
                backend.jobs = _limit_jobs
                jobs_tab(backend)


class TestIQXDashboard(IBMQTestCase):
    """Test backend information Jupyter widget."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.backends = _get_backends(provider)

    def test_backend_widget(self):
        """Test devices tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                cred = backend.provider().credentials
                provider_str = "{}/{}/{}".format(cred.hub, cred.group, cred.project)
                b_w_p = BackendWithProviders(backend=backend, providers=[provider_str])
                make_backend_widget(b_w_p)

    def test_job_widget(self):
        """Test jobs tab."""
        backend = self.provider.get_backend('ibmq_qasm_simulator')
        job = backend.run(transpile(ReferenceCircuits.bell(), backend))
        create_job_widget(mock.MagicMock(), job, backend=backend.name(), status=job.status().value)

    def test_watcher_monitor(self):
        """Test job watcher."""
        backend = self.provider.get_backend('ibmq_qasm_simulator')
        job = backend.run(transpile(ReferenceCircuits.bell(), backend))
        _job_checker(job=job, status=job.status(), watcher=mock.MagicMock())


def _get_backends(provider):
    """Return backends for testing."""
    backends = []
    n_qubits = [1, 5]
    for n_qb in n_qubits:
        filtered_backends = provider.backends(
            operational=True, simulator=False, n_qubits=n_qb)
        if filtered_backends:
            backends.append(filtered_backends[0])
    return backends
