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

"""Tests for the tutorials, copied from ``qiskit-iqx-tutorials``."""

from unittest import skipIf
import os
import glob
import warnings

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

from qiskit.test.decorators import TEST_OPTIONS
from qiskit.providers.ibmq.utils.utils import to_python_identifier

from ..ibmqtestcase import IBMQTestCase

TUTORIAL_PATH = 'docs/tutorials/**/*.ipynb'


class TutorialsTestCaseMeta(type):
    """Metaclass that dynamically appends a "test_TUTORIAL_NAME" method to the class."""
    def __new__(mcs, name, bases, dict_):

        def create_test(filename):
            """Return a new test function."""
            def test_function(self):
                self._run_notebook(filename)
            return test_function

        tutorials = sorted(glob.glob(TUTORIAL_PATH, recursive=True))

        for filename in tutorials:
            # Add a new "test_file_name_ipynb()" function to the test case.
            test_name = "test_%s" % to_python_identifier(filename)
            dict_[test_name] = create_test(filename)
            dict_[test_name].__doc__ = 'Test tutorial "%s"' % filename
        return type.__new__(mcs, name, bases, dict_)


@skipIf(not TEST_OPTIONS['run_slow'], 'Skipping slow tests.')
class TestTutorials(IBMQTestCase, metaclass=TutorialsTestCaseMeta):
    """Tests for tutorials."""

    @staticmethod
    def _run_notebook(filename):
        # Create the preprocessor.
        execute_preprocessor = ExecutePreprocessor(timeout=6000, kernel_name='python3')

        # Open the notebook.
        file_path = os.path.dirname(os.path.abspath(filename))
        with open(filename) as file_:
            notebook = nbformat.read(file_, as_version=4)

        with warnings.catch_warnings():
            # Silence some spurious warnings.
            warnings.filterwarnings('ignore', category=DeprecationWarning)
            # Finally, run the notebook.
            execute_preprocessor.preprocess(notebook,
                                            {'metadata': {'path': file_path}})
