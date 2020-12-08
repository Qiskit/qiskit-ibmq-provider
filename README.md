# Qiskit IBM Quantum Provider

[![License](https://img.shields.io/github/license/Qiskit/qiskit-ibmq-provider.svg?style=popout-square)](https://opensource.org/licenses/Apache-2.0)[![Build Status](https://img.shields.io/travis/com/Qiskit/qiskit-ibmq-provider/master.svg?style=popout-square)](https://travis-ci.com/Qiskit/qiskit-ibmq-provider)[![](https://img.shields.io/github/release/Qiskit/qiskit-ibmq-provider.svg?style=popout-square)](https://github.com/Qiskit/qiskit-ibmq-provider/releases)[![](https://img.shields.io/pypi/dm/qiskit-ibmq-provider.svg?style=popout-square)](https://pypi.org/project/qiskit-ibmq-provider/)

**Qiskit** is an open-source SDK for working with quantum computers at the level of circuits, algorithms, and application modules.

This module contains a provider that allows accessing the **[IBM Quantum]**
systems and simulators.

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

## Setting up the IBM Quantum Provider

Once the package is installed, you can access the provider from Qiskit.

> **Note**: Since November 2019 (and with version `0.4` of this
> `qiskit-ibmq-provider` package / version `0.14` of the `qiskit` package)
> legacy Quantum Experience or QConsole (v1) accounts are no longer supported.
> If you are still using a v1 account, please follow the steps described in
> [update instructions](#updating-to-the-new-IBM-Q-Experience) to update your account.

### Configure your IBM Quantum Experience credentials

1. Create an IBM Quantum Experience account or log in to your existing account by visiting
   the [IBM Quantum Experience login page].

2. Copy (and/or optionally regenerate) your API token from your
   [IBM Quantum Experience account page].

3. Take your token from step 2, here called `MY_API_TOKEN`, and run:

   ```python
   from qiskit import IBMQ
   IBMQ.save_account('MY_API_TOKEN')
   ```
   
   The command above stores your credentials locally in a configuration file called `qiskitrc`. 
   By default, this file is located in `$HOME/.qiskit`, where `$HOME` is your home directory. If 
   you are still using `Qconfig.py`, please delete that file and run the command above.  

### Accessing your IBM Quantum Experience backends

After calling `IBMQ.save_account()`, your credentials will be stored on disk.
Once they are stored, at any point in the future you can load and use them
in your program simply via:

```python
from qiskit import IBMQ

provider = IBMQ.load_account()
backend = provider.get_backend('ibmq_qasm_simulator')
```

Alternatively, if you do not want to save your credentials to disk and only
intend to use them during the current session, you can use:

```python
from qiskit import IBMQ

provider = IBMQ.enable_account('MY_API_TOKEN')
backend = provider.get_backend('ibmq_qasm_simulator')
```

By default, all IBM Quantum Experience accounts have access to the same, open project
(hub: `ibm-q`, group: `open`, project: `main`). For convenience, the
`IBMQ.load_account()` and `IBMQ.enable_account()` methods will return a provider
for that project. If you have access to other projects, you can use:

```python
provider_2 = IBMQ.get_provider(hub='MY_HUB', group='MY_GROUP', project='MY_PROJECT')
```

## Updating to the new IBM Quantum Experience

Since November 2019 (and with version `0.4` of this `qiskit-ibmq-provider`
package), the IBM Quantum Provider only supports the new [IBM Quantum Experience], dropping
support for the legacy Quantum Experience and Qconsole accounts. The new IBM Quantum
Experience is also referred as `v2`, whereas the legacy one and Qconsole as `v1`.

This section includes instructions for updating your accounts and programs.
Please note that:
  * the IBM Quantum Experience `v1` credentials and the programs written for pre-0.3
    versions will still be working during the `0.3.x` series. From 0.4 onwards,
    only `v2` credentials are supported, and it is recommended to upgrade
    in order to take advantage of the new features.
  * updating your credentials to the IBM Quantum Experience `v2` implies that you
    will need to update your programs. The sections below contain instructions
    on how to perform the transition.

### Updating your IBM Quantum Experience credentials

If you have credentials for the legacy Quantum Experience or Qconsole stored in
disk, you can make use of `IBMQ.update_account()` helper. This helper will read
your current credentials stored in disk and attempt to convert them:

```python
from qiskit import IBMQ

IBMQ.update_account()
```

```
Found 2 credentials.
The credentials stored will be replaced with a single entry with token "MYTOKEN"
and the new IBM Quantum Experience v2 URL (https://auth.quantum-computing.ibm.com/api).

In order to access the provider, please use the new "IBMQ.get_provider()" methods:

  provider0 = IBMQ.load_account()
  provider1 = IBMQ.get_provider(hub='A', group='B', project='C')

Note you need to update your programs in order to retrieve backends from a
specific provider directly:

  backends = provider0.backends()
  backend = provider0.get_backend('ibmq_qasm_simulator')

Update the credentials? [y/N]
```

Upon confirmation, your credentials will be overwritten with a valid IBM Quantum
Experience v2 set of credentials. For more complex cases, consider deleting your
previous credentials via `IBMQ.delete_accounts()` and follow the instructions
in the [IBM Quantum Experience account page].

### Updating your programs

The new IBM Quantum Experience support also introduces a more structured approach for accessing backends.
Previously, access to all backends was centralized through:

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

In addition, since the new IBM Quantum Experience provides only one set of
credentials, the account management methods in IBMQ are now in singular form.
For example, you should use `IBMQ.load_account()` instead of
`IBMQ.load_accounts()`. An `IBMQAccountError` exception is raised if you
attempt to use the legacy methods with an IBM Quantum Experience v2 account.

The following tables contains a quick reference for the differences between the
two versions. Please refer to the documentation of each method for more in
depth details:

### Account management

| &lt;0.3 / v1 credentials | &gt;=0.3 and v2 credentials |
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

| &lt;0.3 / v1 credentials | &gt;=0.3 and v2 credentials |
| --- | --- |
| N/A | `providers = IBMQ.providers()` |
| `backend = IBMQ.get_backend(name, hub='HUB')` | `provider = IBMQ.get_provider(hub='HUB')` |
|                                           | `backend = provider.get_backend(name)` |
| `backends = IBMQ.backends(hub='HUB')` | `provider = IBMQ.get_provider(hub='HUB')` |
|                                       | `backends = provider.backends()` |


## Contribution Guidelines

If you'd like to contribute to IBM Quantum Provider, please take a look at our
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

The Qiskit IBM Quantum Provider is the work of [many people] who contribute to the
project at different levels. If you use Qiskit, please cite as per the included
[BibTeX file].

## License

[Apache License 2.0].


[IBM Quantum]: https://www.research.ibm.com/ibm-q/
[IBM Quantum Experience]: https://quantum-computing.ibm.com
[IBM Quantum Experience login page]:  https://quantum-computing.ibm.com/login
[IBM Quantum Experience account page]: https://quantum-computing.ibm.com/account
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
