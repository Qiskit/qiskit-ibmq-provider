# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBMQJob model tests."""

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import assemble, transpile
from qiskit.validation import ModelValidationError
from qiskit.validation.jsonschema import SchemaValidationError

from qiskit.providers.ibmq import IBMQJob

from ..jobtestcase import JobTestCase
from ..decorators import requires_provider

VALID_JOB_RESPONSE = {
    # Attributes needed by the constructor.
    'api': None,
    '_backend': None,

    # Attributes required by the schema.
    'id': 'TEST_ID',
    'kind': 'q-object',
    'status': 'CREATING',
    'creationDate': '2019-01-01T13:15:58.425972'
}


class TestIBMQJobModel(JobTestCase):
    """Test model-related functionality of IBMQJob."""

    def test_bad_job_schema(self):
        """Test creating a job with bad job schema."""
        bad_job_info = {'id': 'TEST_ID'}
        with self.assertRaises(ModelValidationError):
            IBMQJob.from_dict(bad_job_info)

    @requires_provider
    def test_invalid_qobj(self, provider):
        """Test submitting an invalid qobj."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        qobj = assemble(transpile(_bell_circuit(), backend=backend),
                        backend=backend)

        delattr(qobj, 'qobj_id')
        with self.assertRaises(SchemaValidationError):
            backend.run(qobj, validate_qobj=True)

    def test_valid_job(self):
        """Test the model can be created from a response."""
        job = IBMQJob.from_dict(VALID_JOB_RESPONSE)

        # Check for a required attribute with correct name.
        self.assertNotIn('creationDate', job)
        self.assertIn('_creation_date', job)

    def test_auto_undefined_fields(self):
        """Test undefined response fields appear in the model."""
        response = VALID_JOB_RESPONSE.copy()
        response['newField'] = {'foo': 2}
        job = IBMQJob.from_dict(response)

        # Check the field appears as an attribute in the model.
        self.assertIn('new_field', job)
        self.assertEqual(job.new_field, {'foo': 2})

    def test_invalid_enum(self):
        """Test creating a model with an invalid value for an Enum field."""
        response = VALID_JOB_RESPONSE.copy()
        response['kind'] = 'invalid'
        with self.assertRaises(ModelValidationError):
            IBMQJob.from_dict(response)


def _bell_circuit():
    """Return a bell state circuit."""
    qr = QuantumRegister(2, 'q')
    cr = ClassicalRegister(2, 'c')
    qc = QuantumCircuit(qr, cr)
    qc.h(qr[0])
    qc.cx(qr[0], qr[1])
    qc.measure(qr, cr)
    return qc
