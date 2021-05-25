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

"""Experiment integration tests."""

import os
from unittest import mock, SkipTest, skipIf
import contextlib

import numpy as np

from qiskit import transpile
from qiskit.providers import JobStatus
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.experiment import ExperimentDataV1 as ExperimentData
from qiskit.providers.experiment import AnalysisResultV1 as AnalysisResult
from qiskit.providers.experiment.constants import ResultQuality
from qiskit.providers.experiment.exceptions import ExperimentEntryNotFound
from qiskit.providers.ibmq.experiment import IBMExperimentService

from ...ibmqtestcase import IBMQTestCase
from ...decorators import requires_provider, requires_device


@skipIf(not os.environ.get('USE_STAGING_CREDENTIALS', ''), "Only runs on staging")
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
                    self.provider.experiment.delete_analysis_result(result_uuid)
            except Exception as err:    # pylint: disable=broad-except
                self.log.info("Unable to delete analysis result %s: %s", result_uuid, err)
        for expr_uuid in self.experiments_to_delete:
            try:
                with mock.patch('builtins.input', lambda _: 'y'):
                    self.provider.experiment.delete_experiment(expr_uuid)
            except Exception as err:    # pylint: disable=broad-except
                self.log.info("Unable to delete experiment %s: %s", expr_uuid, err)
        for job in self.jobs_to_cancel:
            with contextlib.suppress(Exception):
                job.cancel()
        super().tearDown()

    def test_service_options(self):
        """Test service options."""
        self.assertFalse(self.provider.experiment.option['auto_save'])

    def test_add_data_job(self):
        """Test add job to experiment data."""
        exp_data = ExperimentData(backend=self.backend, experiment_type="qiskit_test")
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
        exp_data = ExperimentData(backend=self.backend,
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
        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
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

        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
        self._verify_experiment_data(exp_data, rexp)

    def _verify_experiment_data(self, expected: ExperimentData, actual: ExperimentData):
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
                                 service=self.provider.experiment)
        exp_data.add_analysis_result(aresult)
        exp_data.save_all()

        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
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

        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
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
        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
        self.assertRaises(ExperimentEntryNotFound, rexp.analysis_result, aresult.result_id)
        self.assertRaises(ExperimentEntryNotFound,
                          self.provider.experiment.analysis_result, aresult.result_id)

    def test_add_figure(self):
        """Test adding a figure to the experiment data."""
        exp_data = self._create_experiment_data()
        hello_bytes = str.encode("hello world")

        sub_tests = ["hello.svg", None]

        for idx, figure_name in enumerate(sub_tests):
            with self.subTest(figure_name=figure_name):
                exp_data.add_figure(figure=hello_bytes, figure_name=figure_name, save_figure=True)
                rexp = self.provider.experiment.experiment(exp_data.experiment_id)
                self.assertEqual(rexp.figure(idx), hello_bytes)

    def test_add_figure_file(self):
        """Test adding a figure file."""
        exp_data = self._create_experiment_data()
        hello_bytes = str.encode("hello world")
        file_name = "hello_world.svg"
        self.addCleanup(os.remove, file_name)
        with open(file_name, "wb") as file:
            file.write(hello_bytes)

        exp_data.add_figure(figure=file_name, save_figure=True)
        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
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
        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
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

        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
        self.assertRaises(ExperimentEntryNotFound, rexp.figure, figure_name)
        self.assertRaises(ExperimentEntryNotFound,
                          self.provider.experiment.figure, exp_data.experiment_id, figure_name)

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

        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
        self.assertEqual(["foo", "bar"], rexp.tags())
        self.assertEqual(aresult.result_id, rexp.analysis_result(0).result_id)
        self.assertEqual(hello_bytes, rexp.figure(0))

        exp_data.delete_analysis_result(0)
        exp_data.delete_figure(0)
        with mock.patch('builtins.input', lambda _: 'y'):
            exp_data.save_all()

        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
        self.assertRaises(ExperimentEntryNotFound, rexp.figure, "hello.svg")
        self.assertRaises(ExperimentEntryNotFound, rexp.analysis_result, aresult.result_id)

    def test_set_service_job(self):
        """Test setting service with a job."""
        exp_data = ExperimentData(experiment_type="qiskit_test")
        job = self._run_circuit()
        exp_data.add_data(job)
        exp_data.save()

        rexp = self.provider.experiment.experiment(exp_data.experiment_id)
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
        exp_data = ExperimentData(backend=self.backend, experiment_type="qiskit_test")
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
        exp_data = ExperimentData(backend=self.backend,
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




    #
    # def test_experiments(self):
    #     """Test retrieving experiments."""
    #     self.assertTrue(self.experiments, "No experiments found.")
    #     providers = ['/'.join([provider.credentials.hub, provider.credentials.group,
    #                            provider.credentials.project]) for provider in IBMQ.providers()]
    #     for exp in self.experiments:
    #         self.assertTrue(isinstance(exp, Experiment))
    #         self.assertTrue(exp.uuid, "{} does not have an uuid!".format(exp))
    #         for dt_attr in ['start_datetime', 'creation_datetime',
    #                         'end_datetime', 'updated_datetime']:
    #             if getattr(exp, dt_attr):
    #                 self.assertTrue(getattr(exp, dt_attr).tzinfo)
    #         if exp.share_level is not ExperimentShareLevel.PUBLIC:
    #             self.assertIn('/'.join([exp.hub, exp.group, exp.project]),
    #                           providers)
    #
    # def test_experiments_with_backend(self):
    #     """Test retrieving all experiments for a specific backend."""
    #     backend_name = self.experiments[0].backend_name
    #     ref_uuid = self.experiments[0].uuid
    #     backend_experiments = self.provider.experiment.experiments(
    #         backend_name=backend_name, limit=None)
    #
    #     found = False
    #     for exp in backend_experiments:
    #         self.assertEqual(exp.backend_name, backend_name)
    #         if exp.uuid == ref_uuid:
    #             found = True
    #     self.assertTrue(found, "Experiment {} not found when filter by backend name {}.".format(
    #         ref_uuid, backend_name))
    #
    # def test_experiments_with_type(self):
    #     """Test retrieving all experiments for a specific type."""
    #     expr_type = self.experiments[0].type
    #     ref_uuid = self.experiments[0].uuid
    #     backend_experiments = self.provider.experiment.experiments(type=expr_type, limit=None)
    #
    #     found = False
    #     for exp in backend_experiments:
    #         self.assertEqual(exp.type, expr_type)
    #         if exp.uuid == ref_uuid:
    #             found = True
    #     self.assertTrue(found, "Experiment {} not found when filter by type {}.".format(
    #         ref_uuid, expr_type))
    #
    # def test_experiments_with_start_time(self):
    #     """Test retrieving all experiments for a specific type."""
    #     ref_start_dt = self.experiments[0].start_datetime
    #     ref_uuid = self.experiments[0].uuid
    #
    #     before_start = ref_start_dt - timedelta(hours=1)
    #     after_start = ref_start_dt + timedelta(hours=1)
    #     sub_tests = [(before_start, None, True, "before start, None"),
    #                  (None, after_start, True, "None, after start"),
    #                  (before_start, after_start, True, "before, after start"),
    #                  (after_start, None, False, "after start, None"),
    #                  (None, before_start, False, "None, before start"),
    #                  (before_start, before_start, False, "before, before start")
    #                  ]
    #
    #     for start_dt, end_dt, expected, title in sub_tests:
    #         with self.subTest(title=title):
    #             backend_experiments = self.provider.experiment.experiments(
    #                 start_datetime=start_dt, end_datetime=end_dt, limit=None)
    #             found = False
    #             for exp in backend_experiments:
    #                 if start_dt:
    #                     self.assertGreaterEqual(exp.start_datetime, start_dt)
    #                 if end_dt:
    #                     self.assertLessEqual(exp.start_datetime, end_dt)
    #                 if exp.uuid == ref_uuid:
    #                     found = True
    #             self.assertEqual(found, expected,
    #                              "Experiment {} (not)found unexpectedly when filter using"
    #                              "start_dt={}, end_dt={}. Found={}".format(
    #                                  ref_uuid, start_dt, end_dt, found))
    #
    # def test_experiments_with_tags(self):
    #     """Test filtering experiments using tags."""
    #     ref_tags = None
    #     ref_expr = None
    #     for expr in self.experiments:
    #         if len(expr.tags) >= 2:
    #             ref_tags = expr.tags
    #             ref_expr = expr
    #             break
    #
    #     phantom_tag = uuid.uuid4().hex
    #     sub_tests = [
    #         (ref_tags, 'AND', True),
    #         (ref_tags, 'OR', True),
    #         (ref_tags + [phantom_tag], "AND", False),
    #         (ref_tags + [phantom_tag], "OR", True),
    #         ([phantom_tag], "OR", False)
    #     ]
    #     for tags, operator, found in sub_tests:
    #         with self.subTest(tags=tags, operator=operator):
    #             experiments = self.provider.experiment.experiments(
    #                 tags=tags, tags_operator=operator, limit=None)
    #             ref_expr_found = False
    #             for expr in experiments:
    #                 msg = "Tags {} not fond in experiment tags {}".format(tags, expr.tags)
    #                 if operator == 'AND':
    #                     self.assertTrue(all(f_tag in expr.tags for f_tag in tags), msg)
    #                 else:
    #                     self.assertTrue(any(f_tag in expr.tags for f_tag in tags), msg)
    #                 if expr.uuid == ref_expr.uuid:
    #                     ref_expr_found = True
    #             self.assertTrue(ref_expr_found == found,
    #                             "Experiment tags {} unexpectedly (not)found. Found={}".format(
    #                                 ref_expr.tags, found))
    #
    # def test_experiments_with_hgp(self):
    #     """Test retrieving all experiments for a specific h/g/p."""
    #     ref_exp = self.experiments[0]
    #     hgp = [ref_exp.hub, ref_exp.group, ref_exp.project]
    #     sub_tests = [
    #         {'hub': hgp[0]},
    #         {'hub': hgp[0], 'group': hgp[1]},
    #         {'hub': hgp[0], 'group': hgp[1], 'project': hgp[2]}
    #     ]
    #
    #     for hgp_kwargs in sub_tests:
    #         with self.subTest(kwargs=hgp_kwargs.keys()):
    #             hgp_experiments = self.provider.experiment.experiments(**hgp_kwargs)
    #             expr_ids = []
    #             for expr in hgp_experiments:
    #                 for hgp_key, hgp_val in hgp_kwargs.items():
    #                     self.assertEqual(getattr(expr, hgp_key), hgp_val, repr(expr))
    #                 expr_ids.append(expr.uuid)
    #             self.assertIn(ref_exp.uuid, expr_ids)
    #
    # def test_experiments_with_hgp_error(self):
    #     """Test retrieving experiments with bad h/g/p specification."""
    #     sub_tests = [
    #         ({'project': 'test_project'}, ['hub', 'group']),
    #         ({'project': 'test_project', 'group': 'test_group'}, ['hub']),
    #         ({'project': 'test_project', 'hub': 'test_hub'}, ['group']),
    #         ({'group': 'test_group'}, ['hub'])
    #     ]
    #
    #     for hgp_kwargs, missing_keys in sub_tests:
    #         with self.subTest(kwargs=hgp_kwargs.keys()):
    #             with self.assertRaises(ValueError) as ex_cm:
    #                 self.provider.experiment.experiments(**hgp_kwargs)
    #             for key in missing_keys:
    #                 self.assertIn(key, str(ex_cm.exception))
    #
    # def test_experiments_with_exclude_public(self):
    #     """Tests retrieving experiments with exclude_public filter."""
    #     # Make sure that we have at least one public experiment and one non-public
    #     # experiment.
    #     public_exp = self._create_experiment(share_level=ExperimentShareLevel.PUBLIC)
    #     non_public_exp = self._create_experiment()
    #
    #     experiments = self.provider.experiment.experiments(exclude_public=True)
    #     # The public experiment we just created should not be in the set.
    #     non_public_experiment_uuids = []
    #     for experiment in experiments:
    #         self.assertNotEqual(
    #             experiment.share_level, ExperimentShareLevel.PUBLIC,
    #             'Public experiment should not be returned with exclude_public filter: %s' %
    #             experiment)
    #         non_public_experiment_uuids.append(experiment.uuid)
    #     self.assertIn(
    #         non_public_exp.uuid, non_public_experiment_uuids,
    #         'Non-public experiment not returned with exclude_public filter: %s' %
    #         non_public_exp)
    #     self.assertNotIn(
    #         public_exp.uuid, non_public_experiment_uuids,
    #         'Public experiment returned with exclude_public filter: %s' %
    #         public_exp)
    #
    # def test_experiments_with_public_only(self):
    #     """Tests retrieving experiments with public_only filter."""
    #     # Make sure that we have at least one public experiment and one non-public
    #     # experiment.
    #     public_exp = self._create_experiment(share_level=ExperimentShareLevel.PUBLIC)
    #     non_public_exp = self._create_experiment()
    #
    #     experiments = self.provider.experiment.experiments(public_only=True)
    #     public_experiment_uuids = []
    #     for experiment in experiments:
    #         self.assertEqual(
    #             experiment.share_level, ExperimentShareLevel.PUBLIC,
    #             'Only public experiments should be returned with public_only filter: %s' %
    #             experiment)
    #         public_experiment_uuids.append(experiment.uuid)
    #     self.assertIn(
    #         public_exp.uuid, public_experiment_uuids,
    #         'Public experiment not returned with public_only filter: %s' %
    #         public_exp)
    #     self.assertNotIn(
    #         non_public_exp.uuid, public_experiment_uuids,
    #         'Non-public experiment returned with public_only filter: %s' %
    #         non_public_exp)
    #
    # def test_experiments_with_public_filters_error(self):
    #     """Tests that exclude_public and public_only cannot both be True."""
    #     with self.assertRaisesRegex(
    #             ValueError,
    #             'exclude_public and public_only cannot both be True'):
    #         self.provider.experiment.experiments(exclude_public=True, public_only=True)
    #
    # def test_experiments_with_exclude_mine(self):
    #     """Tests retrieving experiments with exclude_mine filter."""
    #     # Note that we cannot specify the owner when creating the experiment, the value comes
    #     # from the user profile via the token so we would have to use different test accounts
    #     # to explicitly create separately-owned epxeriments. We should be able to assume that
    #     # there is at least one experiment owned by another user in the integration test
    #     # environment though.
    #     my_exp = self._create_experiment()
    #     not_my_experiments = self.provider.experiment.experiments(exclude_mine=True)
    #     # The experiment we just created should not be in the set.
    #     not_mine_experiment_uuids = []
    #     for experiment in not_my_experiments:
    #         self.assertNotEqual(
    #             experiment.owner, my_exp.owner,  # pylint: disable=no-member
    #             'My experiment should not be returned with exclude_mine filter: %s' %
    #             experiment)
    #         not_mine_experiment_uuids.append(experiment.uuid)
    #     self.assertNotIn(
    #         my_exp.uuid, not_mine_experiment_uuids,
    #         'My experiment returned with exclude_mine filter: %s' %
    #         my_exp)
    #
    # def test_experiments_with_mine_only(self):
    #     """Tests retrieving experiments with mine_only filter."""
    #     # Note that we cannot specify the owner when creating the experiment, the value comes
    #     # from the user profile via the token so we would have to use different test accounts
    #     # to explicitly create separately-owned epxeriments. We should be able to assume that
    #     # there is at least one experiment owned by another user in the integration test
    #     # environment though.
    #     my_exp = self._create_experiment()
    #     my_experiments = self.provider.experiment.experiments(mine_only=True)
    #     my_experiment_uuids = []
    #     for experiment in my_experiments:
    #         self.assertEqual(
    #             experiment.owner, my_exp.owner,  # pylint: disable=no-member
    #             'Only my experiments should be returned with mine_only filter: %s' %
    #             experiment)
    #         my_experiment_uuids.append(experiment.uuid)
    #     self.assertIn(
    #         my_exp.uuid, my_experiment_uuids,
    #         'My experiment not returned with mine_only filter: %s' %
    #         my_exp)
    #
    # def test_experiments_with_owner_filters_error(self):
    #     """Tests that exclude_mine and mine_only cannot both be True."""
    #     with self.assertRaisesRegex(
    #             ValueError,
    #             'exclude_mine and mine_only cannot both be True'):
    #         self.provider.experiment.experiments(exclude_mine=True, mine_only=True)
    #
    # def test_retrieve_experiment(self):
    #     """Test retrieving an experiment by its ID."""
    #     exp = self.experiments[0]
    #     rexp = self.provider.experiment.retrieve_experiment(exp.uuid)
    #     self.assertEqual(exp.uuid, rexp.uuid)
    #     for attr in ['hub', 'group', 'project', 'owner', 'share_level']:
    #         self.assertIsNotNone(getattr(rexp, attr), "{} does not have a {}".format(rexp, attr))
    #

    #
    # def test_update_experiment(self):
    #     """Test updating an experiment."""
    #     new_exp = self._create_experiment(notes='test note')
    #     new_exp.end_datetime = datetime.now()
    #     new_exp.share_level = ExperimentShareLevel.PROJECT
    #     new_exp.notes = ''  # Clear the notes
    #     self.provider.experiment.update_experiment(new_exp)
    #     rexp = self.provider.experiment.retrieve_experiment(new_exp.uuid)
    #     self.assertEqual(new_exp.end_datetime, rexp.end_datetime)
    #     self.assertEqual(ExperimentShareLevel.PROJECT, rexp.share_level)
    #     self.assertIsNone(rexp.notes)
    #
    # def test_delete_experiment(self):
    #     """Test deleting an experiment."""
    #     new_exp = self._create_experiment(notes='delete me')
    #
    #     with mock.patch('builtins.input', lambda _: 'y'):
    #         deleted_exp = self.provider.experiment.delete_experiment(new_exp.uuid)
    #     self.assertEqual(deleted_exp.uuid, new_exp.uuid)
    #     self.assertEqual('delete me', new_exp.notes)
    #
    #     with self.assertRaises(ExperimentNotFoundError) as ex_cm:
    #         self.provider.experiment.retrieve_experiment(new_exp.uuid)
    #     self.assertIn("Not Found for url", ex_cm.exception.message)
    #
    # def test_reference_experiment_analysis_results(self):
    #     """Test referencing analysis results in an experiment."""
    #     ref_result = self.provider.experiment.analysis_results()[0]
    #     experiment = self.provider.experiment.retrieve_experiment(ref_result.experiment_uuid)
    #     for result in experiment.analysis_results:
    #         self.assertEqual(result.experiment_uuid, ref_result.experiment_uuid)
    #
    # def test_get_analysis_results(self):
    #     """Test retrieving all analysis results."""
    #     results = self.provider.experiment.analysis_results()
    #     for res in results:
    #         self.assertTrue(isinstance(res, AnalysisResult))
    #         self.assertIsInstance(res.verified, bool)
    #         self.assertIsInstance(res.fit, dict)
    #         self.assertTrue(res.uuid, "{} does not have an uuid!".format(res))
    #         for dt_attr in ['creation_datetime', 'updated_datetime']:
    #             if getattr(res, dt_attr):
    #                 self.assertTrue(getattr(res, dt_attr).tzinfo)
    #
    # def test_upload_analysis_result(self):
    #     """Test uploading an analysis result."""
    #     ref_result = self.provider.experiment.analysis_results()[0]
    #     device_comp = self.device_components[0]
    #     new_experiment = self._create_experiment(device_comp.backend_name)
    #     new_result = AnalysisResult(experiment_uuid=new_experiment.uuid,
    #                                 fit=ref_result.fit,
    #                                 result_type=ref_result.type,
    #                                 device_components=[device_comp.type],
    #                                 quality='No Information',
    #                                 tags=['qiskit-test'],
    #                                 chisq=ref_result.chisq)
    #     self.provider.experiment.upload_analysis_result(new_result)
    #     self.results_to_delete.append(new_result.uuid)
    #
    #     rresult = self.provider.experiment.retrieve_analysis_result(new_result.uuid)
    #     sub_tests = [(new_result, 'local result'), (rresult, 'retrieved result')]
    #     self.log.debug("Verifying analysis result %s", new_result.uuid)
    #     for res, name in sub_tests:
    #         with self.subTest(sub_test_name=name):
    #             self.assertIsNotNone(res.uuid)
    #             self.assertTrue(res.creation_datetime.tzinfo)
    #             self.assertEqual(res.experiment_uuid, new_experiment.uuid)
    #             self.assertEqual(res.fit, ref_result.fit)
    #             self.assertEqual(res.type, ref_result.type)
    #             self.assertEqual(res.device_components, [device_comp.type])
    #             self.assertEqual(res.quality.value, 'No Information')
    #             self.assertEqual(res.tags, ['qiskit-test'])
    #             self.assertFalse(res.verified)
    #
    # def test_update_analysis_result(self):
    #     """Test updating an analysis result."""
    #     new_result = self._create_analysis_result()
    #     original_type = new_result.type
    #     new_result.quality = ResultQuality.BAD  # pylint: disable=no-member
    #     new_result.verified = True
    #     new_fit = dict(
    #         value=new_result.fit['value']*2,
    #         variance=new_result.fit['variance']*2
    #     )
    #     new_result.fit = new_fit
    #     self.provider.experiment.update_analysis_result(new_result)
    #
    #     rresult = self.provider.experiment.retrieve_analysis_result(new_result.uuid)
    #     sub_tests = [(new_result, 'local result'), (rresult, 'retrieved result')]
    #     for res, name in sub_tests:
    #         with self.subTest(sub_test_name=name):
    #             self.assertEqual(res.fit, new_fit)
    #             self.assertEqual(res.type, original_type)
    #             self.assertEqual(res.quality, ResultQuality.BAD)  # pylint: disable=no-member
    #             self.assertTrue(res.updated_datetime.tzinfo)
    #             self.assertTrue(res.verified)
    #
    # def test_results_experiments_device_components(self):
    #     """Test filtering analysis results and experiments with device components."""
    #     results = self.provider.experiment.analysis_results()
    #     sub_tests = []
    #     ref_result = None
    #     for res in results:
    #         if len(res.device_components) >= 2:
    #             ref_result = res
    #             sub_tests.append((ref_result.device_components[:1], False))
    #             break
    #     if not ref_result:
    #         ref_result = results[0]
    #     sub_tests.append((ref_result.device_components, True))
    #
    #     for comp in self.device_components:
    #         if comp not in ref_result.device_components:
    #             sub_tests.append(([comp], False))
    #             break
    #
    #     for dev_comp, found in sub_tests:
    #         with self.subTest(dev_comp=dev_comp):
    #             f_results = self.provider.experiment.analysis_results(
    #                 device_components=dev_comp, limit=None)
    #             self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
    #                              "Analysis result {} with device component {} (not)found "
    #                              "unexpectedly when filter using device component={}. "
    #                              "Found={}.".format(ref_result.uuid, ref_result.device_components,
    #                                                 dev_comp, found))
    #             for result in f_results[:5]:    # Use a subset to reduce run time.
    #                 self.assertEqual(result.device_components, dev_comp,
    #                                  "Analysis result {} with device component {} "
    #                                  "does not match {}.".format(
    #                                      result.uuid, result.device_components, dev_comp))
    #
    #             f_experiments = self.provider.experiment.experiments(
    #                 device_components=dev_comp, limit=None)
    #             for exp in f_experiments[:5]:
    #                 found = False
    #                 result_dev_comp = []
    #                 for result in exp.analysis_results:
    #                     if result.device_components == dev_comp:
    #                         found = True
    #                         break
    #                     result_dev_comp.append(result.device_components)
    #                 self.assertTrue(
    #                     found, "Device components {} not found in analysis result for experiment "
    #                            "{}. Only {} found.".format(dev_comp, exp.uuid, result_dev_comp))
    #
    # def test_analysis_results_experiment_uuid(self):
    #     """Test filtering analysis results with experiment uuid."""
    #     ref_result = self.provider.experiment.analysis_results()[0]
    #     sub_tests = [(ref_result.experiment_uuid, True)]
    #     for expr in self.experiments:
    #         if expr.uuid != ref_result.experiment_uuid:
    #             sub_tests.append((expr.uuid, False))
    #             break
    #
    #     for expr_uuid, found in sub_tests:
    #         with self.subTest(expr_uuid=expr_uuid):
    #             f_results = self.provider.experiment.analysis_results(
    #                 experiment_id=expr_uuid, limit=None)
    #             self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
    #                              "Analysis result {} with experiment uuid {} (not)found "
    #                              "unexpectedly when filter using experiment uuid={}. "
    #                              "Found={}.".format(ref_result.uuid, ref_result.experiment_uuid,
    #                                                 expr_uuid, found))
    #             for result in f_results:
    #                 self.assertEqual(result.experiment_uuid, expr_uuid,
    #                                  "Analysis result {} with experiment uuid {} does not "
    #                                  "match {}.".format(result.uuid, result.experiment_uuid,
    #                                                     expr_uuid))
    #
    # def test_analysis_results_type(self):
    #     """Test filtering analysis results with type."""
    #     all_results = self.provider.experiment.analysis_results()
    #     ref_result = all_results[0]
    #     sub_tests = [(ref_result.type, True)]
    #     for res in all_results:
    #         if res.type != ref_result.type:
    #             sub_tests.append((res.type, False))
    #             break
    #
    #     for res_type, found in sub_tests:
    #         with self.subTest(res_type=res_type):
    #             f_results = self.provider.experiment.analysis_results(
    #                 result_type=res_type, limit=None)
    #             self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
    #                              "Analysis result {} with type {} (not)found unexpectedly "
    #                              "when filter using type={}. Found={}.".format(
    #                                  ref_result.uuid, ref_result.type, res_type, found))
    #             for result in f_results:
    #                 self.assertEqual(result.type, res_type,
    #                                  "Analysis result {} with type {} does not match {}.".format(
    #                                      result.uuid, result.type, res_type))
    #
    # def test_analysis_results_quality(self):
    #     """Test filtering analysis results with quality."""
    #     all_results = self.provider.experiment.analysis_results()
    #     ref_result = all_results[0]
    #     # Find a result whose quality is in the middle.
    #     bad_good = [ResultQuality.BAD, ResultQuality.GOOD]  # pylint: disable=no-member
    #     for result in all_results:
    #         if result.quality not in bad_good:
    #             ref_result = result
    #             break
    #
    #     sub_tests = [([('eq', ref_result.quality)], True)]
    #     higher = lower = None
    #     for quality in ResultQuality:
    #         if quality > ref_result.quality and not higher:
    #             higher = quality
    #             sub_tests.extend([
    #                 ([('lt', quality)], True),
    #                 ([('le', quality)], True),
    #                 ([('gt', quality)], False),
    #                 ([('ge', quality)], False),
    #             ])
    #         elif quality < ref_result.quality and not lower:
    #             lower = quality
    #             sub_tests.extend([
    #                 ([('lt', quality)], False),
    #                 ([('le', quality)], False),
    #                 ([('gt', quality)], True),
    #                 ([('ge', quality)], True),
    #             ])
    #     if higher and lower:
    #         sub_tests.append(([('gt', lower), ('lt', higher)], True))
    #
    #     operator_table = {'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>=', 'eq': '=='}
    #
    #     for quality, found in sub_tests:
    #         with self.subTest(quality=quality):
    #             f_results = self.provider.experiment.analysis_results(quality=quality, limit=None)
    #             self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
    #                              "Analysis result {} with quality {} (not)found unexpectedly "
    #                              "when filter using quality={}. Found={}.".format(
    #                                  ref_result.uuid, ref_result.quality, quality, found))
    #             for result in f_results:
    #                 for qual in quality:
    #                     self.assertTrue(
    #                         eval("result.quality {} qual[1]".format(  # pylint: disable=eval-used
    #                             operator_table[qual[0]])),
    #                         "Analysis result {} with quality {} does not match {}.".format(
    #                             result.uuid, result.quality, quality))
    #
    # def test_delete_analysis_result(self):
    #     """Test deleting an analysis result."""
    #     result = self._create_analysis_result()
    #     with mock.patch('builtins.input', lambda _: 'y'):
    #         self.provider.experiment.delete_analysis_result(result.uuid)
    #
    #     with self.assertRaises(AnalysisResultNotFoundError):
    #         self.provider.experiment.retrieve_analysis_result(result.uuid)
    #
    # def test_backend_components(self):
    #     """Test retrieving all device components."""
    #     self.assertTrue(self.device_components)
    #     self.assertTrue(all(isinstance(comp, DeviceComponent) for comp in self.device_components))
    #
    # def test_backend_components_backend_name(self):
    #     """Test retrieving device components for a specific backend."""
    #     ref_comp = self.device_components[0]
    #     components = self.provider.experiment.device_components(
    #         backend_name=ref_comp.backend_name)
    #     self.assertTrue(all(comp.backend_name == ref_comp.backend_name for comp in components))
    #     self.assertIn(ref_comp.uuid, [comp.uuid for comp in components])
    #
    # def test_retrieve_backends(self):
    #     """Test retrieving all backends."""
    #     backends = self.provider.experiment.backends()
    #     backend_names = [b['name'] for b in backends]
    #     self.assertIn(self.experiments[0].backend_name, backend_names)
    #
    # def test_plot(self):
    #     """Test uploading and retrieving a plot file."""
    #     new_exp = self._create_experiment()
    #     # Upload a new plot.
    #     hello_bytes = str.encode("hello world")
    #     file_name = "hello_world.svg"
    #     plot_name = "hello.svg"
    #     with open(file_name, 'wb') as file:
    #         file.write(hello_bytes)
    #     self.addCleanup(os.remove, file_name)
    #     response = self.provider.experiment.upload_plot(new_exp.uuid, file_name, plot_name)
    #     self.assertEqual(response['name'], plot_name)
    #     new_exp.refresh()
    #     self.assertIn(plot_name, new_exp.plot_names)
    #
    #     # Retrieve the plot we just uploaded.
    #     plot_content = self.provider.experiment.retrieve_plot(new_exp.uuid, plot_name)
    #     self.assertEqual(plot_content, hello_bytes)
    #
    #     # Delete plot.
    #     with mock.patch('builtins.input', lambda _: 'y'):
    #         self.provider.experiment.delete_plot(new_exp.uuid, plot_name)
    #     with self.assertRaises(PlotNotFoundError) as manager:
    #         self.provider.experiment.retrieve_plot(new_exp.uuid, plot_name)
    #     self.assertIn("not found", manager.exception.message)
    #
    # def test_upload_update_plot_data(self):
    #     """Test uploading and updating plot data."""
    #     new_exp = self._create_experiment()
    #     # Upload a new plot.
    #     plot_name = "batman.svg"
    #     hello_bytes = str.encode("hello world")
    #     plot_names = [plot_name, None]
    #     for name in plot_names:
    #         with self.subTest(name=name):
    #             response = self.provider.experiment.upload_plot(new_exp.uuid, hello_bytes, name)
    #             if name:
    #                 self.assertEqual(response['name'], name)
    #             else:
    #                 name = response['name']
    #             new_exp.refresh()
    #             self.assertIn(name, new_exp.plot_names)
    #
    #     # Update the plot we just uploaded.
    #     friend_bytes = str.encode("hello friend!")
    #     response = self.provider.experiment.update_plot(new_exp.uuid, friend_bytes, plot_name)
    #     self.assertEqual(response['name'], plot_name)
    #     rplot = self.provider.experiment.retrieve_plot(new_exp.uuid, plot_name)
    #     self.assertEqual(rplot, friend_bytes, "Retrieved plot not equal updated plot.")
    #
    # def test_experiments_limit(self):
    #     """Test getting experiments with a limit."""
    #     limits = [10, 1000, 1001]
    #
    #     for limit in limits:
    #         with self.subTest(limit=limit):
    #             experiments = self.provider.experiment.experiments(limit=limit)
    #             self.assertEqual(len(experiments), limit)
    #             self.assertEqual(len({expr.uuid for expr in experiments}), len(experiments))
    #
    #     with self.assertRaises(ValueError) as context_manager:
    #         self.provider.experiment.experiments(limit=-1)
    #     self.assertIn("limit", str(context_manager.exception))
    #
    # def test_analysis_results_limit(self):
    #     """Test getting analysis results with a limit."""
    #     limits = [10, 1000, 1001]
    #     for limit in limits:
    #         with self.subTest(limit=limit):
    #             results = self.provider.experiment.analysis_results(limit=limit)
    #             self.assertEqual(len(results), limit)
    #             self.assertEqual(len({res.uuid for res in results}), len(results))
    #
    #     with self.assertRaises(ValueError) as context_manager:
    #         self.provider.experiment.analysis_results(limit=-1)
    #     self.assertIn("limit", str(context_manager.exception))
    #
    # def _create_experiment(
    #         self,
    #         backend_name: Optional[str] = None,
    #         start_dt: Optional[datetime] = None,
    #         share_level: Optional[Union[ExperimentShareLevel, str]] = None,
    #         notes: Optional[str] = None
    # ) -> Experiment:
    #     backend_name = backend_name or self.experiments[0].backend_name
    #     new_exp = Experiment(  # pylint: disable=unexpected-keyword-arg
    #         provider=self.provider,
    #         backend_name=backend_name,
    #         experiment_type='test',
    #         tags=['qiskit-test'],
    #         start_datetime=start_dt,
    #         share_level=share_level,
    #         notes=notes
    #     )
    #     self.provider.experiment.upload_experiment(new_exp)
    #     self.experiments_to_delete.append(new_exp.uuid)
    #     return new_exp
    #
    # def _create_analysis_result(self):
    #     device_comp = self.device_components[0]
    #     new_experiment = self._create_experiment(device_comp.backend_name)
    #     fit = dict(value=41.456, variance=4.051)
    #     new_result = AnalysisResult(experiment_uuid=new_experiment.uuid,
    #                                 fit=fit,
    #                                 result_type="T1",
    #                                 device_components=[device_comp.type],
    #                                 tags=['qiskit-test'])
    #     self.provider.experiment.upload_analysis_result(new_result)
    #     self.results_to_delete.append(new_result.uuid)
    #     return new_result
