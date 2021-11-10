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

"""Experiment integration test with server."""

import os
import uuid
from unittest import mock, SkipTest, skipIf
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import re

from dateutil import tz
import numpy as np

from qiskit.providers.ibmq.experiment.constants import ExperimentShareLevel
from qiskit.providers.ibmq.exceptions import IBMQNotAuthorizedError
from qiskit.providers.ibmq.experiment import (ResultQuality,
                                              IBMExperimentEntryNotFound)

from ...ibmqtestcase import IBMQTestCase
from ...decorators import requires_provider, requires_device
from .utils import ExperimentEncoder, ExperimentDecoder


@skipIf(not os.environ.get('USE_STAGING_CREDENTIALS', ''), "Only runs on staging")
class TestExperimentServerIntegration(IBMQTestCase):
    """Test experiment modules."""

    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = cls._setup_provider()  # pylint: disable=no-value-for-parameter
        cls.backend = cls._setup_backend()  # pylint: disable=no-value-for-parameter
        try:
            cls.device_components = cls.provider.experiment.device_components(cls.backend.name())
        except Exception:
            raise SkipTest("Not authorized to use experiment service.")

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

    def tearDown(self):
        """Test level tear down."""
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
        exp_id = self._create_experiment()
        experiments = self.provider.experiment.experiments()
        self.assertTrue(experiments, "No experiments found.")

        found = False
        for exp in experiments:
            self.assertTrue(exp["experiment_id"], "{} does not have an ID!".format(exp))
            for dt_attr in ['start_datetime', 'creation_datetime',
                            'end_datetime', 'updated_datetime']:
                if getattr(exp, dt_attr, None):
                    self.assertTrue(getattr(exp, dt_attr).tzinfo)
            if exp["experiment_id"] == exp_id:
                found = True
        self.assertTrue(found, f"Experiment {exp_id} not found!")

    def test_experiments_with_backend(self):
        """Test retrieving all experiments for a specific backend."""
        exp_id = self._create_experiment()
        backend_experiments = self.provider.experiment.experiments(
            backend_name=self.backend.name())

        found = False
        for exp in backend_experiments:
            self.assertEqual(self.backend.name(), exp["backend"].name())
            if exp["experiment_id"] == exp_id:
                found = True
        self.assertTrue(found, "Experiment {} not found when filter by backend name {}.".format(
            exp_id, self.backend.name()))

    def test_experiments_with_type(self):
        """Test retrieving all experiments for a specific type."""
        exp_type = 'qiskit_test'
        exp_id = self._create_experiment(experiment_type=exp_type)
        backend_experiments = self.provider.experiment.experiments(
            experiment_type=exp_type)

        found = False
        for exp in backend_experiments:
            self.assertEqual(exp_type, exp["experiment_type"])
            if exp["experiment_id"] == exp_id:
                found = True
        self.assertTrue(found, "Experiment {} not found when filter by type {}.".format(
            exp_id, exp_type))

    def test_experiments_with_parent_id(self):
        """Test retrieving all experiments for a specific parent id."""
        parent_id = self._create_experiment()
        child_id = self._create_experiment(parent_id=parent_id)
        experiments = self.provider.experiment.experiments(
            parent_id=parent_id)

        found = False
        for exp in experiments:
            self.assertEqual(parent_id, exp["parent_id"])
            if exp["experiment_id"] == child_id:
                found = True
        self.assertTrue(found, "Experiment {} not found when filter by type {}.".format(
            child_id, parent_id))

    def test_experiments_with_type_operator(self):
        """Test retrieving all experiments for a specific type with operator."""
        exp_type = 'qiskit_test'
        exp_id = self._create_experiment(experiment_type=exp_type)

        experiments = self.provider.experiment.experiments(
            experiment_type="foo", experiment_type_operator="like")
        self.assertNotIn(exp_id, [exp["experiment_id"] for exp in experiments])

        subtests = ["qiskit", "test"]
        for filter_type in subtests:
            with self.subTest(filter_type=filter_type):
                experiments = self.provider.experiment.experiments(
                    experiment_type=exp_type, experiment_type_operator="like")
                found = False
                for exp in experiments:
                    self.assertTrue(re.match(f".*{filter_type}.*", exp["experiment_type"]))
                    if exp["experiment_id"] == exp_id:
                        found = True
                self.assertTrue(found, f"Experiment {exp_id} not found "
                                       f"when filter by type {filter_type}")

    def test_experiments_with_bad_type_operator(self):
        """Test retrieving all experiments with a bad type operator."""
        with self.assertRaises(ValueError):
            self.provider.experiment.experiments(
                experiment_type="foo", experiment_type_operator="bad")

    def test_experiments_with_start_time(self):
        """Test retrieving an experiment by its start_time."""
        ref_start_dt = datetime.now() - timedelta(days=1)
        ref_start_dt = ref_start_dt.replace(tzinfo=tz.tzlocal())
        exp_id = self._create_experiment(start_datetime=ref_start_dt)

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
                    start_datetime_after=start_dt, start_datetime_before=end_dt,
                    experiment_type='qiskit_test')
                found = False
                for exp in backend_experiments:
                    if start_dt:
                        self.assertGreaterEqual(exp["start_datetime"], start_dt)
                    if end_dt:
                        self.assertLessEqual(exp["start_datetime"], end_dt)
                    if exp["experiment_id"] == exp_id:
                        found = True
                self.assertEqual(found, expected,
                                 "Experiment {} (not)found unexpectedly when filter using"
                                 "start_dt={}, end_dt={}. Found={}".format(
                                     exp_id, start_dt, end_dt, found))

    def test_experiments_with_tags(self):
        """Test filtering experiments using tags."""
        ref_tags = ["qiskit_test", "foo"]
        exp_id = self._create_experiment(tags=ref_tags)

        phantom_tag = uuid.uuid4().hex
        sub_tests = [
            (ref_tags, 'AND', True),
            (ref_tags, 'OR', True),
            (ref_tags[:1], "OR", True),
            (ref_tags + [phantom_tag], "AND", False),
            (ref_tags + [phantom_tag], "OR", True),
            ([phantom_tag], "OR", False)
        ]
        for tags, operator, found in sub_tests:
            with self.subTest(tags=tags, operator=operator):
                experiments = self.provider.experiment.experiments(
                    tags=tags, tags_operator=operator)
                ref_expr_found = False
                for expr in experiments:
                    msg = "Tags {} not fond in experiment tags {}".format(tags, expr["tags"])
                    if operator == 'AND':
                        self.assertTrue(all(f_tag in expr["tags"] for f_tag in tags), msg)
                    else:
                        self.assertTrue(any(f_tag in expr["tags"] for f_tag in tags), msg)
                    if expr["experiment_id"] == exp_id:
                        ref_expr_found = True
                self.assertTrue(ref_expr_found == found,
                                "Experiment tags {} unexpectedly (not)found. Found={}".format(
                                    ref_tags, found))

    def test_experiments_with_hgp(self):
        """Test retrieving all experiments for a specific h/g/p."""
        exp_id = self._create_experiment()
        credentials = self.provider.credentials
        hgp = [credentials.hub, credentials.group, credentials.project]
        sub_tests = [
            {'hub': hgp[0]},
            {'hub': hgp[0], 'group': hgp[1]},
            {'hub': hgp[0], 'group': hgp[1], 'project': hgp[2]}
        ]

        for hgp_kwargs in sub_tests:
            with self.subTest(kwargs=hgp_kwargs.keys()):
                hgp_experiments = self.provider.experiment.experiments(**hgp_kwargs)
                ref_expr_found = False
                for expr in hgp_experiments:
                    for hgp_key, hgp_val in hgp_kwargs.items():
                        self.assertEqual(expr[hgp_key], hgp_val)
                    if expr["experiment_id"] == exp_id:
                        ref_expr_found = True
                self.assertTrue(ref_expr_found)

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
        public_exp_id = self._create_experiment(share_level=ExperimentShareLevel.PUBLIC)
        private_exp_id = self._create_experiment(share_level=ExperimentShareLevel.PRIVATE)

        experiments = self.provider.experiment.experiments(exclude_public=True)
        # The public experiment we just created should not be in the set.
        non_public_experiment_uuids = []
        for experiment in experiments:
            self.assertNotEqual(
                experiment["share_level"], ExperimentShareLevel.PUBLIC.value,
                'Public experiment should not be returned with exclude_public filter: %s' %
                experiment)
            non_public_experiment_uuids.append(experiment["experiment_id"])
        self.assertIn(
            private_exp_id, non_public_experiment_uuids,
            'Non-public experiment not returned with exclude_public filter: %s' %
            private_exp_id)
        self.assertNotIn(
            public_exp_id, non_public_experiment_uuids,
            'Public experiment returned with exclude_public filter: %s' %
            public_exp_id)

    def test_experiments_with_public_only(self):
        """Tests retrieving experiments with public_only filter."""
        # Make sure that we have at least one public experiment and one non-public
        # experiment.
        public_exp_id = self._create_experiment(share_level=ExperimentShareLevel.PUBLIC)
        private_exp_id = self._create_experiment(share_level=ExperimentShareLevel.PRIVATE)

        experiments = self.provider.experiment.experiments(public_only=True)
        public_experiment_uuids = []
        for experiment in experiments:
            self.assertEqual(
                experiment["share_level"], ExperimentShareLevel.PUBLIC.value,
                'Only public experiments should be returned with public_only filter: %s' %
                experiment)
            public_experiment_uuids.append(experiment["experiment_id"])
        self.assertIn(
            public_exp_id, public_experiment_uuids,
            'Public experiment not returned with public_only filter: %s' %
            public_exp_id)
        self.assertNotIn(
            private_exp_id, public_experiment_uuids,
            'Non-public experiment returned with public_only filter: %s' %
            private_exp_id)

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
        # to explicitly create separately-owned experiments. We should be able to assume that
        # there is at least one experiment owned by another user in the integration test
        # environment though.
        exp_id = self._create_experiment()
        exp_owner = self.provider.experiment.experiment(exp_id)["owner"]

        not_my_experiments = self.provider.experiment.experiments(exclude_mine=True)
        # The experiment we just created should not be in the set.
        not_mine_experiment_uuids = []
        for experiment in not_my_experiments:
            self.assertNotEqual(
                experiment["owner"], exp_owner,  # pylint: disable=no-member
                'My experiment should not be returned with exclude_mine filter: %s' %
                experiment["experiment_id"])
            not_mine_experiment_uuids.append(experiment["experiment_id"])
        self.assertNotIn(
            exp_id, not_mine_experiment_uuids,
            'My experiment returned with exclude_mine filter: %s' %
            exp_id)

    def test_experiments_with_mine_only(self):
        """Tests retrieving experiments with mine_only filter."""
        # Note that we cannot specify the owner when creating the experiment, the value comes
        # from the user profile via the token so we would have to use different test accounts
        # to explicitly create separately-owned epxeriments. We should be able to assume that
        # there is at least one experiment owned by another user in the integration test
        # environment though.
        exp_id = self._create_experiment()
        exp_owner = self.provider.experiment.experiment(exp_id)["owner"]
        my_experiments = self.provider.experiment.experiments(mine_only=True)
        my_experiment_uuids = []
        for experiment in my_experiments:
            self.assertEqual(
                experiment["owner"], exp_owner,  # pylint: disable=no-member
                'Only my experiments should be returned with mine_only filter: %s' %
                experiment["experiment_id"])
            my_experiment_uuids.append(experiment["experiment_id"])
        self.assertIn(
            exp_id, my_experiment_uuids,
            'My experiment not returned with mine_only filter: %s' %
            exp_id)

    def test_experiments_with_owner_filters_error(self):
        """Tests that exclude_mine and mine_only cannot both be True."""
        with self.assertRaisesRegex(
                ValueError,
                'exclude_mine and mine_only cannot both be True'):
            self.provider.experiment.experiments(exclude_mine=True, mine_only=True)

    def test_experiments_with_limit(self):
        """Test retrieving experiments with limit."""
        self._create_experiment()
        experiments = self.provider.experiment.experiments(limit=1)
        self.assertEqual(1, len(experiments))

    def test_experiments_with_no_limit(self):
        """Test retrieving experiments with no limit."""
        tags = [str(uuid.uuid4())]
        exp_id = self._create_experiment(tags=tags)
        experiments = self.provider.experiment.experiments(limit=None, tags=tags)
        self.assertEqual(1, len(experiments))
        self.assertEqual(exp_id, experiments[0]["experiment_id"])

    def test_experiments_with_sort_by(self):
        """Test retrieving experiments with sort_by."""
        tags = [str(uuid.uuid4())]
        exp1 = self._create_experiment(tags=tags,
                                       experiment_type="qiskit_test1",
                                       start_datetime=datetime.now()-timedelta(hours=1))
        exp2 = self._create_experiment(tags=tags,
                                       experiment_type="qiskit_test2",
                                       start_datetime=datetime.now())
        exp3 = self._create_experiment(tags=tags,
                                       experiment_type="qiskit_test1",
                                       start_datetime=datetime.now()-timedelta(hours=2))

        subtests = [
            (["experiment_type:asc"], [exp1, exp3, exp2]),
            (["experiment_type:desc"], [exp2, exp1, exp3]),
            (["start_datetime:asc"], [exp3, exp1, exp2]),
            (["start_datetime:desc"], [exp2, exp1, exp3]),
            (["experiment_type:asc", "start_datetime:asc"], [exp3, exp1, exp2]),
            (["experiment_type:asc", "start_datetime:desc"], [exp1, exp3, exp2]),
            (["experiment_type:desc", "start_datetime:asc"], [exp2, exp3, exp1]),
            (["experiment_type:desc", "start_datetime:desc"], [exp2, exp1, exp3]),
        ]

        for sort_by, expected in subtests:
            with self.subTest(sort_by=sort_by):
                experiments = self.provider.experiment.experiments(tags=tags, sort_by=sort_by)
                self.assertEqual(expected, [exp["experiment_id"] for exp in experiments])

    def test_experiments_with_bad_sort_by(self):
        """Test retrieving experiments with bad sort_by."""
        subtests = ["experiment_id:asc", "experiment_type", "experiment_type:foo", "foo:bar"]

        for sort_by in subtests:
            with self.subTest(sort_by=sort_by):
                with self.assertRaises(ValueError):
                    self.provider.experiment.experiments(sort_by=sort_by)

    def test_experiments_with_device_components(self):
        """Test filtering experiments with device components."""
        expr_id = self._create_experiment()
        self._create_analysis_result(exp_id=expr_id,
                                     device_components=self.device_components)
        experiments = self.provider.experiment.experiments(
            device_components=self.device_components)
        self.assertIn(expr_id, [expr["experiment_id"] for expr in experiments],
                      f"Experiment {expr_id} not found when filtering with "
                      f"device components {self.device_components}")

    def test_experiments_with_device_components_operator(self):
        """Test filtering experiments with device components operator."""
        backend_name, device_components = self._find_backend_device_components(3)
        if not backend_name:
            self.skipTest("Need at least 3 device components.")

        expr_id = self._create_experiment(backend_name=backend_name)
        self._create_analysis_result(exp_id=expr_id,
                                     device_components=device_components)
        experiments = self.provider.experiment.experiments(
            device_components=device_components[:2],
            device_components_operator="contains")

        self.assertIn(expr_id, [expr["experiment_id"] for expr in experiments],
                      f"Experiment {expr_id} not found when filtering with "
                      f"device components {device_components[:2]}")

    def test_experiments_with_bad_components_operator(self):
        """Test filtering experiments with bad device components operator."""
        with self.assertRaises(ValueError):
            self.provider.experiment.experiments(
                device_components=["Q1"],
                device_components_operator="foo")

    def test_retrieve_experiment(self):
        """Test retrieving an experiment by its ID."""
        exp_id = self._create_experiment()
        rexp = self.provider.experiment.experiment(exp_id)
        self.assertEqual(exp_id, rexp["experiment_id"])
        for attr in ['hub', 'group', 'project', 'owner', 'share_level']:
            self.assertIsNotNone(rexp[attr], "{} does not have a {}".format(rexp, attr))

    def test_upload_experiment(self):
        """Test uploading an experiment."""
        exp_id = str(uuid.uuid4())
        new_exp_id = self.provider.experiment.create_experiment(
            experiment_type="qiskit_test",
            backend_name=self.backend.name(),
            metadata={"foo": "bar"},
            experiment_id=exp_id,
            job_ids=["job1", "job2"],
            tags=["qiskit_test"],
            notes="some notes",
            share_level=ExperimentShareLevel.PROJECT,
            start_datetime=datetime.now()
        )
        self.experiments_to_delete.append(new_exp_id)
        self.assertEqual(exp_id, new_exp_id)
        new_exp = self.provider.experiment.experiment(new_exp_id)

        credentials = self.provider.credentials
        self.assertEqual(credentials.hub, new_exp["hub"])  # pylint: disable=no-member
        self.assertEqual(credentials.group, new_exp["group"])  # pylint: disable=no-member
        self.assertEqual(credentials.project, new_exp["project"])  # pylint: disable=no-member
        self.assertEqual("qiskit_test", new_exp["experiment_type"])
        self.assertEqual(self.backend.name(), new_exp["backend"].name())
        self.assertEqual({"foo": "bar"}, new_exp["metadata"])
        self.assertEqual(["job1", "job2"], new_exp["job_ids"])
        self.assertEqual(["qiskit_test"], new_exp["tags"])
        self.assertEqual("some notes", new_exp["notes"])
        self.assertEqual(ExperimentShareLevel.PROJECT.value, new_exp["share_level"])
        self.assertTrue(new_exp["creation_datetime"])
        self.assertIsNotNone(new_exp["owner"], 'Owner should be set')  # pylint: disable=no-member

        for dt_attr in ['start_datetime', 'creation_datetime', 'end_datetime', 'updated_datetime']:
            if dt_attr in new_exp:
                self.assertTrue(new_exp[dt_attr].tzinfo)

    def test_update_experiment(self):
        """Test updating an experiment."""
        new_exp_id = self._create_experiment()

        self.provider.experiment.update_experiment(
            experiment_id=new_exp_id,
            metadata={"foo": "bar"},
            job_ids=["job1", "job2"],
            tags=["qiskit_test"],
            notes="some notes",
            share_level=ExperimentShareLevel.PROJECT,
            end_datetime=datetime.now()
        )

        rexp = self.provider.experiment.experiment(new_exp_id)
        self.assertEqual({"foo": "bar"}, rexp["metadata"])
        self.assertEqual(["job1", "job2"], rexp["job_ids"])
        self.assertEqual(["qiskit_test"], rexp["tags"])
        self.assertEqual("some notes", rexp["notes"])
        self.assertEqual(ExperimentShareLevel.PROJECT.value, rexp["share_level"])
        self.assertTrue(rexp["end_datetime"])

    def test_delete_experiment(self):
        """Test deleting an experiment."""
        new_exp_id = self._create_experiment(notes='delete me')

        with mock.patch('builtins.input', lambda _: 'y'):
            self.provider.experiment.delete_experiment(new_exp_id)

        with self.assertRaises(IBMExperimentEntryNotFound) as ex_cm:
            self.provider.experiment.experiment(new_exp_id)
        self.assertIn("Not Found for url", ex_cm.exception.message)

    def test_upload_analysis_result(self):
        """Test uploading an analysis result."""
        exp_id = self._create_experiment()
        fit = dict(value=41.456, variance=4.051)
        result_id = str(uuid.uuid4())
        chisq = 1.3253
        aresult_id = self.provider.experiment.create_analysis_result(
            experiment_id=exp_id,
            result_type="qiskit_test",
            result_data=fit,
            device_components=self.device_components,
            tags=["qiskit_test"],
            quality=ResultQuality.GOOD,
            verified=True,
            result_id=result_id,
            chisq=chisq
        )

        rresult = self.provider.experiment.analysis_result(aresult_id)
        self.assertEqual(exp_id, rresult["experiment_id"])
        self.assertEqual("qiskit_test", rresult["result_type"])
        self.assertEqual(fit, rresult["result_data"])
        self.assertEqual(self.device_components,
                         [str(comp) for comp in rresult["device_components"]])
        self.assertEqual(["qiskit_test"], rresult["tags"])
        self.assertEqual(ResultQuality.GOOD, rresult["quality"])
        self.assertTrue(rresult["verified"])
        self.assertEqual(result_id, rresult["result_id"])
        self.assertEqual(chisq, rresult["chisq"])

    def test_update_analysis_result(self):
        """Test updating an analysis result."""
        result_id = self._create_analysis_result()
        fit = dict(value=41.456, variance=4.051)
        chisq = 1.3253

        self.provider.experiment.update_analysis_result(
            result_id=result_id,
            result_data=fit,
            tags=["qiskit_test"],
            quality=ResultQuality.GOOD,
            verified=True,
            chisq=chisq
        )

        rresult = self.provider.experiment.analysis_result(result_id)
        self.assertEqual(result_id, rresult["result_id"])
        self.assertEqual(fit, rresult["result_data"])
        self.assertEqual(["qiskit_test"], rresult["tags"])
        self.assertEqual(ResultQuality.GOOD, rresult["quality"])
        self.assertTrue(rresult["verified"])
        self.assertEqual(chisq, rresult["chisq"])

    def test_analysis_results(self):
        """Test retrieving all analysis results."""
        result_id = self._create_analysis_result()
        results = self.provider.experiment.analysis_results()
        found = False
        for res in results:
            self.assertIsInstance(res["verified"], bool)
            self.assertIsInstance(res["result_data"], dict)
            self.assertTrue(res["result_id"], "{} does not have an uuid!".format(res))
            for dt_attr in ['creation_datetime', 'updated_datetime']:
                if dt_attr in res:
                    self.assertTrue(res[dt_attr].tzinfo)
            if res["result_id"] == result_id:
                found = True
        self.assertTrue(found)

    def test_analysis_results_device_components(self):
        """Test filtering analysis results with device components."""
        result_id = self._create_analysis_result(device_components=self.device_components)
        results = self.provider.experiment.analysis_results(
            device_components=self.device_components)

        found = False
        for res in results:
            self.assertEqual(self.device_components,
                             [str(comp) for comp in res["device_components"]])
            if res["result_id"] == result_id:
                found = True
        self.assertTrue(found, f"Result {result_id} not found when filtering by "
                               f"device components {self.device_components}")

    def test_analysis_results_device_components_operator(self):
        """Test filtering analysis results with device components operator."""
        backend_name, device_components = self._find_backend_device_components(3)
        if not backend_name:
            self.skipTest("Need at least 3 device components.")

        expr_id = self._create_experiment(backend_name=backend_name)
        result_id = self._create_analysis_result(exp_id=expr_id,
                                                 device_components=device_components)
        results = self.provider.experiment.analysis_results(
            device_components=device_components[:2], device_components_operator="contains")

        found = False
        for res in results:
            self.assertTrue(set(device_components[:2]) <=
                            {str(comp) for comp in res["device_components"]})
            if res["result_id"] == result_id:
                found = True
        self.assertTrue(found, f"Result {result_id} not found when filtering by "
                               f"device components {device_components[:2]}")

    def test_analysis_results_experiment_id(self):
        """Test filtering analysis results with experiment id."""
        expr_id = self._create_experiment()
        result_id1 = self._create_analysis_result(exp_id=expr_id)
        result_id2 = self._create_analysis_result(exp_id=expr_id)

        results = self.provider.experiment.analysis_results(experiment_id=expr_id)
        self.assertEqual(2, len(results))
        self.assertEqual({result_id1, result_id2}, {res["result_id"] for res in results})

    def test_analysis_results_type(self):
        """Test filtering analysis results with type."""
        result_type = "qiskit_test"
        result_id = self._create_analysis_result(result_type=result_type)
        results = self.provider.experiment.analysis_results(result_type=result_type)
        found = False
        for res in results:
            self.assertEqual(result_type, res["result_type"])
            if res["result_id"] == result_id:
                found = True
        self.assertTrue(found, f"Result {result_id} not returned when filtering by "
                               f"type {result_type}")

    def test_analysis_results_type_operator(self):
        """Test filtering analysis results with type operator."""
        result_type = "qiskit_test_1234"
        result_id = self._create_analysis_result(result_type=result_type)

        results = self.provider.experiment.analysis_results(
            result_type="foo", result_type_operator="like")
        self.assertNotIn(result_id, [res["result_id"] for res in results])

        subtests = ["qiskit_test", "test_1234"]
        for filter_type in subtests:
            with self.subTest(filter_type=filter_type):
                results = self.provider.experiment.analysis_results(
                    result_type=filter_type,
                    result_type_operator="like")

                found = False
                for res in results:
                    self.assertIn(filter_type, res["result_type"])
                    if res["result_id"] == result_id:
                        found = True
                self.assertTrue(found, f"Result {result_id} not returned when filtering by "
                                       f"type substring {filter_type}")

    def test_analysis_results_bad_type_operator(self):
        """Test retrieving all experiments with a bad type operator."""
        with self.assertRaises(ValueError):
            self.provider.experiment.analysis_results(
                result_type="foo", result_type_operator="bad")

    def test_analysis_results_quality(self):
        """Test filtering analysis results with quality."""
        expr_id = self._create_experiment()
        result_id1 = self._create_analysis_result(exp_id=expr_id, quality=ResultQuality.GOOD)
        result_id2 = self._create_analysis_result(exp_id=expr_id, quality=ResultQuality.BAD)
        result_id3 = self._create_analysis_result(exp_id=expr_id, quality=ResultQuality.UNKNOWN)

        subtests = [(ResultQuality.GOOD, {result_id1}),
                    (ResultQuality.BAD.value, {result_id2}),
                    ("unknown", {result_id3}),
                    ([ResultQuality.UNKNOWN], {result_id3}),
                    ([ResultQuality.GOOD, ResultQuality.UNKNOWN], {result_id1, result_id3}),
                    (["Good", "Bad"], {result_id1, result_id2}),
                    ([ResultQuality.UNKNOWN, ResultQuality.BAD], {result_id3, result_id2}),
                    ([ResultQuality.GOOD, ResultQuality.BAD, ResultQuality.UNKNOWN],
                     {result_id1, result_id2, result_id3})
                    ]

        for quality, expected in subtests:
            with self.subTest(quality=quality):
                results = self.provider.experiment.analysis_results(quality=quality)
                if not isinstance(quality, list):
                    quality = [quality]
                qual_set = []
                for qual in quality:
                    if isinstance(qual, str):
                        qual = ResultQuality(qual.upper())
                    qual_set.append(qual)
                res_ids = set()
                for res in results:
                    self.assertIn(res["quality"], qual_set)
                    res_ids.add(res["result_id"])
                self.assertTrue(expected <= res_ids,
                                f"Result {expected} not returned "
                                f"when filter with quality {quality}")

    def test_analysis_results_backend_name(self):
        """Test filtering analysis results with backend name."""
        result_id = self._create_analysis_result()
        results = self.provider.experiment.analysis_results(backend_name=self.backend.name())
        self.assertIn(result_id, [res["result_id"] for res in results])

    def test_analysis_results_verified(self):
        """Test filtering analysis results with verified."""
        result_id = self._create_analysis_result(verified=True)
        results = self.provider.experiment.analysis_results(verified=True)
        found = False
        for res in results:
            self.assertTrue(res["verified"])
            if res["result_id"] == result_id:
                found = True
        self.assertTrue(found, f"Result {result_id} not found when "
                               f"filtering with verified=True")

    def test_analysis_results_with_tags(self):
        """Test filtering analysis results using tags."""
        ref_tags = ["qiskit_test", "foo"]
        result_id = self._create_analysis_result(tags=ref_tags)

        phantom_tag = uuid.uuid4().hex
        sub_tests = [
            (ref_tags, 'AND', True),
            (ref_tags, 'OR', True),
            (ref_tags[:1], "OR", True),
            (ref_tags + [phantom_tag], "AND", False),
            (ref_tags + [phantom_tag], "OR", True),
            ([phantom_tag], "OR", False)
        ]
        for tags, operator, found in sub_tests:
            with self.subTest(tags=tags, operator=operator):
                results = self.provider.experiment.analysis_results(
                    tags=tags, tags_operator=operator)
                res_found = False
                for res in results:
                    msg = "Tags {} not fond in result tags {}".format(tags, res["tags"])
                    if operator == 'AND':
                        self.assertTrue(all(f_tag in res["tags"] for f_tag in tags), msg)
                    else:
                        self.assertTrue(any(f_tag in res["tags"] for f_tag in tags), msg)
                    if res["result_id"] == result_id:
                        res_found = True
                self.assertTrue(res_found == found,
                                "Result tags {} unexpectedly (not)found. Found={}".format(
                                    ref_tags, found))

    def test_analysis_results_with_limit(self):
        """Test retrieving analysis results with limit."""
        self._create_analysis_result()
        results = self.provider.experiment.analysis_results(limit=1)
        self.assertEqual(1, len(results))

    def test_analysis_results_with_no_limit(self):
        """Test retrieving analysis results with no limit."""
        tags = [str(uuid.uuid4())]
        result_id = self._create_analysis_result(tags=tags)
        results = self.provider.experiment.analysis_results(limit=None, tags=tags)
        self.assertEqual(1, len(results))
        self.assertEqual(result_id, results[0]["result_id"])

    def test_analysis_results_with_sort_by(self):
        """Test retrieving analysis results with sort_by."""
        tags = [str(uuid.uuid4())]
        backend, components = self._find_backend_device_components(3)
        backend_name = backend or self.backend.name()
        device_components = components or self.device_components
        if len(device_components) < 3:
            device_components = [None]*3  # Skip testing device components.
        device_components.sort()
        expr_id = self._create_experiment(backend_name=backend_name)

        res1 = self._create_analysis_result(exp_id=expr_id, tags=tags,
                                            result_type="qiskit_test1",
                                            device_components=device_components[2])
        res2 = self._create_analysis_result(exp_id=expr_id, tags=tags,
                                            result_type="qiskit_test2",
                                            device_components=device_components[0])
        res3 = self._create_analysis_result(exp_id=expr_id, tags=tags,
                                            result_type="qiskit_test1",
                                            device_components=device_components[1])

        subtests = [
            (["result_type:asc"], [res3, res1, res2]),
            (["result_type:desc"], [res2, res3, res1]),
            (["creation_datetime:asc"], [res1, res2, res3]),
            (["creation_datetime:desc"], [res3, res2, res1]),
            (["result_type:asc", "creation_datetime:asc"], [res1, res3, res2]),
            (["result_type:asc", "creation_datetime:desc"], [res3, res1, res2]),
            (["result_type:desc", "creation_datetime:asc"], [res2, res1, res3]),
            (["result_type:desc", "creation_datetime:desc"], [res2, res3, res1]),
        ]
        if device_components[0]:
            subtests += [
                (["device_components:asc"], [res2, res3, res1]),
                (["device_components:desc"], [res1, res3, res2]),
                (["result_type:asc", "device_components:desc"], [res1, res3, res2])
            ]

        for sort_by, expected in subtests:
            with self.subTest(sort_by=sort_by):
                results = self.provider.experiment.analysis_results(tags=tags, sort_by=sort_by)
                self.assertEqual(expected, [res["result_id"] for res in results])

    def test_analysis_results_with_bad_sort_by(self):
        """Test retrieving analysis results with bad sort_by."""
        subtests = ["result_id:asc", "result_type", "result_type:foo", "foo:bar"]

        for sort_by in subtests:
            with self.subTest(sort_by=sort_by):
                with self.assertRaises(ValueError):
                    self.provider.experiment.analysis_results(sort_by=sort_by)

    def test_delete_analysis_result(self):
        """Test deleting an analysis result."""
        result_id = self._create_analysis_result()
        with mock.patch('builtins.input', lambda _: 'y'):
            self.provider.experiment.delete_analysis_result(result_id)

        with self.assertRaises(IBMExperimentEntryNotFound):
            self.provider.experiment.analysis_result(result_id)

    def test_backend_components(self):
        """Test retrieving all device components."""
        device_components = self.provider.experiment.device_components()
        self.assertTrue(device_components)

    def test_backend_components_backend_name(self):
        """Test retrieving device components for a specific backend."""
        device_components = self.provider.experiment.device_components()
        backend = list(device_components.keys())[0]
        backend_components = self.provider.experiment.device_components(backend)
        self.assertEqual(device_components[backend], backend_components)

    def test_retrieve_backends(self):
        """Test retrieving all backends."""
        backends = self.provider.experiment.backends()
        self.assertIn(self.backend.name(), [b['name'] for b in backends])

    def test_create_figure(self):
        """Test creating a figure."""
        hello_bytes = str.encode("hello world")
        file_name = "hello_world.svg"
        figure_name = "hello.svg"
        with open(file_name, 'wb') as file:
            file.write(hello_bytes)
        self.addCleanup(os.remove, file_name)

        subtests = [
            (hello_bytes, None),
            (hello_bytes, figure_name),
            (file_name, None),
            (file_name, file_name)
        ]

        for figure, figure_name in subtests:
            title = f"figure_name={figure_name}" if figure_name else f"figure={figure}"
            with self.subTest(title=title):
                expr_id = self._create_experiment()
                name, _ = self.provider.experiment.create_figure(
                    experiment_id=expr_id,
                    figure=figure,
                    figure_name=figure_name
                )
                if figure_name:
                    self.assertEqual(figure_name, name)
                elif isinstance(figure, str):
                    self.assertEqual(figure, name)
                expr = self.provider.experiment.experiment(expr_id)
                self.assertIn(name, expr["figure_names"])

    def test_figure(self):
        """Test getting a figure."""
        hello_bytes = str.encode("hello world")
        figure_name = "hello.svg"
        expr_id = self._create_experiment()
        self.provider.experiment.create_figure(
            experiment_id=expr_id,
            figure=hello_bytes,
            figure_name=figure_name
        )
        file_name = "hello_world.svg"
        self.addCleanup(os.remove, file_name)

        subtests = [
            (figure_name, None),
            (figure_name, file_name)
        ]

        for figure_name, file_name in subtests:
            with self.subTest(file_name=file_name):
                fig = self.provider.experiment.figure(expr_id, figure_name, file_name)
                if file_name:
                    with open(file_name, 'rb') as file:
                        self.assertEqual(hello_bytes, file.read())
                else:
                    self.assertEqual(hello_bytes, fig)

    def test_update_figure(self):
        """Test uploading and updating plot data."""
        figure_name = "hello.svg"
        expr_id = self._create_experiment()
        self.provider.experiment.create_figure(
            experiment_id=expr_id,
            figure=str.encode("hello world"),
            figure_name=figure_name
        )
        friend_bytes = str.encode("hello friend!")
        name, _ = self.provider.experiment.update_figure(
            experiment_id=expr_id,
            figure=friend_bytes,
            figure_name=figure_name
        )
        self.assertEqual(name, figure_name)
        rplot = self.provider.experiment.figure(expr_id, figure_name)
        self.assertEqual(rplot, friend_bytes, "Retrieved plot not equal updated plot.")

    def test_delete_figure(self):
        """Test deleting a figure."""
        figure_name = "hello.svg"
        expr_id = self._create_experiment()
        self.provider.experiment.create_figure(
            experiment_id=expr_id,
            figure=str.encode("hello world"),
            figure_name=figure_name
        )
        with mock.patch('builtins.input', lambda _: 'y'):
            self.provider.experiment.delete_figure(expr_id, figure_name)
        self.assertRaises(IBMExperimentEntryNotFound,
                          self.provider.experiment.figure, expr_id, figure_name)

    def test_experiment_coders(self):
        """Test custom encoder and decoder for an experiment."""
        metadata = {"complex": 2 + 3j, "numpy": np.zeros(2)}
        expr_id = self._create_experiment(metadata=metadata, json_encoder=ExperimentEncoder)
        rexp = self.provider.experiment.experiment(expr_id, json_decoder=ExperimentDecoder)
        rmetadata = rexp["metadata"]
        self.assertEqual(metadata["complex"], rmetadata["complex"])
        self.assertTrue((metadata["numpy"] == rmetadata["numpy"]).all())

        new_metadata = {"complex": 4 + 5j, "numpy": np.ones(3)}
        self.provider.experiment.update_experiment(
            expr_id, metadata=new_metadata, json_encoder=ExperimentEncoder)
        rexp = self.provider.experiment.experiment(expr_id, json_decoder=ExperimentDecoder)
        rmetadata = rexp["metadata"]
        self.assertEqual(new_metadata["complex"], rmetadata["complex"])
        self.assertTrue((new_metadata["numpy"] == rmetadata["numpy"]).all())

    def test_analysis_result_coders(self):
        """Test custom encoder and decoder for an analysis result."""
        data = {"complex": 2 + 3j, "numpy": np.zeros(2)}
        result_id = self._create_analysis_result(
            result_data=data, json_encoder=ExperimentEncoder)
        rresult = self.provider.experiment.analysis_result(
            result_id, json_decoder=ExperimentDecoder)
        rdata = rresult["result_data"]
        self.assertEqual(data["complex"], rdata["complex"])
        self.assertTrue((data["numpy"] == rdata["numpy"]).all())

        new_data = {"complex": 4 + 5j, "numpy": np.ones(3)}
        self.provider.experiment.update_analysis_result(
            result_id, result_data=new_data, json_encoder=ExperimentEncoder)
        rresult = self.provider.experiment.analysis_result(
            result_id, json_decoder=ExperimentDecoder)
        rdata = rresult["result_data"]
        self.assertEqual(new_data["complex"], rdata["complex"])
        self.assertTrue((new_data["numpy"] == rdata["numpy"]).all())

    def _create_experiment(
            self,
            experiment_type: Optional[str] = None,
            backend_name: Optional[str] = None,
            **kwargs
    ) -> str:
        """Create a new experiment."""
        experiment_type = experiment_type or 'qiskit_test'
        backend_name = backend_name or self.backend.name()
        exp_id = self.provider.experiment.create_experiment(
            experiment_type=experiment_type,
            backend_name=backend_name,
            **kwargs
        )
        self.experiments_to_delete.append(exp_id)
        return exp_id

    def _create_analysis_result(
            self,
            exp_id: Optional[str] = None,
            result_type: Optional[str] = None,
            result_data: Optional[Dict] = None,
            **kwargs: Any):
        """Create a simple analysis result."""
        experiment_id = exp_id or self._create_experiment()
        result_type = result_type or "qiskit_test"
        result_data = result_data or {}
        aresult_id = self.provider.experiment.create_analysis_result(
            experiment_id=experiment_id,
            result_data=result_data,
            result_type=result_type,
            **kwargs
        )
        return aresult_id

    def _find_backend_device_components(self, min_components):
        """Find a backend with the minimum number of device components."""
        backend_name = self.backend.name()
        device_components = self.device_components
        if len(device_components) < min_components:
            all_components = self.provider.experiment.device_components()
            for key, val in all_components.items():
                if len(val) >= min_components:
                    backend_name = key
                    device_components = val
                    break
        if len(device_components) < min_components:
            return None, None

        return backend_name, device_components
