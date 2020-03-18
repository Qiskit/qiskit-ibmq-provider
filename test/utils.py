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

"""General utility functions for testing."""

from qiskit import QuantumCircuit
from qiskit.qobj import Qobj
from qiskit.compiler import assemble, transpile
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.exceptions import JobError
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend
from qiskit.providers.ibmq.job import IBMQJob


def most_busy_backend(provider: AccountProvider) -> IBMQBackend:
    """Return the most busy backend for the provider given.

    Return the most busy available backend for those that
    have a `pending_jobs` in their `status`. Backends such as
    local backends that do not have this are not considered.

    Args:
        provider: IBM Quantum Experience account provider.

    Returns:
        The most busy backend.
    """
    backends = provider.backends(simulator=False, operational=True)
    return max([b for b in backends if b.configuration().n_qubits >= 5],
               key=lambda b: b.status().pending_jobs)


def get_large_circuit(backend: IBMQBackend) -> QuantumCircuit:
    """Return a slightly larger circuit that would run a bit longer.

    Args:
        backend: Backend on which the circuit will run.

    Returns:
        A larger circuit.
    """
    n_qubits = min(backend.configuration().n_qubits, 20)
    circuit = QuantumCircuit(n_qubits, n_qubits)
    for n in range(n_qubits-1):
        circuit.h(n)
        circuit.cx(n, n+1)
    circuit.measure(list(range(n_qubits)), list(range(n_qubits)))

    return circuit


def bell_in_qobj(backend: IBMQBackend, shots: int = 1024) -> Qobj:
    """Return a bell circuit in Qobj format.

    Args:
        backend: Backend to use for transpiling the circuit.
        shots: Number of shots.

    Returns:
        A bell circuit in Qobj format.
    """
    return assemble(transpile(ReferenceCircuits.bell(), backend=backend),
                    backend=backend, shots=shots)


def cancel_job(job: IBMQJob, verify: bool = False) -> bool:
    """Cancel a job.

    Args:
        job: Job to cancel.
        verify: Verify job status.

    Returns:
        Whether job has been cancelled.
    """
    cancelled = False
    for _ in range(2):
        # Try twice in case job is not in a cancellable state
        try:
            cancelled = job.cancel()
            if cancelled:
                if verify:
                    status = job.status()
                    assert status is JobStatus.CANCELLED, \
                        'cancel() was successful for job {} but its ' \
                        'status is {}.'.format(job.job_id(), status)
                break
        except JobError:
            pass

    return cancelled
