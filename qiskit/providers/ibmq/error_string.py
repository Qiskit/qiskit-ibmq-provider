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

"""A subclass of string that allows for linking out to solutions on IBM Quantum cloud"""

import re

HTML_STR = """
<style>
.button {
  border: none;
  color: white;
  padding: 8px 16px;
  text-align: center;
  text-decoration: none;
  display: inline-block;
  font-size: 14px;
  margin: 4px 2px;
  transition-duration: 0.2s;
  cursor: pointer;
}
.iqx-button {
  background-color: #0f62fe;
  color: white;
}
.iqx-button:hover {
  background-color: #0043ce;
  color: white;
}
</style>
<a href="%s" target='_blank'><button class='button iqx-button'>Go to solution #%s</button></a>
"""

URL = 'https://quantum-computing.ibm.com/docs/manage/errors#error'


class IBMQErrorString(str):
    """A subclass of str that displays a button in jupyter
    that takes me to the solution of the error message.
    """
    def _repr_html_(self):
        # pylint: disable=import-outside-toplevel
        from IPython.display import HTML, display
        error_msg = self.__str__()
        match = re.search(r'\d{4}', error_msg)
        if match:
            error_code = match.group()
            html_str = HTML_STR % (URL+error_code, error_code)
            html = HTML(html_str)
            display(html)
