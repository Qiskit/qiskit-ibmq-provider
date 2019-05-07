# Qiskit IBMQ Provider

[![License](https://img.shields.io/github/license/Qiskit/qiskit-ibmq-provider.svg?style=popout-square)](https://opensource.org/licenses/Apache-2.0)[![Build Status](https://img.shields.io/travis/com/Qiskit/qiskit-ibmq-provider/master.svg?style=popout-square)](https://travis-ci.com/Qiskit/qiskit-ibmq-provider)[![](https://img.shields.io/github/release/Qiskit/qiskit-ibmq-provider.svg?style=popout-square)](https://github.com/Qiskit/qiskit-ibmq-provider/releases)[![](https://img.shields.io/pypi/dm/qiskit-ibmq-provider.svg?style=popout-square)](https://pypi.org/project/qiskit-ibmq-provider/)

Qiskit is an open-source framework for working with noisy intermediate-scale
quantum computers (NISQ) at the level of pulses, circuits, and algorithms.

This module contains a provider that allows accessing the **[IBM Q]** quantum
devices and simulators.

## Installation

We encourage installing Qiskit via the PIP tool (a python package manager),
which installs all Qiskit elements and components, including this one.

```bash
pip install qiskit
```

PIP will handle all dependencies automatically for us and you will always
install the latest (and well-tested) version.

To install from source, follow the instructions in the
[contribution guidelines].

## Setting up the IBMQ provider

Once the package is installed, you can access the provider from Qiskit.

### Configure your IBMQ credentials

> **Note**: since `IBMQProvider` version `0.2.0`, the package supports
> connecting to [the new IBM Q Experience], which includes a number of new
> features. Please note that support is still experimental, and some
> functionality might be subject to change or experience technical issues.

1. Create an [IBM Q account] if you haven't already done so.

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

## Contribution Guidelines

If you'd like to contribute to IBM Q provider, please take a look at our
[contribution guidelines]. This project adheres to Qiskit's [code of conduct].
By participating, you are expect to uphold to this code.

We use [GitHub issues] for tracking requests and bugs. Please use our [slack]
for discussion and simple questions. To join our Slack community use the
[invite link]. For questions that are more suited for a forum we use the
`Qiskit` tag in [Stack Exchange].

## Next Steps

Now you're set up and ready to check out some of the other examples from our
[Qiskit Tutorial] repository.

## Authors and Citation

The Qiskit IBM Q provider is the work of [many people] who contribute to the
project at different levels. If you use Qiskit, please cite as per the included
[BibTeX file].

## License

[Apache License 2.0].


[IBM Q]: https://www.research.ibm.com/ibm-q/
[IBM Q account]: https://quantumexperience.ng.bluemix.net
[contribution guidelines]: https://github.com/Qiskit/qiskit-ibmq-provider/blob/master/.github/CONTRIBUTING.rst
[code of conduct]: https://github.com/Qiskit/qiskit-ibmq-provider/blob/master/.github/CODE_OF_CONDUCT.rst
[GitHub issues]: https://github.com/Qiskit/qiskit-ibmq-provider/issues
[slack]: https://qiskit.slack.com
[invite link]: https://join.slack.com/t/qiskit/shared_invite/enQtNDc2NjUzMjE4Mzc0LTMwZmE0YTM4ZThiNGJmODkzN2Y2NTNlMDIwYWNjYzA2ZmM1YTRlZGQ3OGM0NjcwMjZkZGE0MTA4MGQ1ZTVmYzk
[Stack Exchange]: https://quantumcomputing.stackexchange.com/questions/tagged/qiskit
[Qiskit Tutorial]: https://github.com/Qiskit/qiskit-tutorial
[many people]: https://github.com/Qiskit/qiskit-terra/graphs/contributors
[BibTeX file]: https://github.com/Qiskit/qiskit/blob/master/Qiskit.bib
[Apache License 2.0]: https://github.com/Qiskit/qiskit-ibmq-provider/blob/master/LICENSE.txt
[the new IBM Q Experience]: https://quantum-computing.ibm.com/
