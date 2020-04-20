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

"""Test serializing and deserializing data sent to the server."""

from qiskit.compiler import assemble

from ..decorators import requires_provider
from ..utils import bell_in_qobj, cancel_job
from ..ibmqtestcase import IBMQTestCase


class TestSerialization(IBMQTestCase):
    """Test data serialization."""

    @requires_provider
    def test_qasm_qobj(self, provider):
        """Test serializing qasm qobj data."""
        backend = provider.get_backend('ibmq_qasm_simulator')
        qobj = bell_in_qobj(backend=backend)
        job = backend.run(qobj, validate_qobj=True)
        rqobj = backend.retrieve_job(job.job_id()).qobj()

        self.assertEqual(_array_to_list(qobj.to_dict()), rqobj.to_dict())

    @requires_provider
    def test_pulse_qobj(self, provider):
        """Test serializing pulse qobj data."""
        backend = provider.get_backend('ibmq_armonk')
        config = backend.configuration()
        defaults = backend.defaults()
        inst_map = defaults.circuit_instruction_map

        x = inst_map.get('x', 0)
        measure = inst_map.get('measure', range(config.n_qubits)) << x.duration
        schedules = x | measure

        qobj = assemble(schedules, backend, meas_level=1, shots=256)
        job = backend.run(qobj, validate_qobj=True)
        rqobj = backend.retrieve_job(job.job_id()).qobj()

        # Convert numpy arrays to lists since they now get converted right
        # before being sent to the server.
        self.assertEqual(_array_to_list(qobj.to_dict()), rqobj.to_dict())

        cancel_job(job)


def _array_to_list(data):
    """Convert numpy arrays to lists."""
    for key, value in data.items():
        if hasattr(value, 'tolist'):
            data[key] = value.tolist()
        elif isinstance(value, dict):
            _array_to_list(value)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    value[index] = _array_to_list(item)

    return data
