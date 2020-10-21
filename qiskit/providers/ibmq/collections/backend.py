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

"""BackendCollection module
"""

from typing import List
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend


class BackendCollection(list):
    """A list subclass that makes handling IBMQBackends easier.
    """
    def __init__(self, data: List):
        """BackendCollection constructor

        Parameters:
            data: List of IBMQbackend instances
        """
        for dd in data:
            if not isinstance(dd, IBMQBackend):
                raise TypeError('Backend collection requires IBMQBackend instances.')
        super().__init__(data)

    def __and__(self, other):
        return BackendCollection(set(self) & set(other))

    def __or__(self, other):
        return BackendCollection(set(self) | set(other))

    def __add__(self, other):
        """Adds to BackendCollections together.
        """
        if not isinstance(other, (BackendCollection, list)):
            if isinstance(other, list):
                other = BackendCollection(other)
            else:
                raise TypeError('BackendCollection addition works only for collections and lists.')

        return BackendCollection(set(self) | set(other))

    def __radd__(self, other):
        """Adds to BackendCollections together.
        """
        if not isinstance(other, (BackendCollection, list)):
            if isinstance(other, list):
                other = BackendCollection(other)
            else:
                raise TypeError('BackendCollection addition works only for collections and lists.')

        return BackendCollection(set(self) | set(other))

    def __getattr__(self, name):
        if name == 'num_qubits':
            return NumQubits(self)
        elif name == 'simulator':
            return IsSimulator(self)
        elif name == 'real':
            return IsReal(self)
        elif name == 'open_pulse':
            return HasPulse(self)
        elif name == 'quantum_volume':
            return QVCompare(self)
        elif name == 'operational':
            return IsOperational(self)
        else:
            raise AttributeError("BackendCollection does not have attr '{}'.".format(name))


class Comparator(BackendCollection):
    """A skeleton constructor class built on BackendCollection.
    """
    def __eq__(self, other):
        raise Exception('Not implimented')

    def __ne__(self, other):
        raise Exception('Not implimented')

    def __gt__(self, other):
        raise Exception('Not implimented')

    def __ge__(self, other):
        raise Exception('Not implimented')

    def __lt__(self, other):
        raise Exception('Not implimented')

    def __le__(self, other):
        raise Exception('Not implimented')


class IsSimulator(Comparator):
    """Impliments a simulator check.
    """
    def __init__(self, data: List):
        """BackendCollection constructor

        Parameters:
            data: List of IBMQbackend instances
        """
        self._full_data = data
        super().__init__([back for back in data if back.configuration().simulator])

    def __eq__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self._full_data if back.configuration().simulator == other]
        return BackendCollection(out)

    def __ne__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self._full_data if back.configuration().simulator != other]
        return BackendCollection(out)


class IsReal(Comparator):
    """Impliments a real system check.
    """
    def __init__(self, data: List):
        """BackendCollection constructor

        Parameters:
            data: List of IBMQbackend instances
        """
        self._full_data = data
        super().__init__([back for back in data if not back.configuration().simulator])

    def __eq__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self._full_data if back.configuration().simulator != other]
        return BackendCollection(out)

    def __ne__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self._full_data if back.configuration().simulator == other]
        return BackendCollection(out)


class IsOperational(Comparator):
    """Impliments a is operational check.
    """
    def __init__(self, data: List):
        """BackendCollection constructor

        Parameters:
            data: List of IBMQbackend instances
        """
        self._full_data = data
        super().__init__([back for back in data if back.status().operational])

    def __eq__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self._full_data if back.status().operational == other]
        return BackendCollection(out)

    def __ne__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self._full_data if back.status().operational != other]
        return BackendCollection(out)


class HasPulse(Comparator):
    """Impliments a open_pulse check.
    """
    def __init__(self, data: List):
        """BackendCollection constructor

        Parameters:
            data: List of IBMQbackend instances
        """
        self._full_data = data
        super().__init__([back for back in data if back.configuration().open_pulse])

    def __eq__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self if back.configuration().open_pulse == other]
        return BackendCollection(out)

    def __ne__(self, other):
        if (other is not None) and not isinstance(other, (bool, int)):
            raise Exception('Can only compare against boolean and int values.')
        if isinstance(other, int) and other not in [0, 1]:
            raise Exception('Integer comparison must be against 0 or 1.')
        out = [back for back in self if back.configuration().open_pulse != other]
        return BackendCollection(out)


class NumQubits(Comparator):
    """Impliments a number of qubits comparator.
    """
    def __eq__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = [back for back in self if back.configuration().num_qubits == other]
        return BackendCollection(out)

    def __ne__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = [back for back in self if back.configuration().num_qubits != other]
        return BackendCollection(out)

    def __gt__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = [back for back in self if back.configuration().num_qubits > other]
        return BackendCollection(out)

    def __ge__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = [back for back in self if back.configuration().num_qubits >= other]
        return BackendCollection(out)

    def __lt__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = [back for back in self if back.configuration().num_qubits < other]
        return BackendCollection(out)

    def __le__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = [back for back in self if back.configuration().num_qubits <= other]
        return BackendCollection(out)


class QVCompare(Comparator):
    """Impliments a quantum volume comparator.
    """
    def __eq__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = []
        for back in self:
            if hasattr(back.configuration(), 'quantum_volume'):
                qv_val = back.configuration().quantum_volume
                if qv_val and qv_val == other:
                    out.append(back)
        return BackendCollection(out)

    def __ne__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = []
        for back in self:
            if hasattr(back.configuration(), 'quantum_volume'):
                qv_val = back.configuration().quantum_volume
                if qv_val and qv_val != other:
                    out.append(back)
        return BackendCollection(out)

    def __gt__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = []
        for back in self:
            if hasattr(back.configuration(), 'quantum_volume'):
                qv_val = back.configuration().quantum_volume
                if qv_val and qv_val > other:
                    out.append(back)
        return BackendCollection(out)

    def __ge__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = []
        for back in self:
            if hasattr(back.configuration(), 'quantum_volume'):
                qv_val = back.configuration().quantum_volume
                if qv_val and qv_val >= other:
                    out.append(back)
        return BackendCollection(out)

    def __lt__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = []
        for back in self:
            if hasattr(back.configuration(), 'quantum_volume'):
                qv_val = back.configuration().quantum_volume
                if qv_val and qv_val < other:
                    out.append(back)
        return BackendCollection(out)

    def __le__(self, other):
        if not isinstance(other, int):
            raise Exception('Can only compare against ints')
        out = []
        for back in self:
            if hasattr(back.configuration(), 'quantum_volume'):
                qv_val = back.configuration().quantum_volume
                if qv_val and qv_val <= other:
                    out.append(back)
        return BackendCollection(out)
