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

"""Module for interfacing with a remote extractor."""

import logging
from typing import Optional, Callable, List

import numpy as np

from .utils import generate_wsr, bytes_to_bitarray, bitarray_to_bytes
from .baserandomservice import BaseRandomService

logger = logging.getLogger(__name__)


class CQCExtractor(BaseRandomService):
    """Class for interfacing with a CQC remote extractor."""

    def run(
            self,
            ext1_in_num_bits: int,
            ext1_out_num_bits: int,
            ext1_raw_bytes: bytes,
            ext1_wsr_bytes: bytes,
            ext2_seed_num_bits: int,
            ext2_wsr_multiplier: int,
            ext2_wsr_generator: Optional[Callable] = None) -> List[int]:
        """Process input data synchronously.

        Args:
            ext1_in_num_bits: Number of input bits, for extractor 1.
            ext1_out_num_bits: Number of output bits, for extractor 1.
            ext1_raw_bytes: Initial random numbers, in bytes, for extractor 1.
            ext1_wsr_bytes: Initial WSRs, in bytes, for extractor 1.
            ext2_seed_num_bits: Number of bits in the seed, for extractor 2.
            ext2_wsr_multiplier: WSR multiplier, for extractor 2. The number of
                bits used by extractor 2 is ext2_seed_num_bits*ext2_wsr_multiplier.
            ext2_wsr_generator: WSR generator used for extractor 2. It must take the
                number of bits as the input and a list of random bits (0s and 1s)
                as the output. If ``None``, :func:``generate_wsr`` is used.

        Returns:
            Extracted random bits.
        """
        # pylint: disable=arguments-differ
        logger.info("Starting first extraction.")
        # Run ext1
        output = self.run_ext1(ext1_in_num_bits, ext1_out_num_bits,
                               ext1_raw_bytes, ext1_wsr_bytes)

        # Run ext2 if requested.
        if ext2_wsr_multiplier != 0:
            ext2_out = self.run_ext2(output, ext2_seed_num_bits,
                                     ext2_wsr_multiplier, ext2_wsr_generator)

            output = np.append(output, ext2_out)
        return output

    def run_ext1(
            self,
            ext1_in_num_bits: int,
            ext1_out_num_bits: int,
            ext1_raw_bytes: bytes,
            ext1_wsr_bytes: bytes,
    ) -> List[int]:
        """Run the first extractor synchronously.

        Args:
            ext1_in_num_bits: Number of input bits, for extractor 1.
            ext1_out_num_bits: Number of output bits, for extractor 1.
            ext1_raw_bytes: Initial random numbers, in bytes, for extractor 1.
            ext1_wsr_bytes: Initial WSRs, in bytes, for extractor 1.

        Returns:
            Extracted random bits.
        """
        logger.info("Starting first extraction.")
        # Run ext1
        ext1_data = {"n": ext1_in_num_bits,
                     "m": ext1_out_num_bits}
        ext1_files = {"x": ext1_raw_bytes,
                      "y": ext1_wsr_bytes}
        raw_data = self._client.extract(name='cqc', method='ext1', data=ext1_data, files=ext1_files)
        return bytes_to_bitarray(raw_data, ext1_out_num_bits)

    def run_ext2(
            self,
            ext2_seed: List[int],
            ext2_seed_num_bits: int,
            ext2_wsr_multiplier: int,
            ext2_wsr_generator: Optional[Callable] = None
    ) -> List[int]:
        """Run the second extractor synchronously.

        Args:
            ext2_seed: Seed used for extractor 2, such as the output of extractor 1.
            ext2_seed_num_bits: Number of bits in the seed, for extractor 2.
            ext2_wsr_multiplier: WSR multiplier, for extractor 2. The number of
                bits used by extractor 2 is ext2_seed_num_bits*ext2_wsr_multiplier.
            ext2_wsr_generator: WSR generator used for extractor 2. It must take the
                number of bits as the input and a list of random bits (0s and 1s)
                as the output. If ``None``, :func:``generate_wsr`` is used.

        Returns:
            Extracted random bits.
        """
        logger.info("Starting second extraction.")
        ext2_seed = bitarray_to_bytes(ext2_seed[:ext2_seed_num_bits])
        if ext2_wsr_generator is None:
            ext2_wsr_generator = generate_wsr
        ext2_wsr = ext2_wsr_generator(ext2_seed_num_bits*ext2_wsr_multiplier)
        ext2_wsr = bitarray_to_bytes(ext2_wsr)
        ext2_data = {"a": ext2_seed_num_bits,
                     "b": ext2_wsr_multiplier}
        ext2_files = {"r": ext2_seed,
                      "x": ext2_wsr}
        raw_data = self._client.extract(name='cqc', method='ext2', data=ext2_data, files=ext2_files)
        return bytes_to_bitarray(raw_data, (ext2_wsr_multiplier-1)*ext2_seed_num_bits)

    def __repr__(self):
        return "<{}('{}') from {}>".format(self.__class__.__name__,
                                           self.name,
                                           self._provider)
