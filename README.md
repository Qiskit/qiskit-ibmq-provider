# Qiskit IBMQ Provider

[![License](https://img.shields.io/github/license/Qiskit/qiskit-ibmq-provider.svg?style=popout-square)](https://opensource.org/licenses/Apache-2.0)
[![Build Status](https://img.shields.io/travis/com/Qiskit/qiskit-ibmq-provider/master.svg?style=popout-square)](https://travis-ci.com/Qiskit/qiskit-ibmq-provider)
[![](https://img.shields.io/github/release/Qiskit/qiskit-ibmq-provider.svg?style=popout-square)](https://github.com/Qiskit/qiskit-ibmq-provider/releases)
[![](https://img.shields.io/pypi/dm/qiskit-ibmq-provider.svg?style=popout-square)](https://pypi.org/project/qiskit-ibmq-provider/)

Qiskit is an open-source framework for working with noisy intermediate-scale
quantum computers (NISQ) at the level of pulses, circuits, and algorithms.

This module contains a provider that allows accessing the quantum devices and
simulators at the [**IBMQ**](https://www.research.ibm.com/ibm-q/) network.

## Installation

We encourage installing Qiskit via the PIP tool (a python package manager),
which installs all Qiskit elements and components, including this one.

```bash
pip install qiskit
```

PIP will handle all dependencies automatically for us and you will always
install the latest (and well-tested) version.

Alternatively, you can install the IBMQ Provider manually via:

```bash
pip install qiskit-ibmq-provider
```

To install from source, follow the instructions in the
[contribution guidelines](.github/CONTRIBUTING.rst).

## Usage

Once the package is installed, you can access the provider from Qiskit.

### Configure your IBMQ credentials

1. Create an _[IBM Q](https://quantumexperience.ng.bluemix.net) > Account_ if
   you haven't already done so.

2. Get an API token from the IBM Q website under
   _My Account > Advanced > API Token_. 

3. Take your token from step 2, here called `MY_API_TOKEN`, and run:

   ```python
   >>> from qiskit import IBMQ
   >>> IBMQ.save_account('MY_API_TOKEN')
   ```

4. If you have access to the IBM Q Network features, you also need to pass the
   url listed on your IBM Q account page to `save_account`.

After calling `IBMQ.save_account()`, your credentials will be stored on disk.
Once they are stored, at any point in the future you can load and use them
in your program simply via:

```python
>>> from qiskit import IBMQ
>>> IBMQ.load_accounts()
```

For those who do not want to save there credentials to disk please use

```python
>>> from qiskit import IBMQ
>>> IBMQ.enable_account('MY_API_TOKEN')
```

## License

[Apache License 2.0](LICENSE.txt)
