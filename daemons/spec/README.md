# BitcartCC Daemons Spec

This directory contains a JSON-RPC specification for error codes and related messages.

All SDK's can create exceptions from spec returned.

In the future additional information may be added to the spec.

It is a json object with the following keys:

- version (`str`): version of spec
- electrum_map (`dict`): dictionary mapping electrum error messages to json-rpc error codes. Used by daemon
- exceptions (`dict`): dictionary mapping json-rpc error codes to exceptions. Used by SDK