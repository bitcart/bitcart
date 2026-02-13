# Bitcart Configuration

This directory contains configuration files for Bitcart.

All settings are read from `.env` file.

By default it doesn't exist, and the defaults are used.

You can override values from `.env` file by environment variables, like so:

```bash
BTC_NETWORK=testnet just daemon btc
```

This directory contains an `.env.sample` file, containing explanation of what different config values do.

When configuring Bitcart, you can start with this sample, and configure it for your needs, like so:

```bash
cp .env.sample .env
# edit .env file for your environment
```

Also this directory contains an `.env.dev.sample` file - this config is used by Bitcart developers when adding new features.

`terminals.json` file is an configuration for [VS Code Terminals extension](https://marketplace.visualstudio.com/items?itemName=fabiospampinato.vscode-terminals), which allows to start all the tasks at once and start developing.
