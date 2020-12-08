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

"""REST adaptors for communicating with the IBM Quantum Experience services.

Each adaptor handles a specific endpoint prefix followed by the base URL. The
Job adaptor, for example, handles all /Jobs/{job id} endpoints.
"""

from .root import Api
from .account import Account
