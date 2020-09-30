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

from .utils import generate_wsr, bitarray_to_bytes
from .baserandomservice import BaseRandomService
from .cqcextractorjob import CQCExtractorJob

logger = logging.getLogger(__name__)


class CQCExtractor(BaseRandomService):
    """Class for interfacing with a CQC remote extractor.

    There are two extractor methods - Dodis (extractor 1) and Hayashi (extractor 2).
    These methods can be invoked synchronously or asynchronously.
    To invoke them synchronously::

        random_bits = extractor.run(*cqc_parameters)

    To invoke them asynchronously::

        import numpy as np
        extractor1_out = extractor.run_async_ext1(*ext1_parameters).block_until_ready()
        extractor2_out = extractor.run_async_ext2(
            ext2_seed=extractor1_out, *ext2_parameters).block_until_ready()
        random_bits = np.append(extractor1_out, extractor2_out)

    Running them asynchronously takes more steps because extractor 2 uses the
    output of extractor 1 as its seed, so it must wait for extractor 1 to finish first.
    """

    def run(
            self,
            ext1_input_num_bits: int,
            ext1_output_num_bits: int,
            ext1_raw_bytes: bytes,
            ext1_wsr_bytes: bytes,
            ext2_seed_num_bits: int,
            ext2_wsr_multiplier: int,
            ext2_wsr_generator: Optional[Callable] = None) -> List[int]:
        """Process input data synchronously.

        Args:
            ext1_input_num_bits: Number of input bits, for extractor 1.
            ext1_output_num_bits: Number of output bits, for extractor 1.
            ext1_raw_bytes: Initial random numbers, in bytes, for extractor 1.
            ext1_wsr_bytes: Initial WSRs, in bytes, for extractor 1.
            ext2_seed_num_bits: Number of bits in the seed, for extractor 2.
            ext2_wsr_multiplier: WSR multiplier, for extractor 2. The number of
                bits used by extractor 2 is ext2_seed_num_bits*ext2_wsr_multiplier.
            ext2_wsr_generator: WSR generator used for extractor 2. It must take the
                number of bits as the input and a list of random bits (0s and 1s)
                as the output. If ``None``, :func:``generate_wsr`` is used.

        Returns:
            An instance of ``CQCExtractorJob`` which can be used to retrieve the
            results later.
        """
        # pylint: disable=arguments-differ
        # Run ext1
        output = self.run_async_ext1(ext1_input_num_bits, ext1_output_num_bits,
                                     ext1_raw_bytes, ext1_wsr_bytes).block_until_ready()

        # Run ext2 if requested.
        if ext2_wsr_multiplier != 0:
            ext2_out = self.run_async_ext2(
                output, ext2_seed_num_bits, ext2_wsr_multiplier,
                ext2_wsr_generator).block_until_ready()

            output = np.append(output, ext2_out).tolist()
        return output

    def run_async_ext1(
            self,
            ext1_input_num_bits: int,
            ext1_output_num_bits: int,
            ext1_raw_bytes: bytes,
            ext1_wsr_bytes: bytes
    ) -> CQCExtractorJob:
        """Run the first extractor asynchronously.

        Args:
            ext1_input_num_bits: Number of input bits, for extractor 1.
            ext1_output_num_bits: Number of output bits, for extractor 1.
            ext1_raw_bytes: Initial random numbers, in bytes, for extractor 1.
            ext1_wsr_bytes: Initial WSRs, in bytes, for extractor 1.

        Returns:
            An instance of ``CQCExtractorJob`` which can be used to retrieve the
            results later.

        Raises:
            ValueError: If an invalid argument values are specified.
        """
        if not ext1_input_num_bits or not ext1_output_num_bits:
            raise ValueError("Invalid input arguments. ext1_input_num_bits and "
                             "ext1_output_num_bits must be non-zero.")

        logger.info("Starting first extraction.")
        # Run ext1
        ext1_data = {"n": ext1_input_num_bits,
                     "m": ext1_output_num_bits}
        ext1_files = {"x": ext1_raw_bytes,
                      "y": ext1_wsr_bytes}
        response = self._client.extract(
            name='cqc', method='ext1', data=ext1_data, files=ext1_files)
        parameters = {'ext1_input_num_bits': ext1_input_num_bits,
                      'ext1_output_num_bits': ext1_output_num_bits,
                      'ext1_raw_bytes': ext1_raw_bytes,
                      'ext1_wsr_bytes': ext1_wsr_bytes}
        return CQCExtractorJob(job_id=response['id'], client=self._client, parameters=parameters)

    def run_async_ext2(
            self,
            ext2_seed: List[int],
            ext2_seed_num_bits: int,
            ext2_wsr_multiplier: int,
            ext2_wsr_generator: Optional[Callable] = None
    ) -> CQCExtractorJob:
        """Run the second extractor asynchronously.

        Args:
            ext2_seed: Seed used for extractor 2, such as the output of extractor 1.
            ext2_seed_num_bits: Number of bits in the seed, for extractor 2.
            ext2_wsr_multiplier: WSR multiplier, for extractor 2. The number of
                bits used by extractor 2 is ext2_seed_num_bits*ext2_wsr_multiplier.
            ext2_wsr_generator: WSR generator used for extractor 2. It must take the
                number of bits as the input and a list of random bits (0s and 1s)
                as the output. If ``None``, :func:``generate_wsr`` is used.

        Returns:
            An instance of ``CQCExtractorJob`` which can be used to retrieve the
            results later.

        Raises:
            ValueError: If an invalid argument values are specified.
        """
        if not ext2_seed_num_bits or not ext2_wsr_multiplier:
            raise ValueError("Invalid input arguments. ext2_seed_num_bits and "
                             "ext2_wsr_multiplier must be non-zero.")

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
        response = self._client.extract(name='cqc', method='ext2',
                                        data=ext2_data, files=ext2_files)
        parameters = {'ext2_seed_num_bits': ext2_seed_num_bits,
                      'ext2_wsr_multiplier': ext2_wsr_multiplier,
                      'ext2_seed_bytes': ext2_seed,
                      'ext2_wsr': ext2_wsr}
        return CQCExtractorJob(job_id=response['id'], client=self._client, parameters=parameters)

    def retrieve_job(self, job_id: str) -> CQCExtractorJob:
        """Retrieve a previously submitted job.

        Args:
            job_id: Job ID.

        Returns:
            A ``CQCExtractorJob`` instance.
        """
        return CQCExtractorJob(job_id, self._client)

    def __repr__(self):
        return "<{}('{}') from {}>".format(self.__class__.__name__,
                                           self.name,
                                           self._provider)
