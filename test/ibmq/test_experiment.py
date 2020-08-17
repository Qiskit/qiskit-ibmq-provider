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

import os
from unittest import mock
from datetime import datetime
from typing import Optional

from qiskit.providers.ibmq.experiment.experiment import Experiment
from qiskit.providers.ibmq.experiment.analysis_result import AnalysisResult, Fit, DeviceComponent
from qiskit.providers.ibmq.api.exceptions import RequestsApiError
from qiskit.providers.ibmq.experiment.constants import ResultQuality

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider

saved_environ = os.environ.get('USE_STAGING_CREDENTIALS')
os.environ['USE_STAGING_CREDENTIALS'] = 'true'


class TestExperiment(IBMQTestCase):
    """Test experiment modules."""

    @classmethod
    def setUpClass(cls):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.saved_environ = os.environ.get('USE_STAGING_CREDENTIALS')
        os.environ['USE_STAGING_CREDENTIALS'] = 'true'
        cls.provider = cls._setup_provider()    # pylint: disable=no-value-for-parameter
        cls.experiments = cls.provider.experiment.experiments()
        cls.device_components = cls.provider.experiment.device_components()

    @classmethod
    @requires_provider
    def _setup_provider(cls, provider):
        """Get the provider for the class."""
        return provider

    @classmethod
    def tearDownClass(cls) -> None:
        """Class level tear down."""
        os.environ['USE_STAGING_CREDENTIALS'] = cls.saved_environ
        super().tearDownClass()

    def setUp(self) -> None:
        """Test level setup."""
        super().setUp()
        self.experiments_to_delete = []
        self.results_to_delete = []

    def tearDown(self):
        """Test level tear down."""
        for uuid in self.results_to_delete:
            try:
                with mock.patch('builtins.input', lambda _: 'y'):
                    self.provider.experiment.delete_analysis_result(uuid)
            except Exception as err:    # pylint: disable=broad-except
                self.log.info("Unable to delete analysis result %s: %s", uuid, err)
        for uuid in self.experiments_to_delete:
            try:
                with mock.patch('builtins.input', lambda _: 'y'):
                    self.provider.experiment.delete_experiment(uuid)
            except Exception as err:    # pylint: disable=broad-except
                self.log.info("Unable to delete experiment %s: %s", uuid, err)
        super().tearDown()

    def test_get_experiments(self):
        """Test retrieving all experiments."""
        self.assertTrue(self.experiments, "No experiments found.")
        for exp in self.experiments:
            self.assertTrue(isinstance(exp, Experiment))
            self.assertTrue(exp.uuid, "{} does not have an uuid!".format(exp))
            for dt_attr in ['start_datetime', 'creation_datetime',
                            'end_datetime', 'updated_datetime']:
                if getattr(exp, dt_attr):
                    self.assertTrue(getattr(exp, dt_attr).tzinfo)

    def test_get_experiments_with_backend(self):
        """Test retrieving all experiments for a specific backend."""
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
        """Test retrieving an experiment by its ID."""
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
        self.experiments_to_delete.append(new_exp.uuid)
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
            deleted_exp = self.provider.experiment.delete_experiment(new_exp.uuid)
        self.assertEqual(deleted_exp.uuid, new_exp.uuid)

        with self.assertRaises(RequestsApiError) as ex_cm:
            self.provider.experiment.retrieve_experiment(new_exp.uuid)
        self.assertIn("Not Found for url", ex_cm.exception.message)

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

        # TODO retrieve just the result when supported.
        results = self.provider.experiment.analysis_results()
        rresult = None
        for res in results:
            if res.uuid == new_result.uuid:
                rresult = res
        self.assertTrue(rresult, "Cannot find new result.")

        sub_tests = [(new_result, 'local result'), (rresult, 'retrieved result')]
        self.log.debug("Verifying analysis result %s", new_result.uuid)
        for res, name in sub_tests:
            with self.subTest(sub_test_name=name):
                self.assertIsNotNone(res.uuid)
                self.assertTrue(res.creation_datetime.tzinfo)
                self.assertEqual(res.experiment_uuid, new_experiment.uuid)
                self.assertEqual(res.fit.to_dict(), ref_result.fit.to_dict())
                self.assertEqual(res.type, ref_result.type)
                self.assertEqual(res.device_components, [device_comp.type])
                self.assertEqual(res.quality.value, 'No Information')
                self.assertEqual(res.tags, ['qiskit-test'])

    def test_update_analysis_result(self):
        """Test updating an analysis result."""
        new_result = self._create_analysis_result()
        original_type = new_result.type
        new_result.quality = ResultQuality.HUMAN_BAD
        new_fit = Fit(new_result.fit.value*2, new_result.fit.variance*2)
        new_result.fit = new_fit
        self.provider.experiment.update_analysis_result(new_result)

        # TODO retrieve just the result when supported.
        results = self.provider.experiment.analysis_results()
        rresult = None
        for res in results:
            if res.uuid == new_result.uuid:
                rresult = res
        self.assertTrue(rresult, "Cannot find new result.")

        sub_tests = [(new_result, 'local result'), (rresult, 'retrieved result')]
        for res, name in sub_tests:
            with self.subTest(sub_test_name=name):
                self.assertEqual(res.fit.to_dict(), new_fit.to_dict())
                self.assertEqual(res.type, original_type)
                self.assertEqual(res.quality, ResultQuality.HUMAN_BAD)

    def test_delete_analysis_result(self):
        """Test deleting an analysis result."""
        result = self._create_analysis_result()
        with mock.patch('builtins.input', lambda _: 'y'):
            self.provider.experiment.delete_analysis_result(result.uuid)

        # TODO retrieve just the result when supported.
        results = self.provider.experiment.analysis_results()
        rresult = None
        for res in results:
            if res.uuid == result.uuid:
                rresult = res
        self.assertFalse(rresult, "Found deleted result.")

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

    def _create_experiment(self, backend_name: Optional[str] = None):
        backend_name = backend_name or self.experiments[0].backend_name
        new_exp = Experiment(
            backend_name=backend_name,
            experiment_type='test',
            tags=['qiskit-test']
        )
        self.provider.experiment.upload_experiment(new_exp)
        self.experiments_to_delete.append(new_exp.uuid)
        return new_exp

    def _create_analysis_result(self):
        device_comp = self.device_components[0]
        new_experiment = self._create_experiment(device_comp.backend_name)
        fit = Fit(41.456, 4.051)
        new_result = AnalysisResult(experiment_uuid=new_experiment.uuid,
                                    fit=fit,
                                    result_type="T1",
                                    device_components=[device_comp.type],
                                    tags=['qiskit-test'])
        self.provider.experiment.upload_analysis_result(new_result)
        self.results_to_delete.append(new_result.uuid)
        return new_result
