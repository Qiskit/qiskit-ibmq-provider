from qiskit.providers.ibmq.utils.json_encoder import IQXJsonEncoder
from ...ibmqtestcase import IBMQTestCase
from ...decorators import requires_provider

from qiskit import Aer, QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import Parameter


class TestJsonEncoder(IBMQTestCase):
    """Tests for AccountClient."""

    @requires_provider
    def test_exception_message(self, provider):
        """Test executing job with Parameter in methadata."""
        qr = QuantumRegister(1)
        cr = ClassicalRegister(1)
        my_circ_str = 'test_metadata'
        my_circ = QuantumCircuit(qr, cr, name=my_circ_str, metadata={Parameter('φ'): 0.2})
        backend = provider.get_backend('ibmq_bogota')
        backend.run(my_circ, shots=1024)
        # There is no self.assert method because if we cannot pass Parameter as metadata the last line throw:
        # "TypeError: keys must be str, int, float, bool or None, not Parameter"

    def test_encode_no_replace(self):
        """Test encode where there is no invalid key to replace."""
        dir = {
            't1': 1,
            None: None,
            'list': [1, 2, {'ld': 1, 2: 3}]
        }

        self.assertEqual('{"t1": 1, "null": null, "list": [1, 2, {"ld": 1, "2": 3}]}', IQXJsonEncoder().encode(dir))

    def test_encode_replace(self):
        """Test encode where there is no invalid key to replace."""
        dir = {
            't1': 1,
            None: None,
            Parameter('a'): 0.2,
            'list': [1, 2, {'ld': 1, 2: 3, Parameter('alfa'): 0.1}]
        }

        self.assertEqual('{"t1": 1, "null": null, "a": 0.2, "list": [1, 2, {"ld": 1, "2": 3, "alfa": 0.1}]}',
                         IQXJsonEncoder().encode(dir))

