# This code is part of Qiskit.
#
# (C) Copyright IBM 2020, 2021
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Experiment integration tests."""

import os
from unittest import mock, SkipTest, skipIf
import contextlib

import numpy as np

from qiskit import transpile
from qiskit.providers import JobStatus
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.ibmq.experiment import (IBMExperimentService,
                                              ResultQuality,
                                              IBMExperimentEntryNotFound)
from qiskit.tools.visualization import HAS_MATPLOTLIB

from ...ibmqtestcase import IBMQTestCase
from ...decorators import requires_provider, requires_device


try:
    from qiskit_experiments.stored_data import StoredDataV1 as StoredData
    from qiskit_experiments.stored_data import AnalysisResultV1 as AnalysisResult
    HAS_QISKIT_EXPERIMENTS = True
except ImportError:
    HAS_QISKIT_EXPERIMENTS = False


@skipIf(not os.environ.get('USE_STAGING_CREDENTIALS', ''), "Only runs on staging")
@skipIf(not HAS_QISKIT_EXPERIMENTS, "Requires qiskit-experiments")
class TestExperimentDataIntegration(IBMQTestCase):
    """Test experiment service with experiment data."""

    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = cls._setup_provider()    # pylint: disable=no-value-for-parameter
        if not cls.provider.has_service('experiment'):
            raise SkipTest("Not authorized to use experiment service.")

        cls.backend = cls._setup_backend()  # pylint: disable=no-value-for-parameter
        cls.device_components = cls.provider.experiment.device_components(cls.backend.name())
        if not cls.device_components:
            raise SkipTest("No device components found.")
        cls.circuit = transpile(ReferenceCircuits.bell(), cls.backend)
        cls.experiment = cls.provider.experiment

    @classmethod
    @requires_provider
    def _setup_provider(cls, provider):
        """Get the provider for the class."""
        return provider

    @classmethod
    @requires_device
    def _setup_backend(cls, backend):
        """Get a backend for the class."""
        return backend

    def setUp(self) -> None:
        """Test level setup."""
        super().setUp()
        self.experiments_to_delete = []
        self.results_to_delete = []
        self.jobs_to_cancel = []

    def tearDown(self):
        """Test level tear down."""
        for result_uuid in self.results_to_delete:
            try:
                with mock.patch('builtins.input', lambda _: 'y'):
                    self.experiment.delete_analysis_result(result_uuid)
            except Exception as err:    # pylint: disable=broad-except
                self.log.info("Unable to delete analysis result %s: %s", result_uuid, err)
        for expr_uuid in self.experiments_to_delete:
            try:
                with mock.patch('builtins.input', lambda _: 'y'):
                    self.experiment.delete_experiment(expr_uuid)
            except Exception as err:    # pylint: disable=broad-except
                self.log.info("Unable to delete experiment %s: %s", expr_uuid, err)
        for job in self.jobs_to_cancel:
            with contextlib.suppress(Exception):
                job.cancel()
        super().tearDown()

    def test_service_options(self):
        """Test service options."""
        self.assertFalse(self.experiment.option['auto_save'])

    def test_add_data_job(self):
        """Test add job to experiment data."""
        exp_data = StoredData(backend=self.backend, experiment_type="qiskit_test")
        transpiled = transpile(ReferenceCircuits.bell(), self.backend)
        transpiled.metadata = {"foo": "bar"}
        job = self._run_circuit(transpiled)
        exp_data.add_data(job)
        self.assertEqual([job.job_id()], exp_data.job_ids)
        result = job.result()
        exp_data.block_for_jobs()
        circuit_data = exp_data.data(0)
        self.assertEqual(result.get_counts(0), circuit_data['counts'])
        self.assertEqual(job.job_id(), circuit_data['job_id'])
        self.assertEqual(transpiled.metadata, circuit_data['metadata'])

    def test_new_experiment_data(self):
        """Test creating a new experiment data."""
        metadata = {"complex": 2 + 3j, "numpy": np.zeros(2)}
        exp_data = StoredData(backend=self.backend,
                              experiment_type="qiskit_test",
                              tags=["foo", "bar"],
                              share_level="hub",
                              metadata=metadata,
                              notes="some notes")

        job_ids = []
        for _ in range(2):
            job = self._run_circuit()
            exp_data.add_data(job)
            job_ids.append(job.job_id())

        exp_data.save()
        self.experiments_to_delete.append(exp_data.experiment_id)

        credentials = self.provider.credentials
        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertIsInstance(rexp, StoredData)
        self._verify_experiment_data(exp_data, rexp)
        self.assertEqual(credentials.hub, rexp.hub)  # pylint: disable=no-member
        self.assertEqual(credentials.group, rexp.group)  # pylint: disable=no-member
        self.assertEqual(credentials.project, rexp.project)  # pylint: disable=no-member

    def test_update_experiment_data(self):
        """Test updating an experiment."""
        exp_data = self._create_experiment_data()

        metadata = {"complex": 2 + 3j, "numpy": np.zeros(2)}
        for _ in range(2):
            job = self._run_circuit()
            exp_data.add_data(job)
        exp_data.update_tags(["foo", "bar"])
        exp_data.share_level = "hub"
        exp_data.update_metadata(metadata)
        exp_data.notes = "some notes"
        exp_data.save()

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self._verify_experiment_data(exp_data, rexp)

    def _verify_experiment_data(self, expected, actual):
        """Verify the input experiment data."""
        self.assertEqual(expected.experiment_id, actual.experiment_id)
        self.assertEqual(expected.job_ids, actual.job_ids)
        self.assertEqual(expected.share_level, actual.share_level)
        self.assertEqual(expected.tags(), actual.tags())
        self.assertEqual(expected.notes, actual.notes)
        self.assertEqual(expected.metadata()['complex'], actual.metadata()['complex'])
        self.assertEqual(expected.metadata()['numpy'].all(), actual.metadata()['numpy'].all())
        self.assertTrue(actual.creation_datetime)
        self.assertTrue(getattr(actual, 'creation_datetime').tzinfo)

    def test_add_analysis_result(self):
        """Test adding an analysis result."""
        exp_data = self._create_experiment_data()
        result_data = {"complex": 2 + 3j, "numpy": np.zeros(2)}
        aresult = AnalysisResult(result_data=result_data,
                                 result_type='qiskit_test',
                                 device_components=self.device_components,
                                 experiment_id=exp_data.experiment_id,
                                 quality=ResultQuality.GOOD,
                                 verified=True,
                                 tags=["foo", "bar"],
                                 service=self.experiment)
        exp_data.add_analysis_result(aresult)
        exp_data.save_all()

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        rresult = rexp.analysis_result(0)
        self._verify_analysis_result(aresult, rresult)

    def test_update_analysis_result(self):
        """Test updating an analysis result."""
        aresult, exp_data = self._create_analysis_result()

        rdata = {"complex": 2 + 3j, "numpy": np.zeros(2)}
        aresult.update_data(rdata)
        aresult.quality = ResultQuality.GOOD
        aresult.verified = True
        aresult.update_tags(["foo", "bar"])
        aresult.save()

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        rresult = rexp.analysis_result(0)
        self._verify_analysis_result(aresult, rresult)

    def _verify_analysis_result(self, expected: AnalysisResult, actual: AnalysisResult):
        """Verify the input analysis result."""
        self.assertEqual(expected.result_id, actual.result_id)
        self.assertEqual(expected.result_type, actual.result_type)
        self.assertEqual(str(expected.device_components), str(actual.device_components))
        self.assertEqual(expected.experiment_id, actual.experiment_id)
        self.assertEqual(expected.quality, actual.quality)
        self.assertEqual(expected.verified, actual.verified)
        self.assertEqual(expected.tags(), actual.tags())
        self.assertEqual(expected.data()['complex'], actual.data()['complex'])
        self.assertEqual(expected.data()['numpy'].all(), actual.data()['numpy'].all())
        self.assertTrue(actual.creation_datetime)
        self.assertTrue(getattr(actual, 'creation_datetime').tzinfo)

    def test_delete_analysis_result(self):
        """Test deleting an analysis result."""
        aresult, exp_data = self._create_analysis_result()
        with mock.patch('builtins.input', lambda _: 'y'):
            exp_data.delete_analysis_result(0)
            exp_data.save_all()
        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertRaises(IBMExperimentEntryNotFound, rexp.analysis_result, aresult.result_id)
        self.assertRaises(IBMExperimentEntryNotFound,
                          self.experiment.analysis_result, aresult.result_id)

    def test_add_figure(self):
        """Test adding a figure to the experiment data."""
        exp_data = self._create_experiment_data()
        hello_bytes = str.encode("hello world")

        sub_tests = ["hello.svg", None]

        for idx, figure_name in enumerate(sub_tests):
            with self.subTest(figure_name=figure_name):
                exp_data.add_figure(figure=hello_bytes, figure_name=figure_name, save_figure=True)
                rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
                self.assertEqual(rexp.figure(idx), hello_bytes)

    @skipIf(not HAS_MATPLOTLIB, "matplotlib not available.")
    def test_add_figure_plot(self):
        """Test adding a matplotlib figure."""
        import matplotlib.pyplot as plt
        figure, axes = plt.subplots()
        axes.plot([1, 2, 3])

        exp_data = self._create_experiment_data()
        exp_data.add_figures(figure, save_figure=True)

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertTrue(rexp.figure(0))

    def test_add_figure_file(self):
        """Test adding a figure file."""
        exp_data = self._create_experiment_data()
        hello_bytes = str.encode("hello world")
        file_name = "hello_world.svg"
        self.addCleanup(os.remove, file_name)
        with open(file_name, "wb") as file:
            file.write(hello_bytes)

        exp_data.add_figure(figure=file_name, save_figure=True)
        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertEqual(rexp.figure(0), hello_bytes)

    def test_update_figure(self):
        """Test updating a figure."""
        exp_data = self._create_experiment_data()
        hello_bytes = str.encode("hello world")
        figure_name = "hello.svg"

        exp_data.add_figure(figure=hello_bytes, figure_name=figure_name, save_figure=True)
        self.assertEqual(exp_data.figure(0), hello_bytes)

        friend_bytes = str.encode("hello friend")
        exp_data.add_figure(figure=friend_bytes, figure_name=figure_name,
                            overwrite=True, save_figure=True)
        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertEqual(rexp.figure(0), friend_bytes)
        self.assertEqual(rexp.figure(figure_name), friend_bytes)

    def test_delete_figure(self):
        """Test deleting a figure."""
        exp_data = self._create_experiment_data()
        hello_bytes = str.encode("hello world")
        figure_name = "hello.svg"

        exp_data.add_figure(figure=hello_bytes, figure_name=figure_name, save_figure=True)
        with mock.patch('builtins.input', lambda _: 'y'):
            exp_data.delete_figure(0)
            exp_data.save_all()

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertRaises(IBMExperimentEntryNotFound, rexp.figure, figure_name)
        self.assertRaises(IBMExperimentEntryNotFound,
                          self.experiment.figure, exp_data.experiment_id, figure_name)

    def test_save_all(self):
        """Test saving all."""
        exp_data = self._create_experiment_data()
        exp_data.update_tags(["foo", "bar"])
        aresult = AnalysisResult(result_data={},
                                 result_type='qiskit_test',
                                 device_components=self.device_components,
                                 experiment_id=exp_data.experiment_id)
        exp_data.add_analysis_result(aresult)
        hello_bytes = str.encode("hello world")
        exp_data.add_figure(hello_bytes, figure_name="hello.svg")
        exp_data.save_all()

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertEqual(["foo", "bar"], rexp.tags())
        self.assertEqual(aresult.result_id, rexp.analysis_result(0).result_id)
        self.assertEqual(hello_bytes, rexp.figure(0))

        exp_data.delete_analysis_result(0)
        exp_data.delete_figure(0)
        with mock.patch('builtins.input', lambda _: 'y'):
            exp_data.save_all()

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertRaises(IBMExperimentEntryNotFound, rexp.figure, "hello.svg")
        self.assertRaises(IBMExperimentEntryNotFound, rexp.analysis_result, aresult.result_id)

    def test_set_service_job(self):
        """Test setting service with a job."""
        exp_data = StoredData(experiment_type="qiskit_test")
        job = self._run_circuit()
        exp_data.add_data(job)
        exp_data.save()

        rexp = self.experiment.experiment(exp_data.experiment_id, StoredData)
        self.assertEqual([job.job_id()], rexp.job_ids)

    def test_auto_save_experiment(self):
        """Test auto save."""
        exp_data = self._create_experiment_data()
        exp_data.auto_save = True

        subtests = [
            (exp_data.update_tags, (["foo"],)),
            (exp_data.update_metadata, ({"foo": "bar"},)),
            (setattr, (exp_data, "notes", "foo")),
            (setattr, (exp_data, "share_level", "hub"))
        ]

        for func, params in subtests:
            with self.subTest(func=func):
                with mock.patch.object(IBMExperimentService, 'update_experiment',
                                       wraps=exp_data.service.update_experiment) as mocked:
                    func(*params)
                    mocked.assert_called_once()
                    _, kwargs = mocked.call_args
                    self.assertEqual(exp_data.experiment_id, kwargs['experiment_id'])
                    mocked.reset_mock()

    def test_auto_save_figure(self):
        """Test auto saving figure."""
        exp_data = self._create_experiment_data()
        exp_data.auto_save = True
        figure_name = "hello.svg"

        with mock.patch.object(IBMExperimentService, 'update_experiment',
                               wraps=exp_data.service.update_experiment) as mocked_exp:
            with mock.patch.object(IBMExperimentService, 'create_figure',
                                   wraps=exp_data.service.create_figure) as mocked_fig:
                exp_data.add_figure(str.encode("hello world"), figure_name=figure_name)
                mocked_exp.assert_called_once()
                mocked_fig.assert_called_once()
                mocked_exp.reset_mock()

            with mock.patch.object(IBMExperimentService, 'update_figure',
                                   wraps=exp_data.service.update_figure) as mocked_fig:
                exp_data.add_figure(str.encode("hello friend"), figure_name=figure_name,
                                    overwrite=True)
                mocked_fig.assert_called_once()
                mocked_exp.assert_called_once()
                mocked_exp.reset_mock()

            with mock.patch.object(IBMExperimentService, 'delete_figure',
                                   wraps=exp_data.service.delete_figure) as mocked_fig, \
                    mock.patch('builtins.input', lambda _: 'y'):
                exp_data.delete_figure(figure_name)
                mocked_fig.assert_called_once()
                mocked_exp.assert_called_once()

    def test_auto_save_analysis_result(self):
        """Test auto saving analysis result."""
        exp_data = self._create_experiment_data()
        exp_data.auto_save = True
        aresult = AnalysisResult(result_data={},
                                 result_type='qiskit_test',
                                 device_components=self.device_components,
                                 experiment_id=exp_data.experiment_id)

        with mock.patch.object(IBMExperimentService, 'update_experiment',
                               wraps=exp_data.service.update_experiment) as mocked_exp:
            with mock.patch.object(IBMExperimentService, 'create_analysis_result',
                                   wraps=exp_data.service.create_analysis_result) as mocked_res:
                exp_data.add_analysis_result(aresult)
                mocked_exp.assert_called_once()
                mocked_res.assert_called_once()
                mocked_exp.reset_mock()

            with mock.patch.object(IBMExperimentService, 'delete_analysis_result',
                                   wraps=exp_data.service.delete_analysis_result) as mocked_res, \
                    mock.patch('builtins.input', lambda _: 'y'):
                exp_data.delete_analysis_result(aresult.result_id)
                mocked_res.assert_called_once()
                mocked_exp.assert_called_once()

    def test_auto_save_analysis_result_update(self):
        """Test auto saving analysis result updates."""
        aresult, exp_data = self._create_analysis_result()
        aresult.auto_save = True

        subtests = [
            (aresult.update_tags, (["foo"],)),
            (aresult.update_data, ({"foo": "bar"},)),
            (setattr, (aresult, "quality", "GOOD")),
            (setattr, (aresult, "verified", True))
        ]
        for func, params in subtests:
            with self.subTest(func=func):
                with mock.patch.object(IBMExperimentService, 'update_analysis_result',
                                       wraps=exp_data.service.update_analysis_result) as mocked:
                    func(*params)
                    mocked.assert_called_once()
                    _, kwargs = mocked.call_args
                    self.assertEqual(aresult.result_id, kwargs['result_id'])
                    mocked.reset_mock()

    def test_block_for_jobs(self):
        """Test blocking for jobs"""
        exp_data = StoredData(backend=self.backend, experiment_type="qiskit_test")
        jobs = []
        for _ in range(2):
            job = self._run_circuit()
            exp_data.add_data(job)
            jobs.append(job)
        exp_data.block_for_jobs()
        self.assertTrue(all(job.status() == JobStatus.DONE for job in jobs))
        self.assertEqual("DONE", exp_data.status())

    def _create_experiment_data(self):
        """Create an experiment data."""
        exp_data = StoredData(backend=self.backend,
                              experiment_type="qiskit_test")
        exp_data.save()
        self.experiments_to_delete.append(exp_data.experiment_id)
        return exp_data

    def _create_analysis_result(self):
        """Create a simple analysis result."""
        exp_data = self._create_experiment_data()
        aresult = AnalysisResult(result_data={},
                                 result_type='qiskit_test',
                                 device_components=self.device_components,
                                 experiment_id=exp_data.experiment_id)
        exp_data.add_analysis_result(aresult)
        exp_data.save_all()
        self.results_to_delete.append(aresult.result_id)
        return aresult, exp_data

    def _run_circuit(self, circuit=None):
        """Run a circuit."""
        circuit = circuit or self.circuit
        job = self.backend.run(circuit, shots=1)
        self.jobs_to_cancel.append(job)
        return job
