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

"""Manager for interacting with QCircuits."""

from functools import wraps

from qiskit.providers.ibmq.api_v2.exceptions import RequestsApiError

from ..exceptions import IBMQError


GRAPH_STATE = 'graph_state'
HARDWARE_EFFICIENT = 'hardware_efficient'
RANDOM_UNIFORM = 'random_uniform'


def requires_api_connection(func):
    """Decorator that ensures that a QCircuitsManager has a valid API."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.client:
            raise IBMQError(
                'An account must be loaded in order to use QCircuits')

        return func(self, *args, **kwargs)

    return wrapper


class QcircuitsManager:
    """Class that provides access to the different qcircuits."""
    def __init__(self):
        self.client = None

    def _call_qcircuit(self, name, **kwargs):
        """Execute a Qcircuit.

        Args:
            name (str): name of the Qcircuit.
            **kwargs (dict): parameters passed to the Qcircuit.

        Returns:
            dict: response.

        Raises:
            IBMQError: if the Qcircuit could not be executed.
            RequestsApiError: if the request could not be completed.
        """
        try:
            response = self.client.qcircuit_run(name=name, **kwargs)
        except RequestsApiError as ex:
            # Revise the original requests exception to intercept.
            response = ex.original_exception.response
            if response.status_code == 400:
                if response.json()['error']['code'] == 'HUB_NOT_FOUND':
                    raise IBMQError('Qcircuit support is not available') from None

            raise

        return response

    @requires_api_connection
    def graph_state(self, number_of_qubits, adjacency_matrix, angles):
        """Execute the graph state Qcircuit.

        Args:
            number_of_qubits:
            adjacency_matrix:
            angles:

        Returns:
            dict: response.
        """

        return self._call_qcircuit(name=GRAPH_STATE,
                                   number_of_qubits=number_of_qubits,
                                   adjacency_matrix=adjacency_matrix,
                                   angles=angles)

    @requires_api_connection
    def hardware_efficient(self, number_of_qubits, angles):
        """Execute the hardware efficient Qcircuit.

        Args:
            number_of_qubits:
            angles:

        Returns:
            dict: response.
        """
        return self._call_qcircuit(name=HARDWARE_EFFICIENT,
                                   number_of_qubits=number_of_qubits,
                                   angles=angles)

    @requires_api_connection
    def random_uniform(self, number_of_qubits):
        """Execute the random uniform Qcircuit.

        Args:
            number_of_qubits:

        Returns:
            dict: response
        """
        return self._call_qcircuit(name=RANDOM_UNIFORM,
                                   number_of_qubits=number_of_qubits)
