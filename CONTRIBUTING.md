# Contributing to BitcartCC

Welcome, and thank you for your interest in contributing to BitcartCC!

There are many ways in which you can contribute, beyond writing code. The goal of this document is to provide a high-level overview of how you can get involved.

## Asking Questions

Have a question? Rather than opening an issue, please ask away in our [communities](https://bitcartcc.com#community)

The active community will be eager to assist you. Your well-worded question will serve as a resource to others searching for help.

## Providing Feedback

Your comments and feedback are welcome, and the development team is available via a handful of different channels.

Join our [communities](https://bitcartcc.com#community) to share your thoughts.

## Reporting Issues

Have you identified a reproducible problem in BitcartCC? Have a feature request? We want to hear about it! Here's how you can make reporting your issue as effective as possible.

### Identify Where to Report

The BitcartCC project is distributed across multiple repositories. Try to file the issue against the correct repository. Check the list of [Linked repositories](https://github.com/bitcartcc/bitcart/blob/master/README.md#linked-repositories) if you aren't sure which repo is correct.

If the issue is related to BitcartCC deployment and not to some individual components, or you are not sure, you can open an issue on our [central repository](https://github.com/bitcartcc/bitcart)

### Look For an Existing Issue

Before you create a new issue, please do a search in [open issues](https://github.com/bitcartcc/bitcart/issues) to see if the issue or feature request has already been filed.

Be sure to scan through the [most popular](https://github.com/bitcartcc/bitcart/issues?q=is%3Aopen+is%3Aissue+label%3Afeature-request+sort%3Areactions-%2B1-desc) feature requests.

If you find your issue already exists, make relevant comments and add your [reaction](https://github.com/blog/2119-add-reactions-to-pull-requests-issues-and-comments). Use a reaction in place of a "+1" comment:

* 👍 - upvote
* 👎 - downvote

If you cannot find an existing issue that describes your bug or feature, create a new issue using the guidelines below.

### Writing Good Bug Reports and Feature Requests

File a single issue per problem and feature request. Do not enumerate multiple bugs or feature requests in the same issue.

Do not add your issue as a comment to an existing issue unless it's for the identical input. Many issues look similar, but have different causes.

The more information you can provide, the more likely someone will be successful at reproducing the issue and finding a fix.

Please include the following with each issue:

* Version of BitcartCC

* Your operating system  

* Deployment method: Docker, manual or others

* Reproducible steps (1... 2... 3...) that cause the issue

* What you expected to see, versus what you actually saw

* Images, animations, or a link to a video showing the issue occurring


### Final Checklist

Please remember to do the following:

* [ ] Search the issue repository to ensure your report is a new issue

* [ ] Try to isolate the problem

* [ ] Try to gather as much information as possible to reproduce your issue

* [ ] Open an issue and communicate with developers to solve it

Don't feel bad if the developers can't reproduce the issue right away. They will simply ask for more information!

## Contributing Fixes
There are many ways to contribute to the BitcartCC project:
* finding bugs
* submitting pull requests
* reporting issues
* creating feature requests

After cloning and setting up environment, check out the [issues list](https://github.com/bitcartcc/bitcart/issues?utf8=%E2%9C%93&q=is%3Aopen+is%3Aissue). Issues labeled [`help wanted`](https://github.com/bitcartcc/bitcart/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) are good issues to submit a PR for. Issues labeled [`good first issue`](https://github.com/bitcartcc/bitcart/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) are great candidates to pick up if you are in the code for the first time. If you are contributing significant changes, please discuss with the assignee of the issue first before starting to work on the issue.

### Setting up development environment

If you want to understand how BitcartCC works or want to debug an issue, you'll want to get the source, and set up dependencies.

As BitcartCC ecosystem consists of many repositories, installation instructions will differ. This file contains coding guidelines for all repositories, plus instructions how to setup the environment in central repository.

### Getting the sources

First, fork the BitcartCC repository you want to contribute to so that you can make a pull request. Then, clone your fork locally:

```
git clone https://github.com/<<<your-github-account>>>/bitcart.git
```

Occassionally you will want to merge changes in the upstream repository (the official code repo) with your fork.

```
cd bitcart
git checkout master
git pull https://github.com/bitcartcc/bitcart.git master
```

Manage any merge conflicts, commit them, and then commit them to your fork.

### Development Prerequisites for Python repositories

You'll need the following tools to develop BitcartCC locally:

- [Git](https://git-scm.com)
- [Python](https://www.python.org/downloads) at least version 3.6 (version 2 is __*not*__ supported)
- [Pip](https://pip.readthedocs.io/en/stable/installing/), with setuptools and wheel installed
- [VirtualEnv](https://virtualenv.pypa.io/en/latest/installation/), not required, but recommended for development

To install all of the following on linux, run:

```
sudo apt install python3 python3-dev python3-pip git
sudo pip3 install setuptools wheel
```

### Setting up python development environment

It is recommended to work with a virtualenv, repository's .gitignore assumes that your virtual environment is named
env, try to don't change it's name to don't add new files to .gitignore.


From a terminal, where you have cloned the `bitcart` repository, execute the following command to create the virtual
environment and activate it(may differ on different platforms):

```bash
virtualenv env
source env/bin/activate
```

Now, install python dependencies:

```
pip3 install -r requirements.txt
pip3 install -r requirements.dev.txt
```

To use BitcartCC you'll need to run at least one BitcartCC daemon. For each daemon you want to run, install it's requirements like so:

```
pip3 install -r requirements/daemons/coin.txt
```

Where coin is coin symbol, for example, btc.

Make sure to install the infrastructure parts of BitcartCC, refer to [Manual Installation Instuctions](https://docs.bitcartcc.com/deployment/manual#typical-manual-installation) and install needed requirements for the repository you are contributing to.

After you have completed manual installation, you can start development.

### Run everything

To test the changes you will need to run the server with applying changes to db if any.

```bash
alembic upgrade head
```

Then, open 3 terminals, and run one command in each of them:

```bash
BTC_NETWORK=testnet python3 daemons/btc.py
```

```bash
uvicorn --reload main:app
```

```bash
dramatiq api.tasks --watch .
```

### Coding guidelines for python code

Make sure to read our [coding guidelines for python code](CODING_STANDARDS.md#coding-guidelines-for-python-code) before contributing. By following these guidelines you will make reviewing process easier both for you and maintainers.

### Work Branches
Even if you have push rights on the bitcartcc/bitcart repository, you should create a personal fork and create feature branches there when you need them. This keeps the main repository clean and your personal workflow cruft out of sight.

### Pull Requests
To enable us to quickly review and accept your pull requests, always create one pull request per issue and [link the issue in the pull request](https://github.com/blog/957-introducing-issue-mentions). Never merge multiple requests in one unless they have the same root cause. Be sure to follow our [[Coding Guidelines|Coding-Guidelines]] and keep code changes as small as possible. Avoid pure formatting changes to code that has not been modified otherwise. Pull requests should contain tests whenever possible.

### Where to Contribute
Check out the [full issues list](https://github.com/bitcartcc/bitcart/issues?utf8=%E2%9C%93&q=is%3Aopen+is%3Aissue) for a list of all potential areas for contributions.

To improve the chances to get a pull request merged you should select an issue that is labelled with the [`help-wanted`](https://github.com/bitcartcc/bitcart/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22) or [`bug`](https://github.com/bitcartcc/bitcart/issues?q=is%3Aopen+is%3Aissue+label%3A%22bug%22) labels. If the issue you want to work on is not labelled with `help-wanted` or `bug`, you can start a conversation with the issue owner asking whether an external contribution will be considered.

To avoid multiple pull requests resolving the same issue, let others know you are working on it by saying so in a comment.

### Packaging
BitcartCC can be packaged for all the platforms docker supports, and for all the platforms python supports.

For packaging we usually use docker images, refer to [Docker packaging repository](https://github.com/bitcartcc/bitcart-docker) for more details.

### Suggestions
We're also interested in your feedback for the future of BitcartCC. You can submit a suggestion or feature request through the issue tracker. To make this process more effective, we're asking that these include more information to help define them more clearly.

### Discussion Etiquette

In order to keep the conversation clear and transparent, please limit discussion to English and keep things on topic with the issue. Be considerate to others and try to be courteous and professional at all times.


# Thank You!

Your contributions to open source, large or small, make great projects like this possible. Thank you for taking the time to contribute.
