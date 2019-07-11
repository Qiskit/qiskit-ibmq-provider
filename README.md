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

> **Note**: Since July 2019 (and with version `0.3` of this
> `qiskit-ibmq-provider` package / version `0.11` of the `qiskit` package),
> using the new IBM Q Experience (v2) is the default behavior. If you have
> been using an account for the legacy Quantum Experience or QConsole (v1),
> please check the [update instructions](#updating-to-the-new-IBM-Q-Experience).

### Configure your IBMQ credentials

1. Create an IBM Q account or log in to your existing account by visiting
   the [IBM Q Experience login page].

2. Copy (and/or optionally regenerate) your API token from your
   [IBM Q Experience account page].

3. Take your token from step 2, here called `MY_API_TOKEN`, and run:

   ```python
   from qiskit import IBMQ
   IBMQ.save_account('MY_API_TOKEN')
   ```

### Accessing your IBMQ backends

After calling `IBMQ.save_account()`, your credentials will be stored on disk.
Once they are stored, at any point in the future you can load and use them
in your program simply via:

```python
from qiskit import IBMQ

provider = IBMQ.load_account()
provider.get_backend('ibmq_qasm_simulator')
```

Alternatively, if you do not want to save your credentials to disk and only
intend to use them during the current session, you can use:

```python
from qiskit import IBMQ

provider = IBMQ.enable_account('MY_API_TOKEN')
provider.get_backend()
```

By default, all IBM Q accounts have access to the same, open project
(hub: `ibm-q`, group: `open`, project: `main`). For convenience, the
`IBMQ.load_account()` and `IBMQ.enable_account()` methods will return a provider
for that project. If you have access to other projects, you can use:

```python
provider_2 = IBMQ.get_provider(hub='MY_HUB', group='MY_GROUP', project='MY_PROJECT')
```

## Updating to the new IBM Q Experience

Since July 2019 (and with version `0.3` of this `qiskit-ibmq-provider` package),
the IBMQProvider defaults to using the new [IBM Q Experience], which supersedes
the legacy Quantum Experience and Qconsole. The new IBM Q Experience is also
referred as `v2`, whereas the legacy one and Qconsole as `v1`.

This section includes instructions for updating your accounts and programs.

### Updating your IBM Q Experience credentials

If you have credentials for the legacy Quantum Experience or Qconsole stored in
disk, you can make use of `IBMQ.update_account()` helper. This helper will read
your current credentials stored in disk and attempt to convert them:

```python
from qiskit import IBMQ

IBMQ.update_account()
```

```
Found 2 credentials.
The credentials stored will be replaced with a single entry with token "MYTOKEN" and the new IBM Q Experience v2 URL.

In order to access the provider, please use the new "IBMQ.get_provider()" methods:

  provider0 = IBMQ.load_account()
  provider1 = IBMQ.get_provider(hub='A', group='B', project='C')
  backends = provider0.backends()

Update the credentials? [y/N]
```

Upon confirmation, your credentials will be overwritten with a valid IBM Q
Experience set of credentials. For more complex cases, consider deleting your
previous credentials via `IBMQ.delete_accounts()` and follow the instructions
in the [IBM Q Experience account page].

### Updating your programs

With the introduction of support for the new IBM Q Experience support, a more
structured approach for accessing backends has been introduced. Previously,
access to all backends was centralized through:

```python
IBMQ.backends()
IBMQ.get_backend('ibmq_qasm_simulator')
```

In version `0.3` onwards, the preferred way to access the backends is via a
`Provider` for one of your projects instead of via the global `IBMQ` instance
directly, allowing for more granular control over
the project you are using:

```python
my_provider = IBMQ.get_provider()
my_provider.backends()
my_provider.get_backend('ibmq_qasm_simulator')
```

In a similar spirit, you can check the providers that you have access to via:
```python
IBMQ.providers()
```

In addition, since the new IBM Q Experience provides only one set of
credentials, the account management methods in IBMQ are now in singular form.
For example, you should use `IBMQ.load_account()` instead of
`IBMQ.load_accounts()`. An `IBMQAccountError` exception is raised if you
attempt to use the legacy methods with an IBM Q Experience v2 account.

The following tables contains a quick reference for the differences between the
two versions. Please refer to the documentation of each method for more in
depth details:

### Account management

| &lt;0.3 | &gt;=0.3 |
| --- | --- |
| N/A | `IBMQ.update_account()` |
| `IBMQ.save_account(token, url)` | `IBMQ.save_account(token)`
| `IBMQ.load_accounts()` | `provider = IBMQ.load_account()`
| `IBMQ.enable_account()` | `provider = IBMQ.enable_account()`
| `IBMQ.disable_accounts()` | `IBMQ.disable_account()`
| `IBMQ.active_accounts()` | `IBMQ.active_account()`
| `IBMQ.stored_accounts()` | `IBMQ.stored_account()`
| `IBMQ.delete_accounts()` | `IBMQ.delete_account()`

### Using backends

| &lt;0.3 | &gt;=0.3 |
| --- | --- |
| N/A | `providers = IBMQ.providers()` |
| `backend = IBMQ.get_backend(name, hub='HUB')` | `provider = IBMQ.get_provider(hub='HUB')` |
|                                           | `backend = provider.get_backend(name)` |
| `backends = IBMQ.backends(hub='HUB')` | `provider = IBMQ.get_provider(hub='HUB')` |
|                                       | `backends = provider.backends()` |


## Contribution Guidelines

If you'd like to contribute to IBM Q provider, please take a look at our
[contribution guidelines]. This project adheres to Qiskit's [code of conduct].
By participating, you are expect to uphold to this code.

We use [GitHub issues] for tracking requests and bugs. Please use our [slack]
for discussion and simple questions. To join our Slack community use the
invite link at [Qiskit.org]. For questions that are more suited for a forum we
use the `Qiskit` tag in [Stack Exchange].

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
[IBM Q Experience]: https://quantum-computing.ibm.com
[IBM Q Experience login page]:  https://quantum-computing.ibm.com/login
[IBM Q Experience account page]: https://quantum-computing.ibm.com/account
[contribution guidelines]: https://github.com/Qiskit/qiskit-ibmq-provider/blob/master/CONTRIBUTING.md
[code of conduct]: https://github.com/Qiskit/qiskit-ibmq-provider/blob/master/CODE_OF_CONDUCT.md
[GitHub issues]: https://github.com/Qiskit/qiskit-ibmq-provider/issues
[slack]: https://qiskit.slack.com
[Qiskit.org]: https://qiskit.org
[Stack Exchange]: https://quantumcomputing.stackexchange.com/questions/tagged/qiskit
[Qiskit Tutorial]: https://github.com/Qiskit/qiskit-tutorial
[many people]: https://github.com/Qiskit/qiskit-ibmq-provider/graphs/contributors
[BibTeX file]: https://github.com/Qiskit/qiskit/blob/master/Qiskit.bib
[Apache License 2.0]: https://github.com/Qiskit/qiskit-ibmq-provider/blob/master/LICENSE.txt
