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

from unittest import skipIf
from typing import Any

import dateutil.parser
import qiskit
from qiskit.compiler import assemble

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

    @skipIf(qiskit.__version__ < '0.14.0', 'Test requires terra 0.14.0')
    def test_backend_configuration(self):
        """Test deserializing backend configuration."""
        backends = self.provider.backends(operational=True, simulator=False)

        # Known keys that look like a serialized complex number.
        good_keys = ('coupling_map', 'qubit_lo_range', 'meas_lo_range', 'gates.coupling_map',
                     'meas_levels', 'qubit_channel_mapping', 'backend_version')
        good_keys_prefix = ('channels',)

        for backend in backends:
            with self.subTest(backend=backend):
                configuration = backend.configuration()
                suspect_keys = set()
                _find_potential_encoded(configuration.to_dict(), '', suspect_keys)

                for gkey in good_keys:
                    try:
                        suspect_keys.remove(gkey)
                    except KeyError:
                        pass

                for gkey in good_keys_prefix:
                    suspect_keys = {ckey for ckey in suspect_keys if not ckey.startswith(gkey)}

                self.assertFalse(suspect_keys)

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
                defaults = backend.defaults()
                complex_keys = set()
                _find_potential_encoded(defaults.to_dict(), '', complex_keys)

                for gkey in good_keys:
                    try:
                        complex_keys.remove(gkey)
                    except KeyError:
                        pass

                self.assertFalse(complex_keys)

    @skipIf(qiskit.__version__ < '0.14.0', 'Test requires terra 0.14.0')
    def test_backend_properties(self):
        """Test deserializing backend properties."""
        backends = self.provider.backends(operational=True, simulator=False)

        # Known keys that look like a serialized object.
        good_keys = ('gates.qubits', 'qubits.name', 'backend_version')

        for backend in backends:
            with self.subTest(backend=backend):
                properties = backend.properties()
                suspect_keys = set()
                _find_potential_encoded(properties.to_dict(), '', suspect_keys)

                for gkey in good_keys:
                    try:
                        suspect_keys.remove(gkey)
                    except KeyError:
                        pass

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
