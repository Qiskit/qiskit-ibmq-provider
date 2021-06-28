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

"""Experiment Tests."""

import os
import uuid
from unittest import mock, SkipTest, skipIf
from datetime import datetime, timedelta
from typing import Optional, Union

from qiskit.providers.ibmq.experiment.experiment import Experiment
from qiskit.providers.ibmq.experiment.analysis_result import AnalysisResult, DeviceComponent
from qiskit.providers.ibmq.experiment.exceptions import (ExperimentNotFoundError,
                                                         AnalysisResultNotFoundError,
                                                         PlotNotFoundError)
from qiskit.providers.ibmq.experiment.constants import ResultQuality, ExperimentShareLevel
from qiskit.providers.ibmq.exceptions import IBMQNotAuthorizedError
from qiskit.providers.ibmq import IBMQ


from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider


@skipIf(not os.environ.get('USE_STAGING_CREDENTIALS', ''), "Only runs on staging")
class TestExperiment(IBMQTestCase):
    """Test experiment modules."""

    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        try:
            cls.provider = cls._setup_provider()    # pylint: disable=no-value-for-parameter
            cls.experiments = cls.provider.experiment.experiments()
            cls.device_components = cls.provider.experiment.device_components()
        except Exception:
            raise SkipTest("Not authorized to use experiment service.")

    @classmethod
    @requires_provider
    def _setup_provider(cls, provider):
        """Get the provider for the class."""
        return provider

    def setUp(self) -> None:
        """Test level setup."""
        super().setUp()
        self.experiments_to_delete = []
        self.results_to_delete = []

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
        super().tearDown()

    def test_unauthorized(self):
        """Test unauthorized access."""
        saved_experiment = self.provider._experiment
        try:
            self.provider._experiment = None
            with self.assertRaises(IBMQNotAuthorizedError) as context_manager:
                self.provider.experiment.experiments()
            self.assertIn("experiment service", str(context_manager.exception))
        finally:
            self.provider._experiment = saved_experiment

    def test_experiments(self):
        """Test retrieving experiments."""
        self.assertTrue(self.experiments, "No experiments found.")
        providers = ['/'.join([provider.credentials.hub, provider.credentials.group,
                               provider.credentials.project]) for provider in IBMQ.providers()]
        for exp in self.experiments:
            self.assertTrue(isinstance(exp, Experiment))
            self.assertTrue(exp.uuid, "{} does not have an uuid!".format(exp))
            for dt_attr in ['start_datetime', 'creation_datetime',
                            'end_datetime', 'updated_datetime']:
                if getattr(exp, dt_attr):
                    self.assertTrue(getattr(exp, dt_attr).tzinfo)
            if exp.share_level is not ExperimentShareLevel.PUBLIC:
                self.assertIn('/'.join([exp.hub, exp.group, exp.project]),
                              providers)

    def test_experiments_with_backend(self):
        """Test retrieving all experiments for a specific backend."""
        backend_name = self.experiments[0].backend_name
        ref_uuid = self.experiments[0].uuid
        backend_experiments = self.provider.experiment.experiments(
            backend_name=backend_name, limit=None)

        found = False
        for exp in backend_experiments:
            self.assertEqual(exp.backend_name, backend_name)
            if exp.uuid == ref_uuid:
                found = True
        self.assertTrue(found, "Experiment {} not found when filter by backend name {}.".format(
            ref_uuid, backend_name))

    def test_experiments_with_type(self):
        """Test retrieving all experiments for a specific type."""
        expr_type = self.experiments[0].type
        ref_uuid = self.experiments[0].uuid
        backend_experiments = self.provider.experiment.experiments(type=expr_type, limit=None)

        found = False
        for exp in backend_experiments:
            self.assertEqual(exp.type, expr_type)
            if exp.uuid == ref_uuid:
                found = True
        self.assertTrue(found, "Experiment {} not found when filter by type {}.".format(
            ref_uuid, expr_type))

    def test_experiments_with_start_time(self):
        """Test retrieving all experiments for a specific type."""
        ref_start_dt = self.experiments[0].start_datetime
        ref_uuid = self.experiments[0].uuid

        before_start = ref_start_dt - timedelta(hours=1)
        after_start = ref_start_dt + timedelta(hours=1)
        sub_tests = [(before_start, None, True, "before start, None"),
                     (None, after_start, True, "None, after start"),
                     (before_start, after_start, True, "before, after start"),
                     (after_start, None, False, "after start, None"),
                     (None, before_start, False, "None, before start"),
                     (before_start, before_start, False, "before, before start")
                     ]

        for start_dt, end_dt, expected, title in sub_tests:
            with self.subTest(title=title):
                backend_experiments = self.provider.experiment.experiments(
                    start_datetime=start_dt, end_datetime=end_dt, limit=None)
                found = False
                for exp in backend_experiments:
                    if start_dt:
                        self.assertGreaterEqual(exp.start_datetime, start_dt)
                    if end_dt:
                        self.assertLessEqual(exp.start_datetime, end_dt)
                    if exp.uuid == ref_uuid:
                        found = True
                self.assertEqual(found, expected,
                                 "Experiment {} (not)found unexpectedly when filter using"
                                 "start_dt={}, end_dt={}. Found={}".format(
                                     ref_uuid, start_dt, end_dt, found))

    def test_experiments_with_tags(self):
        """Test filtering experiments using tags."""
        ref_tags = None
        ref_expr = None
        for expr in self.experiments:
            if len(expr.tags) >= 2:
                ref_tags = expr.tags
                ref_expr = expr
                break

        phantom_tag = uuid.uuid4().hex
        sub_tests = [
            (ref_tags, 'AND', True),
            (ref_tags, 'OR', True),
            (ref_tags + [phantom_tag], "AND", False),
            (ref_tags + [phantom_tag], "OR", True),
            ([phantom_tag], "OR", False)
        ]
        for tags, operator, found in sub_tests:
            with self.subTest(tags=tags, operator=operator):
                experiments = self.provider.experiment.experiments(
                    tags=tags, tags_operator=operator, limit=None)
                ref_expr_found = False
                for expr in experiments:
                    msg = "Tags {} not fond in experiment tags {}".format(tags, expr.tags)
                    if operator == 'AND':
                        self.assertTrue(all(f_tag in expr.tags for f_tag in tags), msg)
                    else:
                        self.assertTrue(any(f_tag in expr.tags for f_tag in tags), msg)
                    if expr.uuid == ref_expr.uuid:
                        ref_expr_found = True
                self.assertTrue(ref_expr_found == found,
                                "Experiment tags {} unexpectedly (not)found. Found={}".format(
                                    ref_expr.tags, found))

    def test_experiments_with_hgp(self):
        """Test retrieving all experiments for a specific h/g/p."""
        ref_exp = self.experiments[0]
        hgp = [ref_exp.hub, ref_exp.group, ref_exp.project]
        sub_tests = [
            {'hub': hgp[0]},
            {'hub': hgp[0], 'group': hgp[1]},
            {'hub': hgp[0], 'group': hgp[1], 'project': hgp[2]}
        ]

        for hgp_kwargs in sub_tests:
            with self.subTest(kwargs=hgp_kwargs.keys()):
                hgp_experiments = self.provider.experiment.experiments(**hgp_kwargs)
                expr_ids = []
                for expr in hgp_experiments:
                    for hgp_key, hgp_val in hgp_kwargs.items():
                        self.assertEqual(getattr(expr, hgp_key), hgp_val, repr(expr))
                    expr_ids.append(expr.uuid)
                self.assertIn(ref_exp.uuid, expr_ids)

    def test_experiments_with_hgp_error(self):
        """Test retrieving experiments with bad h/g/p specification."""
        sub_tests = [
            ({'project': 'test_project'}, ['hub', 'group']),
            ({'project': 'test_project', 'group': 'test_group'}, ['hub']),
            ({'project': 'test_project', 'hub': 'test_hub'}, ['group']),
            ({'group': 'test_group'}, ['hub'])
        ]

        for hgp_kwargs, missing_keys in sub_tests:
            with self.subTest(kwargs=hgp_kwargs.keys()):
                with self.assertRaises(ValueError) as ex_cm:
                    self.provider.experiment.experiments(**hgp_kwargs)
                for key in missing_keys:
                    self.assertIn(key, str(ex_cm.exception))

    def test_experiments_with_exclude_public(self):
        """Tests retrieving experiments with exclude_public filter."""
        # Make sure that we have at least one public experiment and one non-public
        # experiment.
        public_exp = self._create_experiment(share_level=ExperimentShareLevel.PUBLIC)
        non_public_exp = self._create_experiment()

        experiments = self.provider.experiment.experiments(exclude_public=True)
        # The public experiment we just created should not be in the set.
        non_public_experiment_uuids = []
        for experiment in experiments:
            self.assertNotEqual(
                experiment.share_level, ExperimentShareLevel.PUBLIC,
                'Public experiment should not be returned with exclude_public filter: %s' %
                experiment)
            non_public_experiment_uuids.append(experiment.uuid)
        self.assertIn(
            non_public_exp.uuid, non_public_experiment_uuids,
            'Non-public experiment not returned with exclude_public filter: %s' %
            non_public_exp)
        self.assertNotIn(
            public_exp.uuid, non_public_experiment_uuids,
            'Public experiment returned with exclude_public filter: %s' %
            public_exp)

    def test_experiments_with_public_only(self):
        """Tests retrieving experiments with public_only filter."""
        # Make sure that we have at least one public experiment and one non-public
        # experiment.
        public_exp = self._create_experiment(share_level=ExperimentShareLevel.PUBLIC)
        non_public_exp = self._create_experiment()

        experiments = self.provider.experiment.experiments(public_only=True)
        public_experiment_uuids = []
        for experiment in experiments:
            self.assertEqual(
                experiment.share_level, ExperimentShareLevel.PUBLIC,
                'Only public experiments should be returned with public_only filter: %s' %
                experiment)
            public_experiment_uuids.append(experiment.uuid)
        self.assertIn(
            public_exp.uuid, public_experiment_uuids,
            'Public experiment not returned with public_only filter: %s' %
            public_exp)
        self.assertNotIn(
            non_public_exp.uuid, public_experiment_uuids,
            'Non-public experiment returned with public_only filter: %s' %
            non_public_exp)

    def test_experiments_with_public_filters_error(self):
        """Tests that exclude_public and public_only cannot both be True."""
        with self.assertRaisesRegex(
                ValueError,
                'exclude_public and public_only cannot both be True'):
            self.provider.experiment.experiments(exclude_public=True, public_only=True)

    def test_experiments_with_exclude_mine(self):
        """Tests retrieving experiments with exclude_mine filter."""
        # Note that we cannot specify the owner when creating the experiment, the value comes
        # from the user profile via the token so we would have to use different test accounts
        # to explicitly create separately-owned epxeriments. We should be able to assume that
        # there is at least one experiment owned by another user in the integration test
        # environment though.
        my_exp = self._create_experiment()
        not_my_experiments = self.provider.experiment.experiments(exclude_mine=True)
        # The experiment we just created should not be in the set.
        not_mine_experiment_uuids = []
        for experiment in not_my_experiments:
            self.assertNotEqual(
                experiment.owner, my_exp.owner,  # pylint: disable=no-member
                'My experiment should not be returned with exclude_mine filter: %s' %
                experiment)
            not_mine_experiment_uuids.append(experiment.uuid)
        self.assertNotIn(
            my_exp.uuid, not_mine_experiment_uuids,
            'My experiment returned with exclude_mine filter: %s' %
            my_exp)

    def test_experiments_with_mine_only(self):
        """Tests retrieving experiments with mine_only filter."""
        # Note that we cannot specify the owner when creating the experiment, the value comes
        # from the user profile via the token so we would have to use different test accounts
        # to explicitly create separately-owned epxeriments. We should be able to assume that
        # there is at least one experiment owned by another user in the integration test
        # environment though.
        my_exp = self._create_experiment()
        my_experiments = self.provider.experiment.experiments(mine_only=True)
        my_experiment_uuids = []
        for experiment in my_experiments:
            self.assertEqual(
                experiment.owner, my_exp.owner,  # pylint: disable=no-member
                'Only my experiments should be returned with mine_only filter: %s' %
                experiment)
            my_experiment_uuids.append(experiment.uuid)
        self.assertIn(
            my_exp.uuid, my_experiment_uuids,
            'My experiment not returned with mine_only filter: %s' %
            my_exp)

    def test_experiments_with_owner_filters_error(self):
        """Tests that exclude_mine and mine_only cannot both be True."""
        with self.assertRaisesRegex(
                ValueError,
                'exclude_mine and mine_only cannot both be True'):
            self.provider.experiment.experiments(exclude_mine=True, mine_only=True)

    def test_retrieve_experiment(self):
        """Test retrieving an experiment by its ID."""
        exp = self.experiments[0]
        rexp = self.provider.experiment.retrieve_experiment(exp.uuid)
        self.assertEqual(exp.uuid, rexp.uuid)
        for attr in ['hub', 'group', 'project', 'owner', 'share_level']:
            self.assertIsNotNone(getattr(rexp, attr), "{} does not have a {}".format(rexp, attr))

    def test_upload_experiment(self):
        """Test uploading an experiment."""
        exp = self.experiments[0]
        new_exp = Experiment(
            provider=self.provider,
            backend_name=exp.backend_name,
            experiment_type='test',
            tags=['qiskit-test']
        )
        self.provider.experiment.upload_experiment(new_exp)
        self.experiments_to_delete.append(new_exp.uuid)
        credentials = self.provider.credentials
        self.assertEqual(credentials.hub, new_exp.hub)  # pylint: disable=no-member
        self.assertEqual(credentials.group, new_exp.group)  # pylint: disable=no-member
        self.assertEqual(credentials.project, new_exp.project)  # pylint: disable=no-member
        self.assertTrue(new_exp.uuid)
        self.assertTrue(new_exp.creation_datetime)
        self.assertEqual(ExperimentShareLevel.PRIVATE, new_exp.share_level)
        self.assertIsNotNone(new_exp.owner, 'Owner should be set')  # pylint: disable=no-member
        self.assertIsNone(new_exp.notes)
        for dt_attr in ['start_datetime', 'creation_datetime', 'end_datetime', 'updated_datetime']:
            if getattr(exp, dt_attr):
                self.assertTrue(getattr(exp, dt_attr).tzinfo)

    def test_update_experiment(self):
        """Test updating an experiment."""
        new_exp = self._create_experiment(notes='test note')
        new_exp.end_datetime = datetime.now()
        new_exp.share_level = ExperimentShareLevel.PROJECT
        new_exp.notes = ''  # Clear the notes
        self.provider.experiment.update_experiment(new_exp)
        rexp = self.provider.experiment.retrieve_experiment(new_exp.uuid)
        self.assertEqual(new_exp.end_datetime, rexp.end_datetime)
        self.assertEqual(ExperimentShareLevel.PROJECT, rexp.share_level)
        self.assertIsNone(rexp.notes)

    def test_delete_experiment(self):
        """Test deleting an experiment."""
        new_exp = self._create_experiment(notes='delete me')

        with mock.patch('builtins.input', lambda _: 'y'):
            deleted_exp = self.provider.experiment.delete_experiment(new_exp.uuid)
        self.assertEqual(deleted_exp.uuid, new_exp.uuid)
        self.assertEqual('delete me', new_exp.notes)

        with self.assertRaises(ExperimentNotFoundError) as ex_cm:
            self.provider.experiment.retrieve_experiment(new_exp.uuid)
        self.assertIn("Not Found for url", ex_cm.exception.message)

    def test_reference_experiment_analysis_results(self):
        """Test referencing analysis results in an experiment."""
        ref_result = self.provider.experiment.analysis_results()[0]
        experiment = self.provider.experiment.retrieve_experiment(ref_result.experiment_uuid)
        for result in experiment.analysis_results:
            self.assertEqual(result.experiment_uuid, ref_result.experiment_uuid)

    def test_get_analysis_results(self):
        """Test retrieving all analysis results."""
        results = self.provider.experiment.analysis_results()
        for res in results:
            self.assertTrue(isinstance(res, AnalysisResult))
            self.assertIsInstance(res.verified, bool)
            self.assertIsInstance(res.fit, dict)
            self.assertTrue(res.uuid, "{} does not have an uuid!".format(res))
            for dt_attr in ['creation_datetime', 'updated_datetime']:
                if getattr(res, dt_attr):
                    self.assertTrue(getattr(res, dt_attr).tzinfo)

    def test_upload_analysis_result(self):
        """Test uploading an analysis result."""
        ref_result = self.provider.experiment.analysis_results()[0]
        device_comp = self.device_components[0]
        new_experiment = self._create_experiment(device_comp.backend_name)
        new_result = AnalysisResult(experiment_uuid=new_experiment.uuid,
                                    fit=ref_result.fit,
                                    result_type=ref_result.type,
                                    device_components=[device_comp.type],
                                    quality='No Information',
                                    tags=['qiskit-test'],
                                    chisq=ref_result.chisq)
        self.provider.experiment.upload_analysis_result(new_result)
        self.results_to_delete.append(new_result.uuid)

        rresult = self.provider.experiment.retrieve_analysis_result(new_result.uuid)
        sub_tests = [(new_result, 'local result'), (rresult, 'retrieved result')]
        self.log.debug("Verifying analysis result %s", new_result.uuid)
        for res, name in sub_tests:
            with self.subTest(sub_test_name=name):
                self.assertIsNotNone(res.uuid)
                self.assertTrue(res.creation_datetime.tzinfo)
                self.assertEqual(res.experiment_uuid, new_experiment.uuid)
                self.assertEqual(res.fit, ref_result.fit)
                self.assertEqual(res.type, ref_result.type)
                self.assertEqual(res.device_components, [device_comp.type])
                self.assertEqual(res.quality.value, 'No Information')
                self.assertEqual(res.tags, ['qiskit-test'])
                self.assertFalse(res.verified)

    def test_update_analysis_result(self):
        """Test updating an analysis result."""
        new_result = self._create_analysis_result()
        original_type = new_result.type
        new_result.quality = ResultQuality.BAD  # pylint: disable=no-member
        new_result.verified = True
        new_fit = dict(
            value=new_result.fit['value']*2,
            variance=new_result.fit['variance']*2
        )
        new_result.fit = new_fit
        self.provider.experiment.update_analysis_result(new_result)

        rresult = self.provider.experiment.retrieve_analysis_result(new_result.uuid)
        sub_tests = [(new_result, 'local result'), (rresult, 'retrieved result')]
        for res, name in sub_tests:
            with self.subTest(sub_test_name=name):
                self.assertEqual(res.fit, new_fit)
                self.assertEqual(res.type, original_type)
                self.assertEqual(res.quality, ResultQuality.BAD)  # pylint: disable=no-member
                self.assertTrue(res.updated_datetime.tzinfo)
                self.assertTrue(res.verified)

    def test_results_experiments_device_components(self):
        """Test filtering analysis results and experiments with device components."""
        results = self.provider.experiment.analysis_results()
        sub_tests = []
        ref_result = None
        for res in results:
            if len(res.device_components) >= 2:
                ref_result = res
                sub_tests.append((ref_result.device_components[:1], False))
                break
        if not ref_result:
            ref_result = results[0]
        sub_tests.append((ref_result.device_components, True))

        for comp in self.device_components:
            if comp not in ref_result.device_components:
                sub_tests.append(([comp], False))
                break

        for dev_comp, found in sub_tests:
            with self.subTest(dev_comp=dev_comp):
                f_results = self.provider.experiment.analysis_results(
                    device_components=dev_comp, limit=None)
                self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
                                 "Analysis result {} with device component {} (not)found "
                                 "unexpectedly when filter using device component={}. "
                                 "Found={}.".format(ref_result.uuid, ref_result.device_components,
                                                    dev_comp, found))
                for result in f_results[:5]:    # Use a subset to reduce run time.
                    self.assertEqual(result.device_components, dev_comp,
                                     "Analysis result {} with device component {} "
                                     "does not match {}.".format(
                                         result.uuid, result.device_components, dev_comp))

                f_experiments = self.provider.experiment.experiments(
                    device_components=dev_comp, limit=None)
                for exp in f_experiments[:5]:
                    found = False
                    result_dev_comp = []
                    for result in exp.analysis_results:
                        if result.device_components == dev_comp:
                            found = True
                            break
                        result_dev_comp.append(result.device_components)
                    self.assertTrue(
                        found, "Device components {} not found in analysis result for experiment "
                               "{}. Only {} found.".format(dev_comp, exp.uuid, result_dev_comp))

    def test_analysis_results_experiment_uuid(self):
        """Test filtering analysis results with experiment uuid."""
        ref_result = self.provider.experiment.analysis_results()[0]
        sub_tests = [(ref_result.experiment_uuid, True)]
        for expr in self.experiments:
            if expr.uuid != ref_result.experiment_uuid:
                sub_tests.append((expr.uuid, False))
                break

        for expr_uuid, found in sub_tests:
            with self.subTest(expr_uuid=expr_uuid):
                f_results = self.provider.experiment.analysis_results(
                    experiment_id=expr_uuid, limit=None)
                self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
                                 "Analysis result {} with experiment uuid {} (not)found "
                                 "unexpectedly when filter using experiment uuid={}. "
                                 "Found={}.".format(ref_result.uuid, ref_result.experiment_uuid,
                                                    expr_uuid, found))
                for result in f_results:
                    self.assertEqual(result.experiment_uuid, expr_uuid,
                                     "Analysis result {} with experiment uuid {} does not "
                                     "match {}.".format(result.uuid, result.experiment_uuid,
                                                        expr_uuid))

    def test_analysis_results_type(self):
        """Test filtering analysis results with type."""
        all_results = self.provider.experiment.analysis_results()
        ref_result = all_results[0]
        sub_tests = [(ref_result.type, True)]
        for res in all_results:
            if res.type != ref_result.type:
                sub_tests.append((res.type, False))
                break

        for res_type, found in sub_tests:
            with self.subTest(res_type=res_type):
                f_results = self.provider.experiment.analysis_results(
                    result_type=res_type, limit=None)
                self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
                                 "Analysis result {} with type {} (not)found unexpectedly "
                                 "when filter using type={}. Found={}.".format(
                                     ref_result.uuid, ref_result.type, res_type, found))
                for result in f_results:
                    self.assertEqual(result.type, res_type,
                                     "Analysis result {} with type {} does not match {}.".format(
                                         result.uuid, result.type, res_type))

    def test_analysis_results_quality(self):
        """Test filtering analysis results with quality."""
        all_results = self.provider.experiment.analysis_results()
        ref_result = all_results[0]
        # Find a result whose quality is in the middle.
        bad_good = [ResultQuality.BAD, ResultQuality.GOOD]  # pylint: disable=no-member
        for result in all_results:
            if result.quality not in bad_good:
                ref_result = result
                break

        sub_tests = [([('eq', ref_result.quality)], True)]
        higher = lower = None
        for quality in ResultQuality:
            if quality > ref_result.quality and not higher:
                higher = quality
                sub_tests.extend([
                    ([('lt', quality)], True),
                    ([('le', quality)], True),
                    ([('gt', quality)], False),
                    ([('ge', quality)], False),
                ])
            elif quality < ref_result.quality and not lower:
                lower = quality
                sub_tests.extend([
                    ([('lt', quality)], False),
                    ([('le', quality)], False),
                    ([('gt', quality)], True),
                    ([('ge', quality)], True),
                ])
        if higher and lower:
            sub_tests.append(([('gt', lower), ('lt', higher)], True))

        operator_table = {'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>=', 'eq': '=='}

        for quality, found in sub_tests:
            with self.subTest(quality=quality):
                f_results = self.provider.experiment.analysis_results(quality=quality, limit=None)
                self.assertEqual(ref_result.uuid in [res.uuid for res in f_results], found,
                                 "Analysis result {} with quality {} (not)found unexpectedly "
                                 "when filter using quality={}. Found={}.".format(
                                     ref_result.uuid, ref_result.quality, quality, found))
                for result in f_results:
                    for qual in quality:
                        self.assertTrue(
                            eval("result.quality {} qual[1]".format(  # pylint: disable=eval-used
                                operator_table[qual[0]])),
                            "Analysis result {} with quality {} does not match {}.".format(
                                result.uuid, result.quality, quality))

    def test_delete_analysis_result(self):
        """Test deleting an analysis result."""
        result = self._create_analysis_result()
        with mock.patch('builtins.input', lambda _: 'y'):
            self.provider.experiment.delete_analysis_result(result.uuid)

        with self.assertRaises(AnalysisResultNotFoundError):
            self.provider.experiment.retrieve_analysis_result(result.uuid)

    def test_backend_components(self):
        """Test retrieving all device components."""
        self.assertTrue(self.device_components)
        self.assertTrue(all(isinstance(comp, DeviceComponent) for comp in self.device_components))

    def test_backend_components_backend_name(self):
        """Test retrieving device components for a specific backend."""
        ref_comp = self.device_components[0]
        components = self.provider.experiment.device_components(
            backend_name=ref_comp.backend_name)
        self.assertTrue(all(comp.backend_name == ref_comp.backend_name for comp in components))
        self.assertIn(ref_comp.uuid, [comp.uuid for comp in components])

    def test_retrieve_backends(self):
        """Test retrieving all backends."""
        backends = self.provider.experiment.backends()
        backend_names = [b['name'] for b in backends]
        self.assertIn(self.experiments[0].backend_name, backend_names)

    def test_plot(self):
        """Test uploading and retrieving a plot file."""
        new_exp = self._create_experiment()
        # Upload a new plot.
        hello_bytes = str.encode("hello world")
        file_name = "hello_world.svg"
        plot_name = "hello.svg"
        with open(file_name, 'wb') as file:
            file.write(hello_bytes)
        self.addCleanup(os.remove, file_name)
        response = self.provider.experiment.upload_plot(new_exp.uuid, file_name, plot_name)
        self.assertEqual(response['name'], plot_name)
        new_exp.refresh()
        self.assertIn(plot_name, new_exp.plot_names)

        # Retrieve the plot we just uploaded.
        plot_content = self.provider.experiment.retrieve_plot(new_exp.uuid, plot_name)
        self.assertEqual(plot_content, hello_bytes)

        # Delete plot.
        with mock.patch('builtins.input', lambda _: 'y'):
            self.provider.experiment.delete_plot(new_exp.uuid, plot_name)
        with self.assertRaises(PlotNotFoundError) as manager:
            self.provider.experiment.retrieve_plot(new_exp.uuid, plot_name)
        self.assertIn("not found", manager.exception.message)

    def test_upload_update_plot_data(self):
        """Test uploading and updating plot data."""
        new_exp = self._create_experiment()
        # Upload a new plot.
        plot_name = "batman.svg"
        hello_bytes = str.encode("hello world")
        plot_names = [plot_name, None]
        for name in plot_names:
            with self.subTest(name=name):
                response = self.provider.experiment.upload_plot(new_exp.uuid, hello_bytes, name)
                if name:
                    self.assertEqual(response['name'], name)
                else:
                    name = response['name']
                new_exp.refresh()
                self.assertIn(name, new_exp.plot_names)

        # Update the plot we just uploaded.
        friend_bytes = str.encode("hello friend!")
        response = self.provider.experiment.update_plot(new_exp.uuid, friend_bytes, plot_name)
        self.assertEqual(response['name'], plot_name)
        rplot = self.provider.experiment.retrieve_plot(new_exp.uuid, plot_name)
        self.assertEqual(rplot, friend_bytes, "Retrieved plot not equal updated plot.")

    def test_experiments_limit(self):
        """Test getting experiments with a limit."""
        limits = [10, 1000, 1001]

        for limit in limits:
            with self.subTest(limit=limit):
                experiments = self.provider.experiment.experiments(limit=limit)
                self.assertEqual(len(experiments), limit)
                self.assertEqual(len({expr.uuid for expr in experiments}), len(experiments))

        with self.assertRaises(ValueError) as context_manager:
            self.provider.experiment.experiments(limit=-1)
        self.assertIn("limit", str(context_manager.exception))

    def test_analysis_results_limit(self):
        """Test getting analysis results with a limit."""
        limits = [10, 1000, 1001]
        for limit in limits:
            with self.subTest(limit=limit):
                results = self.provider.experiment.analysis_results(limit=limit)
                self.assertEqual(len(results), limit)
                self.assertEqual(len({res.uuid for res in results}), len(results))

        with self.assertRaises(ValueError) as context_manager:
            self.provider.experiment.analysis_results(limit=-1)
        self.assertIn("limit", str(context_manager.exception))

    def _create_experiment(
            self,
            backend_name: Optional[str] = None,
            start_dt: Optional[datetime] = None,
            share_level: Optional[Union[ExperimentShareLevel, str]] = None,
            notes: Optional[str] = None
    ) -> Experiment:
        backend_name = backend_name or self.experiments[0].backend_name
        new_exp = Experiment(  # pylint: disable=unexpected-keyword-arg
            provider=self.provider,
            backend_name=backend_name,
            experiment_type='test',
            tags=['qiskit-test'],
            start_datetime=start_dt,
            share_level=share_level,
            notes=notes
        )
        self.provider.experiment.upload_experiment(new_exp)
        self.experiments_to_delete.append(new_exp.uuid)
        return new_exp

    def _create_analysis_result(self):
        device_comp = self.device_components[0]
        new_experiment = self._create_experiment(device_comp.backend_name)
        fit = dict(value=41.456, variance=4.051)
        new_result = AnalysisResult(experiment_uuid=new_experiment.uuid,
                                    fit=fit,
                                    result_type="T1",
                                    device_components=[device_comp.type],
                                    tags=['qiskit-test'])
        self.provider.experiment.upload_analysis_result(new_result)
        self.results_to_delete.append(new_result.uuid)
        return new_result
