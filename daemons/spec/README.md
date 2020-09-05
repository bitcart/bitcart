# BitcartCC Daemons Spec

This directory contains a JSON-RPC specification for error codes and related messages.

All SDK's can create exceptions from spec returned.

In the future additional information may be added to the spec.

## Working with the spec

To work with the spec, all SDK's must:

- Fetch the spec from `/spec` daemon endpoint (requires auth)
- Validate the spec by using it's description below
- Cache the spec if it was valid
- Otherwise, fallback to the following spec:

    `{"exceptions": {"-32600": {"exc_name": "UnauthorizedError", "docstring": "Unauthorized"}}}`
    
    It allows to raise unauthorized error if spec failed to fetch because of wrong credentials
- When raising error, if error code is in the spec, raise that error with
error name got from `exc_name` key with error message got from `docstring` ley.

- If error code isn't in the spec, raise `UnknownError` and pass server response as error message. This should also be done when spec is invalid, it works because of fallback spec.

Reference implementation can be found in [SDK repo](https://github.com/MrNaif2018/bitcart-sdk)

## Spec schema

It is a json object with the following keys:

- version (`str`): version of spec
- electrum_map (`dict`): dictionary mapping electrum error messages to json-rpc error codes. Used by daemon
- exceptions (`dict`): dictionary mapping json-rpc error codes to exceptions. Used by SDK. 

    Each object value is a dictionary
with keys `exc_name` and `docstring`. 

    Each object key is a string (JSON-RPC error code).