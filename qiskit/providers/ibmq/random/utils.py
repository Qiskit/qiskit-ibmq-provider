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

"""Module for utility functions."""

from typing import List

import numpy as np


def bytes_to_bitarray(the_bytes: bytes, num_bits: int) -> List[int]:
    """Convert input bytes into an array of bits.

    Args:
        the_bytes: Bytes to be converted.
        num_bits: Number of bits to return.

    Returns:
        An array of bits.
    """
    return [(the_bytes[i >> 3] >> (i & 7)) & 1 for i in range(num_bits)]


def bitarray_to_bytes(bitarray: List[int]) -> bytes:
    """Convert an array of bits to bytes.

    Args:
        bitarray: Bit array to be converted.

    Returns:
        Input array in bytes.
    """
    n_bits = len(bitarray)
    n_bytes = (n_bits + 7) >> 3
    int_array = [0] * n_bytes
    for i in range(n_bits):
        int_array[i >> 3] |= bitarray[i] << (i & 7)
    return bytes(int_array)


def generate_wsr(num_bits: int) -> List:
    """Generate a list of WSR bits.

    Args:
        num_bits: Number of bits needed.

    Returns:
        A list of random binary numbers.
    """
    return list(np.random.randint(2, size=num_bits))
