# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Test IBMQJob attributes."""

import time
from unittest import mock, skip
from datetime import datetime, timedelta
import re
import uuid

from dateutil import tz

from qiskit.test import slow_test
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.jobstatus import JobStatus, JOB_FINAL_STATES
from qiskit.providers.ibmq.job.exceptions import IBMQJobFailureError
from qiskit.providers.ibmq.api.clients.account import AccountClient
from qiskit.providers.ibmq.exceptions import IBMQBackendValueError, IBMQBackendApiProtocolError
from qiskit.compiler import transpile

from ..ibmqtestcase import IBMQTestCase
from ..decorators import requires_provider, requires_device
from ..utils import (most_busy_backend, cancel_job, get_large_circuit,
                     update_job_tags_and_verify, submit_job_bad_shots,
                     submit_job_one_bad_instr)
from ..fake_account_client import BaseFakeAccountClient, MissingFieldFakeJob


class TestIBMQJobAttributes(IBMQTestCase):
    """Test IBMQJob instance attributes."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider
        cls.sim_backend = provider.get_backend('ibmq_qasm_simulator')
        cls.bell = transpile(ReferenceCircuits.bell(), cls.sim_backend)
        cls.sim_job = cls.sim_backend.run(cls.bell)
        cls.last_week = datetime.now() - timedelta(days=7)

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self._qc = ReferenceCircuits.bell()

    def test_job_id(self):
        """Test getting a job ID."""
        self.assertTrue(self.sim_job.job_id() is not None)

    def test_get_backend_name(self):
        """Test getting a backend name."""
        self.assertTrue(self.sim_job.backend().name() == self.sim_backend.name())

    @slow_test
    @requires_device
    def test_running_job_properties(self, backend):
        """Test fetching properties of a running job."""
        def _job_callback(job_id, job_status, cjob, **kwargs):
            self.simple_job_callback(job_id, job_status, cjob, **kwargs)
            if job_status is JobStatus.RUNNING:
                job_properties[0] = cjob.properties()
                cancel_job(cjob)

        job_properties = [None]
        large_qx = get_large_circuit(backend=backend)
        job = backend.run(transpile(large_qx, backend=backend))
        job.wait_for_final_state(wait=None, callback=_job_callback)
        self.assertIsNotNone(job_properties[0])

    def test_job_name(self):
        """Test using job names on a simulator."""
        # Use a unique job name
        job_name = str(time.time()).replace('.', '')
        job = self.sim_backend.run(self.bell, job_name=job_name)
        job_id = job.job_id()
        rjob = self.provider.backend.retrieve_job(job_id)
        self.assertEqual(rjob.name(), job_name)

        # Check using partial matching.
        job_name_partial = job_name[8:]
        retrieved_jobs = self.provider.backend.jobs(
            backend_name=self.sim_backend.name(), job_name=job_name_partial,
            start_datetime=self.last_week)
        self.assertGreaterEqual(len(retrieved_jobs), 1)
        retrieved_job_ids = {job.job_id() for job in retrieved_jobs}
        self.assertIn(job_id, retrieved_job_ids)

        # Check using regular expressions.
        job_name_regex = '^{}$'.format(job_name)
        retrieved_jobs = self.provider.backend.jobs(
            backend_name=self.sim_backend.name(), job_name=job_name_regex,
            start_datetime=self.last_week)
        self.assertEqual(len(retrieved_jobs), 1)
        self.assertEqual(job_id, retrieved_jobs[0].job_id())

    def test_job_name_update(self):
        """Test changing the name associated with a job."""
        # Use a unique job name
        initial_job_name = str(time.time()).replace('.', '')
        job = self.sim_backend.run(self.bell, job_name=initial_job_name)

        new_names_to_test = [
            '',  # empty string as name.
            '{}_new'.format(str(time.time()).replace('.', ''))  # unique name.
        ]
        for new_name in new_names_to_test:
            with self.subTest(new_name=new_name):
                _ = job.update_name(new_name)  # Update the job name.
                # Cached results may be returned if updating too quickly.
                # Wait before updating again.
                time.sleep(2)
                job.refresh()
                self.assertEqual(job.name(), new_name,
                                 'Updating the name for job {} from "{}" to "{}" '
                                 'was unsuccessful.'.format(job.job_id(), job.name(), new_name))

    def test_duplicate_job_name(self):
        """Test multiple jobs with the same custom job name using a simulator."""
        # Use a unique job name
        job_name = str(time.time()).replace('.', '')
        job_ids = set()
        for _ in range(2):
            job = self.sim_backend.run(self.bell, job_name=job_name)
            job_ids.add(job.job_id())

        retrieved_jobs = self.provider.backend.jobs(
            backend_name=self.sim_backend.name(), job_name=job_name,
            start_datetime=self.last_week)

        self.assertEqual(len(retrieved_jobs), 2,
                         "More than 2 jobs retrieved: {}".format(retrieved_jobs))
        retrieved_job_ids = {job.job_id() for job in retrieved_jobs}
        self.assertEqual(job_ids, retrieved_job_ids)
        for job in retrieved_jobs:
            self.assertEqual(job.name(), job_name)

    @slow_test
    @requires_device
    def test_error_message_device(self, backend):
        """Test retrieving job error messages from a device backend."""
        job = submit_job_one_bad_instr(backend)
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)

        rjob = backend.retrieve_job(job.job_id())

        for q_job, partial in [(job, False), (rjob, True)]:
            with self.subTest(partial=partial):
                with self.assertRaises(IBMQJobFailureError) as err_cm:
                    q_job.result(partial=partial)
                for msg in (err_cm.exception.message, q_job.error_message()):
                    self.assertIn('bad_instruction', msg)
                    self.assertIsNotNone(re.search(r'Error code: [0-9]{4}\.$', msg), msg)

    @skip("Skip until aer issue 1214 is fixed")
    def test_error_message_simulator(self):
        """Test retrieving job error messages from a simulator backend."""
        job = submit_job_one_bad_instr(self.sim_backend)
        with self.assertRaises(IBMQJobFailureError) as err_cm:
            job.result()
        self.assertNotIn('bad_instruction', err_cm.exception.message)

        message = job.error_message()
        self.assertIn('Experiment 1: ERROR', message)

        r_message = self.provider.backend.retrieve_job(job.job_id()).error_message()
        self.assertIn('Experiment 1: ERROR', r_message)

    def test_error_message_validation(self):
        """Test retrieving job error message for a validation error."""
        job = submit_job_bad_shots(self.sim_backend)
        rjob = self.sim_backend.retrieve_job(job.job_id())

        for q_job, partial in [(job, False), (rjob, True)]:
            with self.subTest(partial=partial):
                with self.assertRaises(IBMQJobFailureError) as err_cm:
                    q_job.result(partial=partial)
                for msg in (err_cm.exception.message, q_job.error_message()):
                    self.assertNotIn("Unknown", msg)
                    self.assertIsNotNone(re.search(r'Error code: [0-9]{4}\.$', msg), msg)

        self.assertEqual(job.error_message(), rjob.error_message())

    def test_refresh(self):
        """Test refreshing job data."""
        self.sim_job._wait_for_completion()
        if 'COMPLETED' not in self.sim_job.time_per_step():
            self.sim_job.refresh()

        rjob = self.provider.backend.jobs(
            db_filter={'id': self.sim_job.job_id()}, start_datetime=self.last_week)[0]
        self.assertFalse(rjob._time_per_step)
        rjob.refresh()
        self.assertEqual(rjob._time_per_step, self.sim_job._time_per_step)

    def test_job_creation_date(self):
        """Test retrieving creation date, while ensuring it is in local time."""
        # datetime, before running the job, in local time.
        start_datetime = datetime.now().replace(tzinfo=tz.tzlocal()) - timedelta(seconds=1)
        job = self.sim_backend.run(self.bell)
        job.result()
        # datetime, after the job is done running, in local time.
        end_datetime = datetime.now().replace(tzinfo=tz.tzlocal()) + timedelta(seconds=1)

        self.assertTrue((start_datetime <= job.creation_date() <= end_datetime),
                        'job creation date {} is not '
                        'between the start date time {} and end date time {}'
                        .format(job.creation_date(), start_datetime, end_datetime))

    def test_time_per_step(self):
        """Test retrieving time per step, while ensuring the date times are in local time."""
        # datetime, before running the job, in local time.
        start_datetime = datetime.now().replace(tzinfo=tz.tzlocal()) - timedelta(seconds=1)
        job = self.sim_backend.run(self.bell)
        job.result()
        # datetime, after the job is done running, in local time.
        end_datetime = datetime.now().replace(tzinfo=tz.tzlocal()) + timedelta(seconds=1)

        self.assertTrue(job.time_per_step())
        for step, time_data in job.time_per_step().items():
            self.assertTrue((start_datetime <= time_data <= end_datetime),
                            'job time step "{}={}" is not '
                            'between the start date time {} and end date time {}'
                            .format(step, time_data, start_datetime, end_datetime))

        rjob = self.provider.backend.jobs(
            db_filter={'id': job.job_id()}, start_datetime=self.last_week)[0]
        self.assertTrue(rjob.time_per_step())

    def test_new_job_attributes(self):
        """Test job with new attributes."""
        def _mocked__api_job_submit(*args, **kwargs):
            submit_info = original_submit(*args, **kwargs)
            submit_info.update({'batman': 'bruce'})
            return submit_info

        original_submit = self.sim_backend._api_client.job_submit
        with mock.patch.object(AccountClient, 'job_submit',
                               side_effect=_mocked__api_job_submit):
            job = self.sim_backend.run(self.bell)

        self.assertEqual(job.batman_, 'bruce')

    def test_queue_info(self):
        """Test retrieving queue information."""
        # Find the most busy backend.
        backend = most_busy_backend(self.provider)
        leave_states = list(JOB_FINAL_STATES) + [JobStatus.RUNNING]
        job = backend.run(self.bell)
        queue_info = None
        for _ in range(20):
            queue_info = job.queue_info()
            # Even if job status is queued, its queue info may not be immediately available.
            if (job._status is JobStatus.QUEUED and job.queue_position() is not None) or \
                    job._status in leave_states:
                break
            time.sleep(1)

        if job._status is JobStatus.QUEUED and job.queue_position() is not None:
            self.log.debug("Job id=%s, queue info=%s, queue position=%s",
                           job.job_id(), queue_info, job.queue_position())
            msg = "Job {} is queued but has no ".format(job.job_id())
            self.assertIsNotNone(queue_info, msg + "queue info.")
            for attr, value in queue_info.__dict__.items():
                self.assertIsNotNone(value, msg + attr)
            self.assertTrue(all(0 < priority <= 1.0 for priority in [
                queue_info.hub_priority, queue_info.group_priority, queue_info.project_priority]),
                            "Unexpected queue info {} for job {}".format(queue_info, job.job_id()))

            self.assertTrue(queue_info.format())
            self.assertTrue(repr(queue_info))
        else:
            self.assertIsNone(job.queue_position())
            self.log.warning("Unable to retrieve queue information")

        # Cancel job so it doesn't consume more resources.
        cancel_job(job)

    def test_esp_readout_not_enabled(self):
        """Test that an error is thrown is ESP readout is used and the backend does not support it.
        """
        saved_api = self.sim_backend._api_client
        try:
            self.sim_backend._api_client = BaseFakeAccountClient()
            # sim backend does not have ``measure_esp_enabled`` flag: defaults to ``False``
            with self.assertRaises(IBMQBackendValueError) as context_manager:
                self.sim_backend.run(self.bell, use_measure_esp=True)
            self.assertIn(
                "ESP readout not supported on this device. Please make sure the flag "
                "'use_measure_esp' is unset or set to 'False'.",
                context_manager.exception.message,
            )
        finally:
            self.sim_backend._api_client = saved_api

    def test_esp_readout_enabled(self):
        """Test that ESP readout can be used when the backend supports it."""
        saved_api = self.sim_backend._api_client
        try:
            self.sim_backend._api_client = BaseFakeAccountClient()
            setattr(self.sim_backend._configuration, "measure_esp_enabled", True)
            job = self.sim_backend.run(self.bell, use_measure_esp=True)
            self.assertEqual(job.backend_options()["use_measure_esp"], True)
        finally:
            delattr(self.sim_backend._configuration, "measure_esp_enabled")
            self.sim_backend._api_client = saved_api

    def test_esp_readout_default_value(self):
        """Test that ESP readout is set to backend support value if not specified."""
        saved_api = self.sim_backend._api_client
        try:
            self.sim_backend._api_client = BaseFakeAccountClient()
            # ESP readout not enabled on backend
            setattr(self.sim_backend._configuration, "measure_esp_enabled", False)
            job = self.sim_backend.run(self.bell)
            self.assertEqual(job.backend_options()["use_measure_esp"], False)
            # ESP readout enabled on backend
            setattr(self.sim_backend._configuration, "measure_esp_enabled", True)
            job = self.sim_backend.run(self.bell)
            self.assertEqual(job.backend_options()["use_measure_esp"], True)
        finally:
            delattr(self.sim_backend._configuration, "measure_esp_enabled")
            self.sim_backend._api_client = saved_api

    def test_esp_readout_enabled_not_used(self):
        """Test that ESP readout is not used if user sets to ``False``, even if backend supports it.
        """
        saved_api = self.sim_backend._api_client
        try:
            self.sim_backend._api_client = BaseFakeAccountClient()
            setattr(self.sim_backend._configuration, "measure_esp_enabled", True)
            job = self.sim_backend.run(self.bell, use_measure_esp=False)
            self.assertEqual(job.backend_options()["use_measure_esp"], False)
        finally:
            delattr(self.sim_backend._configuration, "measure_esp_enabled")
            self.sim_backend._api_client = saved_api

    def test_job_tags_or(self):
        """Test using job tags with an or operator."""
        # Use a unique tag.
        job_tags = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]
        job = self.sim_backend.run(self.bell, job_tags=job_tags)

        rjobs = self.sim_backend.jobs(
            job_tags=['phantom_tag'], start_datetime=self.last_week)
        self.assertEqual(len(rjobs), 0,
                         "Expected job {}, got {}".format(job.job_id(), rjobs))

        # Check all tags, some of the tags, and a mixture of good and bad tags.
        tags_to_check = [job_tags, job_tags[1:2], job_tags[0:1]+['phantom_tag']]
        for tags in tags_to_check:
            with self.subTest(tags=tags):
                rjobs = self.sim_backend.jobs(job_tags=tags, start_datetime=self.last_week)
                self.assertEqual(len(rjobs), 1,
                                 "Expected job {}, got {}".format(job.job_id(), rjobs))
                self.assertEqual(rjobs[0].job_id(), job.job_id())
                self.assertEqual(set(rjobs[0].tags()), set(job_tags))

    def test_job_tags_and(self):
        """Test using job tags with an and operator."""
        # Use a unique tag.
        job_tags = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]
        job = self.sim_backend.run(self.bell, job_tags=job_tags)

        no_rjobs_tags = [job_tags[0:1]+['phantom_tags'], ['phantom_tag']]
        for tags in no_rjobs_tags:
            rjobs = self.sim_backend.jobs(
                job_tags=tags, job_tags_operator="AND", start_datetime=self.last_week)
            self.assertEqual(len(rjobs), 0,
                             "Expected job {}, got {}".format(job.job_id(), rjobs))

        has_rjobs_tags = [job_tags, job_tags[1:3]]
        for tags in has_rjobs_tags:
            with self.subTest(tags=tags):
                rjobs = self.sim_backend.jobs(
                    job_tags=tags, job_tags_operator="AND", start_datetime=self.last_week)
                self.assertEqual(len(rjobs), 1,
                                 "Expected job {}, got {}".format(job.job_id(), rjobs))
                self.assertEqual(rjobs[0].job_id(), job.job_id())
                self.assertEqual(set(rjobs[0].tags()), set(job_tags))

    def test_job_tags_replace(self):
        """Test updating job tags by replacing a job's existing tags."""
        initial_job_tags = [uuid.uuid4().hex]
        job = self.sim_backend.run(self.bell, job_tags=initial_job_tags)

        tags_to_replace_subtests = [
            [],  # empty tags.
            ['{}_new_tag_{}'.format(uuid.uuid4().hex, i) for i in range(2)]  # unique tags.
        ]
        for tags_to_replace in tags_to_replace_subtests:
            with self.subTest(tags_to_replace=tags_to_replace):
                update_job_tags_and_verify(job_to_update=job,
                                           tags_after_update=tags_to_replace,
                                           replacement_tags=tags_to_replace)

    def test_job_tags_add(self):
        """Test updating job tags by adding to a job's existing tags."""
        initial_job_tags = [uuid.uuid4().hex]
        job = self.sim_backend.run(self.bell, job_tags=initial_job_tags)

        tags_to_add_subtests = [
            [],  # empty tags.
            ['{}_new_tag_{}'.format(uuid.uuid4().hex, i) for i in range(2)]  # unique tags.
        ]
        for tags_to_add in tags_to_add_subtests:
            tags_after_add = job.tags() + tags_to_add
            update_job_tags_and_verify(job_to_update=job,
                                       tags_after_update=tags_after_add,
                                       additional_tags=tags_to_add)

    def test_job_tags_remove(self):
        """Test updating job tags by removing from a job's existing tags."""
        initial_job_tags = [uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex]
        job = self.sim_backend.run(self.bell, job_tags=initial_job_tags)

        tags_to_remove_subtests = [
            [],
            initial_job_tags[:2],  # Will be used to remove the first two tags of initial_job_tags.
            ['phantom_tag', 'ghost_tag', initial_job_tags[-1]]  # Get the last initial tag.
        ]
        for tags_to_remove in tags_to_remove_subtests:
            tags_after_removal_set = set(job.tags()) - set(tags_to_remove)
            update_job_tags_and_verify(job_to_update=job,
                                       tags_after_update=list(tags_after_removal_set),
                                       removal_tags=tags_to_remove)

    def test_job_tags_add_and_remove(self):
        """Test updating job tags by adding and removing the same job tag."""
        new_job_tags = [uuid.uuid4().hex]
        update_job_tags_and_verify(job_to_update=self.sim_job,
                                   tags_after_update=[],
                                   additional_tags=new_job_tags,
                                   removal_tags=new_job_tags)

    def test_job_tags_replace_and_remove(self):
        """Test updating job tags by replacing and removing tags."""
        job = self.sim_backend.run(self.bell, job_tags=[uuid.uuid4().hex])

        replacement_tags = [uuid.uuid4().hex, uuid.uuid4().hex]
        # Remove the first tag in `replacement_tags`
        removal_tags = replacement_tags[:1]
        # After updating, the final tags should only be the second tag of `replacement_tags`.
        tags_after_update = replacement_tags[1:]

        update_job_tags_and_verify(job_to_update=job,
                                   tags_after_update=tags_after_update,
                                   replacement_tags=replacement_tags,
                                   removal_tags=removal_tags)

    def test_job_tags_all_parameters(self):
        """Test updating job tags by replacing, adding, and removing tags."""
        job = self.sim_backend.run(self.bell, job_tags=[uuid.uuid4().hex])

        replacement_tags = [uuid.uuid4().hex, uuid.uuid4().hex]
        additional_tags = [uuid.uuid4().hex, uuid.uuid4().hex]
        # Remove the first tag of `replacement_tags` and `additional_tags`.
        removal_tags = replacement_tags[:1] + additional_tags[:1]
        # After updating, the final tags should contain the second tag of both
        # `replacement_tags` and `additional_tags`.
        tags_after_update = replacement_tags[1:] + additional_tags[1:]

        update_job_tags_and_verify(job_to_update=job,
                                   tags_after_update=tags_after_update,
                                   replacement_tags=replacement_tags,
                                   additional_tags=additional_tags,
                                   removal_tags=removal_tags)

    def test_invalid_job_tags(self):
        """Test using job tags with an and operator."""
        self.assertRaises(IBMQBackendValueError, self.sim_backend.run,
                          self.bell, job_tags={'foo'})
        self.assertRaises(IBMQBackendValueError, self.sim_backend.jobs, job_tags=[1, 2, 3])

    def test_run_mode(self):
        """Test job run mode."""
        self.sim_job.wait_for_final_state()
        self.assertEqual(self.sim_job.scheduling_mode(), "fairshare",
                         "Job {} scheduling mode is {}".format(
                             self.sim_job.job_id(), self.sim_job.scheduling_mode()))

        rjob = self.sim_backend.retrieve_job(self.sim_job.job_id())
        self.assertEqual(rjob.scheduling_mode(), "fairshare",
                         "Job {} scheduling mode is {}".format(
                             rjob.job_id(), rjob.scheduling_mode()))

    def test_missing_required_fields(self):
        """Test response data is missing required fields."""
        saved_api = self.sim_backend._api_client
        try:
            self.sim_backend._api_client = BaseFakeAccountClient(job_class=MissingFieldFakeJob)
            self.assertRaises(IBMQBackendApiProtocolError, self.sim_backend.run, self.bell)
        finally:
            self.sim_backend._api_client = saved_api

    def test_client_version(self):
        """Test job client version information."""
        self.assertIsNotNone(self.sim_job.result().client_version)
        self.assertIsNotNone(self.sim_job.client_version)

    def test_experiment_id(self):
        """Test job experiment id."""
        exp_id = uuid.uuid4().hex
        job = self.sim_backend.run(self.bell, experiment_id=exp_id)
        self.assertEqual(job.experiment_id, exp_id)
        rjob = self.provider.backend.retrieve_job(job.job_id())
        self.assertEqual(rjob.experiment_id, exp_id)
        rjobs = self.provider.backend.jobs(experiment_id=exp_id)
        for rjob in rjobs:
            self.assertEqual(rjob.experiment_id, exp_id,
                             f"Job {rjob.job_id()} has experiment ID {rjob.experiment_id} "
                             f"instead of {exp_id}")
