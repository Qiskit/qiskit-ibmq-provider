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

"""Error handling routines"""
import sys

#pylint: disable=simplifiable-if-statement
if ('ipykernel' in sys.modules) and ('spyder' not in sys.modules):
    from ..jupyter.exceptions import exception_widget
    HAS_JUPYTER = True
else:
    HAS_JUPYTER = False

def raise_pretty(error: Exception) -> None:
    """A custom handler of exceptions.

    Allows for pretty formatting of exceptions
    in Jupyter notebooks if Theia is installed.

    Args:
        error: The input exception.

    Example:
        .. jupyter-execute::

            from qiskit.providers.ibmq.utils import raise_pretty

            raise_pretty(TypeError('Your not my type.'))
    """
    if HAS_JUPYTER:
        exception_widget(error)
    else:
        raise error
