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

# pylint: disable=method-hidden

"""Custom JSON encoders."""

import json
from typing import Any
import numpy as np
import dill
import base64

from qiskit.result import Result


class RuntimeEncoder(json.JSONEncoder):
    """JSON Encoder used by runtime service."""

    def default(self, obj: Any) -> Any:
        if hasattr(obj, 'tolist'):
            return {'__type__': 'array', '__value__': obj.tolist()}
        if isinstance(obj, complex):
            return {'__type__': 'complex', '__value__': [obj.real, obj.imag]}
        if isinstance(obj, Result):
            return {'__type__': 'result', '__value__': obj.to_dict()}
        if hasattr(obj, '__class__'):
            encoded = base64.standard_b64encode(dill.dumps(obj))
            return {'__type__': 'dill', '__value__': encoded.decode('utf-8')}

        return super().default(obj)


class RuntimeDecoder(json.JSONDecoder):
    """JSON Decoder used by runtime service."""

    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if '__type__' in obj:
            if obj['__type__'] == 'complex':
                val = obj['__value__']
                return val[0] + 1j * val[1]
            if obj['__type__'] == 'array':
                return np.array(obj['__value__'])
            if obj['__type__'] == 'result':
                return Result.from_dict(obj['__value__'])
            if obj['__type__'] == 'dill':
                decoded = base64.standard_b64decode(obj['__value__'])
                return dill.loads(decoded)
        return obj
