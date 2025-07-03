# Bitcart (Core) Daemons

This directory contains source code for Bitcart core part: daemons.

All daemons inherit from others, building a dependency graph.

All daemons must inherit from `base.py`.

## Base daemon

`BaseDaemon` has the following properties:

- Daemon is an aiohttp web application
- Daemon supports "spec" (see spec directory) to provide better exception messages to clients
- Daemon can load different environment variables, under it's name prefix `COIN_ENVNAME`
- Daemon supports websocket notifications
- Daemon is a server following an extended variant of JSON-RPC 2.0 specification, it allows passing both
  positional and named parameters
  for example, passing `{"id": 0, "method": "method", "params": ["x", "y", {"xpub": "xpub..."}]}` is equivalent to calling `method("x", "y", xpub="xpub...")`

- Daemon exposes 3 endpoints
  - `POST /` - main execution endpoint, used for calling different methods provided. Override `execute_method` in your subclass to support it
  - `GET /ws` - websocket endpoint, used to listen for events. Where needed, call `notify_websockets` in your subclass to trigger notification on all websockets
  - `GET /spec` - returns daemon specification, for more details see [daemon spec directory](spec/README.md)

## Ready daemon implementations

Unless your coin is completely custom, usually there is no need to implement everything from scratch.

Most coins are based on bitcoin directly or not, and may have electrum wallet existing.

Note: to specify which electrum module to use, and if you need to customize something by using it's properties, don't do this:

```python
import customelectrum

class MyDaemon(BTCDaemon):
  electrum = customdaemon
  NETWORK_MAPPING = {"mainnet": electrum.networks.set_mainnet}
```

It would make all daemons dependent on your coin's daemon also require your `customelectrum` module to be installed. Instead do:

```python
class MyDaemon(BTCDaemon):
  def load_electrum(self):
    import customelectrum

    self.electrum = customelectrum
    self.NETWORK_MAPPING = {"mainnet": self.electrum.networks.set_mainnet}
```

It would import the `customelectrum` module only on startup

### BTC daemon

`BTCDaemon` is an implementation of Bitcart daemon using electrum wallet for it's operations. Read `btc.py` source code to check what you need to override in your subclass.

```python
class CustomDaemon(BTCDaemon):
    name = "COIN"
    DEFAULT_PORT = 5000 # assigned in order of addition
    electrum = custom_electrum
```

In most cases that's how approximate implementation of electrum-based daemons might look like.

### BCH daemon

If your coin is based on BCH and has a fork of electron cash instead, you should inherit from BCH daemon, as electron cash is too different from original electrum.
