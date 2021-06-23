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

from datetime import datetime, timedelta
import time
from unittest import mock
import uuid

from test.ibmq.runtime.fake_runtime_client import BaseFakeRuntimeClient

from qiskit.test.reference_circuits import ReferenceCircuits
# from qiskit.providers.ibmq.visualization.interactive.error_map import iplot_error_map
from qiskit.providers.ibmq.jupyter.dashboard.backend_widget import make_backend_widget
from qiskit.providers.ibmq.jupyter.dashboard.utils import BackendWithProviders
from qiskit.providers.ibmq.jupyter.dashboard.job_widgets import create_job_widget
from qiskit.providers.ibmq.jupyter.dashboard.dashboard import _IQX_DASHBOARD, IQXDashboardMagic
from qiskit.providers.ibmq.jupyter.dashboard.watcher_monitor import (
    job_monitor, CircuitJobMonitor, RuntimeJobMonitor)
from qiskit.providers.ibmq.jupyter.dashboard.runtime_program_widget import create_program_widget
from qiskit.providers.ibmq.jupyter.qubits_widget import qubits_tab
from qiskit.providers.ibmq.jupyter.config_widget import config_tab
from qiskit.providers.ibmq.jupyter.gates_widget import gates_tab
from qiskit.providers.ibmq.jupyter.jobs_widget import jobs_tab
from qiskit.providers.ibmq.runtime.runtime_program import RuntimeProgram
from qiskit.providers.ibmq.runtime.runtime_job import RuntimeJob
from qiskit.providers.ibmq.credentials.credentials import Credentials
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.job.ibmqjob import IBMQJob
from qiskit.test.mock import FakeBackend
from qiskit import transpile
from qiskit import assemble

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

    # def test_error_map_tab(self):
    #     """Test error map tab."""
    #     for backend in self.backends:
    #         with self.subTest(backend=backend):
    #             iplot_error_map(backend)

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


class TestJobMonitor(IBMQTestCase):
    """Tests the job monitor"""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider) -> None:
        """Class constants setup"""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        # Simulated backends
        cls.sim_backend: IBMQBackend = provider.get_backend('ibmq_qasm_simulator')
        # Dummy runtime API
        cls.runtime = BaseFakeRuntimeClient()
        # Dummy credentials
        cls.credentials = Credentials(
            token="", url="", services={"runtime": "https://quantum-computing.ibm.com"})

    def test_monitor_queue_circuit(self) -> None:
        """Tests a circuit monitors `_set_queue` function"""
        job = self.create_circuit_job()
        monitor = CircuitJobMonitor(job, mock.MagicMock())
        # Now we have to "trick" the monitor into updating
        monitor._prev_queue_pos = 'N/A'
        monitor._set_job_queued()

    def test_monitor_queue_runtime(self) -> None:
        """Tests a runtime monitors `_set_queue` function"""
        job = self.create_runtime_job()
        RuntimeJobMonitor(job, mock.MagicMock())._set_job_queued()

    def test_watcher_monitor_runtime(self) -> None:
        """Tests the `job_monitor` function for runtime job"""
        job = self.create_runtime_job()
        job_monitor(job, watcher=mock.MagicMock())
        while job.status().name != 'DONE':
            time.sleep(1)

    def test_watcher_monitor_circuit(self) -> None:
        """Tests the `job_monitor` function for circuit job"""
        job = self.create_circuit_job()
        job_monitor(job, watcher=mock.MagicMock())
        while job.status().name != 'DONE':
            time.sleep(1)

    @classmethod
    def create_runtime_job(cls) -> RuntimeJob:
        """Executes a circuit on Runtime. (Test)

        Returns:
            RuntimeJob: the job
        """
        program_id = cls._upload_program()['id']
        job_id = cls.runtime.program_run(program_id=program_id,
                                         credentials=cls.credentials,
                                         backend_name='test-backend',
                                         params='')['id']
        job = cls.runtime._get_job(job_id).job()
        return job

    def create_circuit_job(self) -> IBMQJob:
        """ Creates a circuit job via IBMQJobManager

        Returns:
            IBMQJob: the job
        """
        job = self.sim_backend.run(transpile(ReferenceCircuits.bell(), self.sim_backend))
        job._wait_for_completion()
        return job

    @classmethod
    def _upload_program(cls):
        """Upload a new program."""
        name = uuid.uuid4().hex
        data = "def main() {}"
        program_id = cls.runtime.program_create(
            program_data=data.encode(),
            name=name,
            description='A Test program',
            max_execution_time=300)
        return program_id


class TestIQXDashboard(IBMQTestCase):
    """Test backend information Jupyter widget."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider) -> None:
        """Class constants setup"""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.backends = _get_backends(provider)
        # Simulated backends
        cls.sim_backend: IBMQBackend = provider.get_backend('ibmq_qasm_simulator')
        cls.fake_backend = FakeBackend(cls.sim_backend.configuration())
        # Dummy credentials
        cls.credentials = Credentials(
            token="", url="", services={"runtime": "https://quantum-computing.ibm.com"})
        # Dummy runtime API
        cls.runtime = BaseFakeRuntimeClient()

        # The jobs to be used for testing
        cls.circ_job = None
        cls.rt_job = None

        # Startup IQX Dashboard
        IQXDashboardMagic().iqx_dashboard()
        cls.dash = _IQX_DASHBOARD
        cls.dash.runtime_progs.runtime_programs = [
            RuntimeProgram(program_name='test-name',
                           program_id='test-id',
                           description='test-description')]

    @classmethod
    def tearDownClass(cls) -> None:
        """Test level tear down."""
        super().tearDownClass()
        # Close IQX Dashboard
        IQXDashboardMagic().disable_ibmq_dashboard()

    def test_dashboard_adds_circuit_job(self) -> None:
        """Test adding a circuit job to the dashboard"""
        view = self.dash.circuit_jobs
        # Get the number of jobs before testing
        n_circuit_jobs = len(view.jobs)
        # Create and test circuit jobs
        self.circ_job = self.create_circuit_job(use_api=True)
        self.assertEqual(len(view.jobs), n_circuit_jobs + 1)

    def test_dashboard_adds_runtime_job(self) -> None:
        """Test adding a runtime job to the dashboard"""
        view = self.dash.runtime_jobs
        # Get the number of jobs before testing
        n_runtime_jobs = len(view.jobs)  # pylint: disable=no-member
        # Create and test runtime jobs
        self.rt_job = self.create_runtime_job()
        self.assertEqual(len(view.jobs), n_runtime_jobs + 1)   # pylint: disable=no-member

    def test_dashboard_refresh(self) -> None:
        """Test refreshing the dashboard"""
        self.dash.refresh()

    def test_dashboard_update_job(self) -> None:
        """Test updating a job on the dashboard"""
        circ_job = self.circ_job or self.create_circuit_job()
        rt_job = self.rt_job or self.create_runtime_job()
        self.dash.circuit_jobs.update_job((circ_job.job_id(), 'QUEUED', 1))
        self.dash.runtime_jobs.update_job((rt_job.job_id(), 'RUNNING'))

    def test_dashboard_cancel(self) -> None:
        """Test cancelling a job on the dashboard"""
        circ_job = self.circ_job or self.create_circuit_job()
        rt_job = self.rt_job or self.create_runtime_job()
        self.dash.circuit_jobs.cancel_job(job_id=circ_job.job_id())
        self.dash.runtime_jobs.cancel_job(job_id=rt_job.job_id())

    def test_dashboard_clear(self) -> None:
        """Test clearing inactive jobs from the dashboard"""
        self.dash.runtime_jobs.clear_done()
        self.dash.circuit_jobs.clear_done()

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
        backend = self.sim_backend
        job = backend.run(transpile(ReferenceCircuits.bell(), backend))
        create_job_widget(mock.MagicMock(), job, backend=backend.name(), status=job.status().value)

    def test_runtime_program_widget(self):
        """Test runtime tab."""
        # 1. Create runtime progran
        program = RuntimeProgram(program_name='test-name', program_id='test-id',
                                 description='test-description')
        # 2. Create runtime widget
        create_program_widget(program)

    def create_circuit_job(self, use_api: bool = True) -> IBMQJob:
        """ Creates a circuit job via IBMQJobManager

        Args:
            use_api: whether to ping the live API or locally simulate it

        Returns:
            IBMQJob: the job
        """
        if use_api:
            job = self.sim_backend.run(transpile(ReferenceCircuits.bell(), self.sim_backend))
            job._wait_for_completion()
            return job
        return self.fake_backend.run(assemble(ReferenceCircuits.bell()))

    @classmethod
    def create_runtime_job(cls) -> RuntimeJob:
        """Executes a circuit on Runtime. (Test)

        Returns:
            RuntimeJob: the job
        """
        program_id = cls._upload_program()['id']
        job_id = cls.runtime.program_run(program_id=program_id,
                                         credentials=cls.credentials,
                                         backend_name='test-backend',
                                         params='')['id']
        job = cls.runtime._get_job(job_id).job()
        return job

    @classmethod
    def _upload_program(cls):
        """Upload a new program."""
        name = uuid.uuid4().hex
        data = "def main() {}"
        program_id = cls.runtime.program_create(
            program_data=data.encode(),
            name=name,
            description='A Test program',
            max_execution_time=300)
        return program_id


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
