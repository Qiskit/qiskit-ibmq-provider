# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2018.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import os

from setuptools import setup

REQUIREMENTS = [
    "qiskit-terra>=0.18.0",
    "requests>=2.19",
    "requests-ntlm>=1.1.0",
    "numpy>=1.13",
    "urllib3>=1.21.1",
    "python-dateutil>=2.8.0",
    "websocket-client>=1.0.1"
]

# Handle version.
VERSION_PATH = os.path.join(os.path.dirname(__file__),
                            "qiskit", "providers", "ibmq", "VERSION.txt")
with open(VERSION_PATH, "r") as version_file:
    VERSION = version_file.read().strip()

# Read long description from README.
README_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                           'README.md')
with open(README_PATH) as readme_file:
    README = readme_file.read()


setup(
    name="qiskit-ibmq-provider",
    version=VERSION,
    description="Qiskit provider for accessing the quantum devices and "
                "simulators at IBMQ",
    long_description=README,
    long_description_content_type='text/markdown',
    url="https://github.com/Qiskit/qiskit-ibmq-provider",
    author="Qiskit Development Team",
    author_email="hello@qiskit.org",
    license="Apache 2.0",
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Scientific/Engineering",
    ],
    keywords="qiskit sdk quantum api ibmq",
    packages=['qiskit.providers.ibmq',
              'qiskit.providers.ibmq.api',
              'qiskit.providers.ibmq.api.clients',
              'qiskit.providers.ibmq.api.rest',
              'qiskit.providers.ibmq.api.rest.utils',
              'qiskit.providers.ibmq.credentials',
              'qiskit.providers.ibmq.job',
              'qiskit.providers.ibmq.managed',
              'qiskit.providers.ibmq.utils',
              'qiskit.providers.ibmq.visualization',
              'qiskit.providers.ibmq.visualization.interactive',
              'qiskit.providers.ibmq.jupyter',
              'qiskit.providers.ibmq.jupyter.dashboard',
              'qiskit.providers.ibmq.random',
              'qiskit.providers.ibmq.experiment',
              'qiskit.providers.ibmq.runtime',
              'qiskit.providers.ibmq.runtime.program'],
    install_requires=REQUIREMENTS,
    include_package_data=True,
    python_requires=">=3.6",
    zip_safe=False,
    extras_require={'visualization': ['matplotlib>=2.1', 'ipywidgets>=7.3.0',
                                      "seaborn>=0.9.0", "plotly>=4.4",
                                      "ipyvuetify>=1.1", "pyperclip>=1.7",
                                      "ipython>=5.0.0", "traitlets!=5.0.5",
                                      "ipyvue>=1.4.1"]},
    project_urls={
        "Bug Tracker": "https://github.com/Qiskit/qiskit-ibmq-provider/issues",
        "Documentation": "https://qiskit.org/documentation/",
        "Source Code": "https://github.com/Qiskit/qiskit-ibmq-provider",
    },
)
