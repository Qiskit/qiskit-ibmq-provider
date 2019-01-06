# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Supporting fake, stubs and mocking classes.

The module includes, among other, a dummy backend simulator. The purpose of
this class is to create a Simulator that we can trick for testing purposes:
testing local timeouts, arbitrary responses or behavior, etc.
"""

import logging

from qiskit.providers.models import BackendConfiguration
from qiskit.providers.models.backendconfiguration import GateConfig
from qiskit.qobj import Qobj, QobjConfig, QobjHeader, QobjInstruction, QobjItem
from qiskit.qobj import QobjExperiment, QobjExperimentHeader

logger = logging.getLogger(__name__)


def new_fake_qobj():
    """Create fake `Qobj` and backend instances."""
    backend = FakeBackend()
    return Qobj(
        qobj_id='test-id',
        config=QobjConfig(shots=1024, memory_slots=1, max_credits=100),
        header=QobjHeader(backend_name=backend.name()),
        experiments=[QobjExperiment(
            instructions=[
                QobjInstruction(name='barrier', qubits=[1])
            ],
            header=QobjExperimentHeader(compiled_circuit_qasm='fake-code'),
            config=QobjItem(seed=123456)
        )]
    )


class FakeBackend:
    """A fake backend."""

    def name(self):
        """Name of fake backend"""
        return 'qiskit_is_cool'

    def configuration(self):
        """Return a make up configuration for a fake device."""
        qx5_cmap = [[1, 0], [1, 2], [2, 3], [3, 4], [3, 14], [5, 4], [6, 5],
                    [6, 7], [6, 11], [7, 10], [8, 7], [9, 8], [9, 10], [11, 10],
                    [12, 5], [12, 11], [12, 13], [13, 4], [13, 14], [15, 0],
                    [15, 2], [15, 14]]
        return BackendConfiguration(
            backend_name='fake',
            backend_version='0.0.0',
            n_qubits=16,
            basis_gates=['u1', 'u2', 'u3', 'cx', 'id'],
            simulator=False,
            local=True,
            conditional=False,
            open_pulse=False,
            memory=False,
            max_shots=65536,
            gates=[GateConfig(name='TODO', parameters=[], qasm_def='TODO')],
            coupling_map=qx5_cmap,
        )
