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

import time
from typing import List, Optional

from qiskit import QuantumCircuit
from qiskit.qobj import QasmQobj
from qiskit.compiler import assemble, transpile
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.exceptions import JobError
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.ibmq.ibmqfactory import IBMQFactory
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


def bell_in_qobj(backend: IBMQBackend, shots: int = 1024) -> QasmQobj:
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


def get_provider(
        ibmq_factory: IBMQFactory,
        qe_token: str,
        qe_url: str,
        default: bool = True
) -> AccountProvider:
    """Return a provider for the account.

    Args:
        ibmq_factory: An `IBMQFactory` instance.
        qe_token: IBM Quantum Experience token.
        qe_url: IBM Quantum Experience auth URL.
        default: If `True`, the default open access project provider is returned.
            Otherwise, a non open access project provider is returned.

    Returns:
        A provider, as specified by `default`.
    """
    provider_to_return = ibmq_factory.enable_account(qe_token, url=qe_url)  # Default provider.
    if not default:
        # Get a non default provider (i.e.not the default open access project).
        providers = ibmq_factory.providers()
        for provider in providers:
            if provider != provider_to_return:
                provider_to_return = provider
                break
    ibmq_factory.disable_account()

    return provider_to_return


def update_job_tags_and_verify(
        job_to_update: IBMQJob,
        tags_after_update: List[str],
        replacement_tags: Optional[List[str]] = None,
        additional_tags: Optional[List[str]] = None,
        removal_tags: Optional[List[str]] = None
) -> None:
    """Update the tags for a job and assert that the update was successful.

    Args:
        job_to_update: The job to update.
        tags_after_update: The list of tags a job should be associated after updating.
        replacement_tags: The tags that should replace the current tags
            associated with this job set.
        additional_tags: The new tags that should be added to the current tags
            associated with this job set.
        removal_tags: The tags that should be removed from the current tags
            associated with this job set.
    """
    # Update the job tags.
    _ = job_to_update.update_tags(replacement_tags=replacement_tags,
                                  additional_tags=additional_tags,
                                  removal_tags=removal_tags)

    # Cached results may be returned if quickly refreshing,
    # after an update, so wait some time.
    time.sleep(2)
    job_to_update.refresh()

    assert set(job_to_update.tags()) == set(tags_after_update), (
        'Updating the tags for job {} was unsuccessful. '
        'The tags are {}, but they should be {}.'
        .format(job_to_update.job_id(), job_to_update.tags(), tags_after_update))
