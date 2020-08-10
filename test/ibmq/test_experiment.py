# -*- coding: utf-8 -*-

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

from unittest import mock, skip
from datetime import datetime

from qiskit.providers.ibmq.experiment.experiment import Experiment
from qiskit.providers.ibmq.experiment.analysis_results import AnalysisResult, Fit
from qiskit.providers.ibmq.api.exceptions import RequestsApiError

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider


class TestExperiment(IBMQTestCase):
    """Test experiment modules."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.experiments = provider.experiment.experiments()

    def setUp(self) -> None:
        """Test level setup."""
        super().setUp()
        self.uuid_to_delete = []

    def tearDown(self):
        for uuid in self.uuid_to_delete:
            try:
                with mock.patch('builtins.input', lambda _: 'y'):
                    self.provider.experiment.delete_experiment(uuid)
            except Exception:
                pass
        super().tearDown()

    def test_get_experiments(self):
        """Test retrieve all experiments."""
        self.assertTrue(self.experiments, "No experiments found.")
        for exp in self.experiments:
            self.assertTrue(isinstance(exp, Experiment))
            self.assertTrue(exp.uuid, "{} does not have an uuid!".format(exp))
            for dt_attr in ['start_datetime', 'creation_datetime', 'end_datetime', 'updated_datetime']:
                if getattr(exp, dt_attr):
                    self.assertTrue(getattr(exp, dt_attr).tzinfo)

    def test_get_experiments_with_backend(self):
        """Test retrieve all experiments for a specific backend."""
        backend_name = self.experiments[0].backend_name
        uuid = self.experiments[0].uuid
        backend_experiments = self.provider.experiment.experiments(backend_name=backend_name)

        found = False
        for exp in backend_experiments:
            self.assertEqual(exp.backend_name, backend_name)
            if exp.uuid == uuid:
                found = True
        self.assertTrue(found, "Experiment {} not found when filter by backend name {}.".format(
            uuid, backend_name))

    def test_retrieve_experiment(self):
        """Test retrieve a experiment by its ID."""
        exp = self.experiments[0]
        rexp = self.provider.experiment.retrieve_experiment(exp.uuid)
        self.assertEqual(exp.uuid, rexp.uuid)

    def test_upload_experiment(self):
        """Test uploading an experiment."""
        exp = self.experiments[0]
        new_exp = Experiment(
            backend_name=exp.backend_name,
            experiment_type='test',
            tags=['qiskit-test']
        )
        self.provider.experiment.upload_experiment(new_exp)
        self.uuid_to_delete.append(new_exp.uuid)
        self.assertTrue(new_exp.uuid)
        self.assertTrue(new_exp.creation_datetime)
        for dt_attr in ['start_datetime', 'creation_datetime', 'end_datetime', 'updated_datetime']:
            if getattr(exp, dt_attr):
                self.assertTrue(getattr(exp, dt_attr).tzinfo)

    def test_update_experiment(self):
        """Test updating an experiment."""
        new_exp = self._create_experiment()
        new_exp.end_datetime = datetime.now()
        self.provider.experiment.update_experiment(new_exp)
        rexp = self.provider.experiment.retrieve_experiment(new_exp.uuid)
        self.assertEqual(new_exp.end_datetime, rexp.end_datetime)

    def test_delete_experiment(self):
        """Test deleting an experiment."""
        new_exp = self._create_experiment()

        with mock.patch('builtins.input', lambda _: 'y'):
            self.provider.experiment.delete_experiment(new_exp.uuid)

        with self.assertRaises(RequestsApiError) as ex_cm:
            self.provider.experiment.retrieve_experiment(new_exp.uuid)
        self.assertIn("Not Found for url", ex_cm.exception.message)

    def test_retrieve_backends(self):
        """Test retrieving all backends."""
        backends = self.provider.experiment.backends()
        backend_names = [b['name'] for b in backends]
        self.assertIn(self.experiments[0].backend_name, backend_names)

    def test_get_analysis_results(self):
        """Test retrieving all analysis results."""
        results = self.provider.experiment.analysis_results()
        experiment_ids = [exp.uuid for exp in self.experiments]
        for res in results:
            self.assertTrue(isinstance(res, AnalysisResult))
            self.assertTrue(isinstance(res.fit, Fit))
            self.assertTrue(res.uuid, "{} does not have an uuid!".format(res))
            self.assertIn(res.experiment_uuid, experiment_ids)
            for dt_attr in ['creation_datetime', 'updated_datetime']:
                if getattr(res, dt_attr):
                    self.assertTrue(getattr(res, dt_attr).tzinfo)

    @skip("Not supported yet")
    def test_upload_analysis_result(self):
        """Test uploading an analysis result."""
        experiment_uuid = self.experiments[0].uuid
        fit = Fit(41.45645369602045, 4.0513113770512685)
        new_result = AnalysisResult(experiment_uuid=experiment_uuid,
                                    fit=fit,
                                    result_type='T1',
                                    device_components=["Q1", "R1"],
                                    quality='No Information',
                                    tags=['qiskit-test'],
                                    chisq=1.3253077965696105)
        self.provider.experiment.upload_analysis_result(new_result)

        # TODO retrieve just the result when supported.
        results = self.provider.experiment.analysis_results()
        rresult = None
        for res in results:
            if res.uuid == new_result.uuid:
                rresult = res
        self.failIf(not rresult, "Cannot find new result.")

        sub_tests = [(new_result, 'new result'), (rresult, 'retrieved result')]
        self.log.debug("Verifying analysis result %s", new_result.uuid)
        for res, name in sub_tests:
            with self.subTest(sub_test_name=name):
                self.assertIsNotNone(res.uuid)
                self.assertTrue(res.creation_datetime.tzinfo)
                self.assertTrue(res.updated_datetime.tzinfo)
                self.assertEqual(res.experiment_uuid, experiment_uuid)
                self.assertEqual(res.fit.to_dict(), fit.to_dict())
                self.assertEqual(res.type, 'T1')
                self.assertEqual(res.device_components, ["Q1"])
                self.assertEqual(res.quality.value, 'Human Bad')
                self.assertEqual(res.tags, ['qiskit-test'])

    def _create_experiment(self):
        exp = self.experiments[0]
        new_exp = Experiment(
            backend_name=exp.backend_name,
            experiment_type='test',
            tags=['qiskit-test']
        )
        self.provider.experiment.upload_experiment(new_exp)
        self.uuid_to_delete.append(new_exp.uuid)
        return new_exp
