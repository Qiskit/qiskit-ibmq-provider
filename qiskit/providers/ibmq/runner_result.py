# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Circuit-runner result class"""

from typing import List, Union
import json

from qiskit.result import Result, QuasiDistribution
from qiskit.result.postprocess import _hex_to_bin
from qiskit.exceptions import QiskitError

from .runtime import ResultDecoder


class RunnerResult(Result, ResultDecoder):
    """Result class for Qiskit Runtime program circuit-runner."""

    @classmethod
    def decode(cls, data: str) -> 'RunnerResult':
        """Decoding for results from Qiskit runtime jobs."""
        return cls.from_dict(json.loads(data))

    def get_quasiprobabilities(
            self,
            experiment: Union[int, List] = None
    ) -> Union[QuasiDistribution, List[QuasiDistribution]]:
        """Get quasiprobabilites associated with one or more experiments.

        Parameters:
            experiment: Indices of experiments to grab quasiprobabilities from.

        Returns:
            A single distribution or a list of distributions.

        Raises:
            QiskitError: If experiment result doesn't contain quasiprobabilities.
        """
        if experiment is None:
            exp_keys = range(len(self.results))
        else:
            exp_keys = [experiment]  # type: ignore[assignment]

        dict_list = []
        for key in exp_keys:
            if 'quasiprobabilities' in self.data(key).keys():
                shots = self.results[key].shots
                hex_quasi = self.results[key].data.quasiprobabilities
                bit_lenth = len(self.results[key].header.final_measurement_mapping)
                quasi = {}
                for hkey, val in hex_quasi.items():
                    quasi[_hex_to_bin(hkey).zfill(bit_lenth)] = val

                out = QuasiDistribution(quasi, shots)
                out.shots = shots
                dict_list.append(out)
            else:
                raise QiskitError('No quasiprobabilities for experiment "{}"'.format(repr(key)))

        # Return first item of dict_list if size is 1
        if len(dict_list) == 1:
            return dict_list[0]
        else:
            return dict_list
