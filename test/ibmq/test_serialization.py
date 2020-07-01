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

from unittest import skipIf, SkipTest
from typing import Any, Dict, Optional

import dateutil.parser
import qiskit
from qiskit.test import slow_test
from qiskit.providers.ibmq import least_busy
from qiskit import assemble, transpile, schedule, QuantumCircuit

from ..decorators import requires_provider
from ..utils import bell_in_qobj, cancel_job
from ..ibmqtestcase import IBMQTestCase


class TestSerialization(IBMQTestCase):
    """Test data serialization."""

    @classmethod
    @requires_provider
    def setUpClass(cls, provider):
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.provider = provider

    def test_qasm_qobj(self):
        """Test serializing qasm qobj data."""
        backend = self.provider.get_backend('ibmq_qasm_simulator')
        qobj = bell_in_qobj(backend=backend)
        job = backend.run(qobj, validate_qobj=True)
        rqobj = backend.retrieve_job(job.job_id()).qobj()

        self.assertEqual(_array_to_list(qobj.to_dict()), rqobj.to_dict())

    def test_pulse_qobj(self):
        """Test serializing pulse qobj data."""
        backends = self.provider.backends(operational=True, open_pulse=True)
        if not backends:
            self.skipTest('Need pulse backends.')

        backend = backends[0]
        config = backend.configuration()
        defaults = backend.defaults()
        inst_map = defaults.instruction_schedule_map

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

    @skipIf(qiskit.__version__ < '0.14.0', 'Test requires terra 0.14.0')
    def test_backend_configuration(self):
        """Test deserializing backend configuration."""
        backends = self.provider.backends(operational=True, simulator=False)

        # Known keys that look like a serialized complex number.
        good_keys = ('coupling_map', 'qubit_lo_range', 'meas_lo_range', 'gates.coupling_map',
                     'meas_levels', 'qubit_channel_mapping', 'backend_version')
        good_keys_prefixes = ('channels',)

        for backend in backends:
            with self.subTest(backend=backend):
                self._verify_data(backend.configuration().to_dict(),
                                  good_keys, good_keys_prefixes)

    @skipIf(qiskit.__version__ < '0.14.0', 'Test requires terra 0.14.0')
    def test_pulse_defaults(self):
        """Test deserializing backend configuration."""
        backends = self.provider.backends(operational=True, open_pulse=True)
        if not backends:
            self.skipTest('Need pulse backends.')

        # Known keys that look like a serialized complex number.
        good_keys = ('cmd_def.qubits', 'cmd_def.sequence.ch')

        for backend in backends:
            with self.subTest(backend=backend):
                self._verify_data(backend.defaults().to_dict(), good_keys)

    @skipIf(qiskit.__version__ < '0.14.0', 'Test requires terra 0.14.0')
    def test_backend_properties(self):
        """Test deserializing backend properties."""
        backends = self.provider.backends(operational=True, simulator=False)

        # Known keys that look like a serialized object.
        good_keys = ('gates.qubits', 'qubits.name', 'backend_version')

        for backend in backends:
            with self.subTest(backend=backend):
                properties = backend.properties()
                self._verify_data(properties.to_dict(), good_keys)

    @skipIf(qiskit.__version__ < '0.15.0', 'Test requires terra 0.15.0')
    def test_qasm_job_result(self):
        """Test deserializing a QASM job result."""
        backend = self.provider.get_backend('ibmq_qasm_simulator')
        qobj = bell_in_qobj(backend=backend)
        result = backend.run(qobj, validate_qobj=True).result()

        self._verify_data(result.to_dict(), ())

    @skipIf(qiskit.__version__ < '0.15.0', 'Test requires terra 0.15.0')
    @slow_test
    def test_pulse_job_result(self):
        """Test deserializing a pulse job result."""
        backends = self.provider.backends(open_pulse=True, operational=True)
        if not backends:
            raise SkipTest('Skipping pulse test since no pulse backend found.')

        backend = least_busy(backends)
        qc = QuantumCircuit(1, 1)
        qc.x(0)
        qc.measure([0], [0])
        sched = schedule(transpile(qc, backend=backend), backend=backend)
        job = backend.run(assemble(sched, backend=backend))
        result = job.result()

        # Known keys that look like a serialized object.
        good_keys = ('header.backend_version', 'backend_version')
        self._verify_data(result.to_dict(), good_keys)

    def _verify_data(
            self,
            data: Dict,
            good_keys: tuple,
            good_key_prefixes: Optional[tuple] = None
    ):
        """Verify that the input data does not contain serialized objects.

        Args:
            data: Data to validate.
            good_keys: A list of known keys that look serialized objects.
            good_key_prefixes: A list of known prefixes for keys that look like
                serialized objects.
        """
        suspect_keys = set()
        _find_potential_encoded(data, '', suspect_keys)
        # Remove known good keys from suspect keys.
        for gkey in good_keys:
            try:
                suspect_keys.remove(gkey)
            except KeyError:
                pass
        if good_key_prefixes:
            for gkey in good_key_prefixes:
                suspect_keys = {ckey for ckey in suspect_keys if not ckey.startswith(gkey)}
        self.assertFalse(suspect_keys)


def _find_potential_encoded(data: Any, c_key: str, tally: set) -> None:
    """Find data that may be in JSON serialized format.

    Args:
        data: Data to be recursively traversed to find suspects.
        c_key: Key of the field currently being traversed.
        tally: Keys of fields that look suspect.
    """
    if _check_encoded(data):
        tally.add(c_key)

    if isinstance(data, list):
        for item in data:
            _find_potential_encoded(item, c_key, tally)
    elif isinstance(data, dict):
        for key, value in data.items():
            full_key = c_key + '.' + str(key) if c_key else str(key)
            _find_potential_encoded(value, full_key, tally)


def _check_encoded(data):
    """Check if the input data is potentially in JSON serialized format."""
    if isinstance(data, list) and len(data) == 2 and all(isinstance(x, (float, int)) for x in data):
        return True
    elif isinstance(data, str):
        try:
            dateutil.parser.parse(data)
            return True
        except ValueError:
            pass
    return False


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
