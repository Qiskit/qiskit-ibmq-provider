# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Manager for interacting with Circuits."""

from qiskit.providers import JobStatus

from ..api_v2.exceptions import RequestsApiError
from ..job.circuitjob import CircuitJob
from .exceptions import (CircuitError,
                         CircuitAvailabilityError, CircuitResultError,
                         CircuitSubmitError)


GRAPH_STATE = 'graph_state'
HARDWARE_EFFICIENT = 'hardware_efficient'
RANDOM_UNIFORM = 'random_uniform'


class CircuitsManager:
    """Class that provides access to the different Circuits."""

    def __init__(self, client):
        self.client = client

    def _call_circuit(self, name, **kwargs):
        """Execute a Circuit.

        Args:
            name (str): name of the Circuit.
            **kwargs: parameters passed to the Circuit.

        Returns:
            Result: the result of executing the circuit.

        Raises:
            CircuitAvailabilityError: if Circuits are not available.
            CircuitSubmitError: if there was an error submitting the Circuit.
            CircuitResultError: if the result of the Circuit could not be
                returned.
        """
        try:
            response = self.client.circuit_run(name=name, **kwargs)
        except RequestsApiError as ex:
            # Revise the original requests exception to intercept.
            error_response = ex.original_exception.response

            # Check for errors related to the submission.
            try:
                body = error_response.json()
            except ValueError:
                body = {}

            # Generic authorization or unavailable endpoint error.
            if error_response.status_code in (401, 404):
                raise CircuitAvailabilityError() from None

            if error_response.status_code == 400:
                # Hub permission error.
                if body.get('error', {}).get('code') == 'HUB_NOT_FOUND':
                    raise CircuitAvailabilityError() from None

                # Generic error.
                if body.get('error', {}).get('code') == 'GENERIC_ERROR':
                    raise CircuitAvailabilityError() from None

            # Handle the rest of the exceptions as unexpected.
            raise CircuitSubmitError(str(ex))
        except Exception as ex:
            # Handle non-requests exception as unexpected.
            raise CircuitSubmitError(str(ex))

        # Create a Job for the circuit.
        try:
            job = CircuitJob(backend=None,
                             job_id=response['id'],
                             api=self.client,
                             creation_date=response['creationDate'],
                             api_status=response['status'],
                             use_websockets=True)
        except Exception as ex:
            raise CircuitResultError(str(ex))

        # Wait for the job to complete, explicitly checking for errors.
        job._wait_for_completion()
        if job.status() is JobStatus.ERROR:
            raise CircuitResultError(
                'Job {} finished with an error'.format(job.job_id()))

        return job.result()

    def graph_state(self, number_of_qubits, adjacency_matrix, angles):
        """Execute the graph state Circuit.

        This circuit implements graph state circuits that are measured in a
        product basis. Measurement angles can be chosen to measure graph state
        stabilizers (for validation/characterization) or to measure in a basis
        such that the circuit family may be hard to classically simulate.

        Args:
            number_of_qubits (int): number of qubits to use, in the 2-20 range.
            adjacency_matrix (list[list]): square matrix of elements whose
                values are 0 or 1. The matrix size is `number_of_qubits` by
                `number_of_qubits` and is expected to be symmetric and have
                zeros on the diagonal.
            angles (list[float]): list of phase angles, each in the interval
                `[0, 2*pi)` radians. There should be 3 * number_of_qubits
                elements in the array. The first three elements are the
                theta, phi, and lambda angles, respectively, of a u3 gate
                acting on the first qubit. Each of the number_of_qubits triples
                is interpreted accordingly as the parameters of a u3 gate
                acting on subsequent qubits.

        Returns:
            Result: the result of executing the circuit.

        Raises:
            CircuitError: if the parameters are not valid.
        """
        if not 2 <= number_of_qubits <= 20:
            raise CircuitError('Invalid number_of_qubits')
        if len(angles) != number_of_qubits*3:
            raise CircuitError('Invalid angles length')

        return self._call_circuit(name=GRAPH_STATE,
                                  number_of_qubits=number_of_qubits,
                                  adjacency_matrix=adjacency_matrix,
                                  angles=angles)

    def hardware_efficient(self, number_of_qubits, angles):
        """Execute the hardware efficient Circuit.

        This circuit implements the random lattice circuit across a user
        specified number of qubits and phase angles.

        Args:
            number_of_qubits (int): number of qubits to use, in the 2-20 range.
            angles (list): array of three phase angles (x/y/z) each from
                0 to 2*Pi, one set for each qubit of each layer of the lattice.
                There should be 3 * number_of_qubits * desired lattice depth
                entries in the array.

        Returns:
            Result: the result of executing the circuit.

        Raises:
            CircuitError: if the parameters are not valid.
        """
        if not 2 <= number_of_qubits <= 20:
            raise CircuitError('Invalid number_of_qubits')
        if len(angles) % 3*number_of_qubits != 0:
            raise CircuitError('Invalid angles length')

        return self._call_circuit(name=HARDWARE_EFFICIENT,
                                  number_of_qubits=number_of_qubits,
                                  angles=angles)

    def random_uniform(self, number_of_qubits=None):
        """Execute the random uniform Circuit.

        This circuit implements hadamard gates across all available qubits on
        the device.

        Args:
            number_of_qubits (int) : optional argument for number of qubits to
                use. If not specified will use all qubits on device.

        Returns:
            Result: the result of executing the circuit.
        """
        kwargs = {}
        if number_of_qubits is not None:
            kwargs['number_of_qubits'] = number_of_qubits

        return self._call_circuit(name=RANDOM_UNIFORM, **kwargs)
