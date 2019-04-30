# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

import os

from setuptools import setup

requirements = [
    "qiskit-terra>=0.8",
    "requests>=2.19",
    "requests-ntlm>=1.1.0",
    "websockets>=7,<8"
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
    description="Qiskit provider for accesing the quantum devices and "
                "simulators at IBMQ",
    long_description=README,
    long_description_content_type='text/markdown',
    url="https://github.com/Qiskit/qiskit-ibmq-provider",
    author="Qiskit Development Team",
    author_email="qiskit@qiskit.org",
    license="Apache 2.0",
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Scientific/Engineering",
    ],
    keywords="qiskit sdk quantum api ibmq",
    packages=['qiskit.providers.ibmq',
              'qiskit.providers.ibmq.api',
              'qiskit.providers.ibmq.credentials'],
    install_requires=requirements,
    include_package_data=True,
    python_requires=">=3.5"
)
