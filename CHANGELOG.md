# Release Notes

## Latest changes

## 0.9.0.0

### The long-awaited release

After almost 2 years, we now have a new release. It's not like we had no changes, we had over 200 commits of changes.

The thing is, after addition of `./install-master.sh` script, it was sometimes easier to just run it without issuing a release.

But now it's the right time to make all new users receive proper Bitcart version by default

### ETH payments plugin

As you may probably know, ETH payments is a complex topic. After years of research, we've checked all solutions available.

Bitcart by default uses detection of incoming payments by asking for address of the sender beforehand.

This works well detection-wise, but provides bad UX especially because exchange users can't send you payments. It doesn't require paying any network fees, but UX is suboptimal.

That's why we have created a plugin which allows to make UX the best possible, and also save on network fees more than any solution existing.

Check out plugins marketplace in your admin panel to get the plugin!

### Plugins marketplace

Before this release, plugins were installed manually, often shared as files in our community.

Now, all plugins are listed in your admin panel's plugins page, and you can install it with a single click! (and another click to reload plugins).

Also marketplace added the licensing server, which allows us to sell paid plugins and make it possible to make Bitcart development sustainable for many-many years.

### Seed server in daemons

Another issue that has occurred during years of helping users was that, some RPCs for non-BTC-based coins are unreliable. Sometimes they get closed, or it hits rate limits.

And because of that, many users complained about X coin not running error. Which means we would have to forward the same message over and over again because we can't instantly update RPC url in all instances quickly.

So now we've launched the seed server at https://seed-server.bitcart.ai (e.g. https://seed-server.bitcart.ai/eth)

By default daemons are configured to use the seed server, and every hour (configurable) it will check for updates in server list and update it in runtime.

Which means, if any issues occur, in at most 1 hour your daemons will be working properly.

It allowed us to insert some servers we didn't want to commit to bitcart repositories, which means better RPC quality by default as well.

If you want to opt out of that behaviour, you just need to set `COIN_SERVER` to some specific RPC url not equal to seed server URL, and it will work the old way.

### Daemons RPC multiple providers support

As an additional feature to the daemons, you can now configure multiple RPC servers per coin. When sending requests, if one RPC fails, it tries the next from the list. If one RPC fails too many times, the default RPC for next requests is switched to the next RPC in the list as well.

You can set multiple servers via `COIN_SERVER=server1,server2,server3`. But note that by default seed server is used, which already provides multiple RPC urls for most coins.

### Support using a separate archive node for internal transactions

For ETH-based coins, the issue was that bitcart actually wasn't parsing all transactions existing. For example some exchanges like Coinbase may use internal transactions sometimes. Internal transactions are special type which isn't returned by any of the default RPCs in any API call. It requires calling a special method which isn't available in most places.

But if you do have access to one, you can set `COIN_ARCHIVE_SERVER` and if the server supports tracing, it will also parse internal transactions.

Because it's a separate server it is used only for tracing calls, because those RPCs are rare and we really don't want to use their total requests limit.

It is assumed that `COIN_SERVER` is a fast, almost-unlimited server which can serve many requests we have, while `COIN_ARCHIVE_SERVER` is used only for it's main purpose.

### Better notification providers

We've replaced the old notifications library with Apprise, which allows to use a variety of different notification providers.

Now you can even send SMS if you want to.

**NOTE**: you may need to re-check your notification provider settings as data format has changed.

### New captcha provider

Now you can use Cloudflare Turnstile as a captcha provider, which is easier to use for end users. HCaptcha isn't removed, and now you can switch between different options.

### Optional Sentry integration

If you want to use Sentry for error tracking, you can now do so by setting `BITCART_SENTRY_DSN` environment variable.

### Better email settings

Before it was confusing to configure email servers with the "SSL/TLS" switch, which was not reflecting what it actually did. Now you can choose between a list of auth modes.

### Other changes

There are too many changes to list, but here's some of them:

- Payment ID field to invoices for better matching of paid methods
- Add favicon to API docs
- New commands in daemon: `rescan_blocks`, `batch_load`
- Support for one-time calls in xpub data. This allows to execute request and close wallet right away.
- Refactored email utilities
- Better email verification on sign up
- Refactored schemes with Python 3.9+ type hints
- Upgraded to Pydantic v2
- Changed from passlib to pwdlib
- Require Python 3.11+ (with Python 3.12 support)
- Use Ruff for linting and formatting
- Use uv instead of pip-compile
- Use human-readable migration names
- Renamed alembic folder to migrations
- Upgraded all dependencies
- Electrums upgrade
- Fixed TRX contract sending
- Fixed processing of invoices dropped from mempool
- Fixed explorers for BCH
- Fixed DKIM signing of emails
- Fixed USDT exchange rate when only Tron is enabled
- Fixed network fee estimation
- Fixed SMTP port 465 issues
- Fixed contract getting
- Fixed BNB payouts
- Fixed currency-api link
- Fixed HTML mode in notifications
- Fixed ETH max amount payouts
- Fixed quotes with more than one underscore
- Fixed verification emails sending
- Fixed XMR amount formatting for underpaid detection
- Fixed TRX daemon startup
- Fixed setting fields to empty string
- Fixed sign up when email is required
- Fixed XMR invoices stuck on paid
- More robust handling of Decimals
- Allow to edit global templates
- Optimize daemon shutdown
- Reduce log spam in notifications
- Add BCH testnet4 and chipnet support

## 0.8.0.0

### Name change: from BitcartCC to Bitcart

It is an important milestone in our project. Initially we couldn't take that name because it was already filled by some other projects
Now, after years there is only one bitcart: ours. In fact, it was used as bitcart in code before, and now the UI naming will catch up too
It is more consistent. Also from the community polls it is easier and many people used Bitcart instead of BitcartCC even before.

Together with a new name, we've got a new professional-made logo redesign

This release has breaking changes in docker deployment mostly due to changing of some files.

In order to do the update, run:

```bash
./update.sh
./setup.sh
contrib/upgrades/upgrade-to-0800.sh
```

The env vars are now stored in /etc/profile.d/bitcart-env.sh, and systemd file is also named bitcart.service now.

All plugins have been updated with new naming and logos

### Electrums upgrade

With the new electrums and other daemons update, it fixed a rare but possible bug when BTC or LTC wallets got stuck forever. More robustness, more performance!

### Tracing internal ETH transactions

If your RPC supports debug_traceTransaction method, then bitcart will also automatically detect internal transactions to your wallet! Unfortunately for now the default RPC doesn't support it, but bitcart is ready

### Publish to multiple container registries

Now Bitcart docker image is published to dockerhub, ghcr.io and nirvati registries for better reliability!

### Bug fixing

- A bug with metamask button in admin panel have been fixed
- Also, before when you added a new wallet with contract in a new blockchain, it broke the exchange rates system and everything was stuck until a reboot. This is now fixed
- `get_updates` method now no longer crashes in eth-based daemons
- Speed-up payouts loading, fix tron payouts
- Add more data to `new_transaction` event in eth-based coins
- Allow passing nonce directly and add `getnonce` method in eth-based coins
- Add ability to customize gas price by a multiplier globally or by call in eth-based coins
- Store time it takes for customer to pay for an invoice
- Fix store POS for non-global store

## 0.7.4.1

Fix an issue with new store POS checkout for tor onedomain mode

Allow to disable POS calculator screen

## 0.7.4.0

### New exchange rates engine

Because of recent issues of coingecko, as well of lack of some local currencies and other issues, our rate engine has been improved.

The exchange rates functionality have been moved from the daemon one layer up, to the Merchants API. If you use `exchange_rate` or `list_fiat` functions from daemons RPC protocol, please either use Merchants API directly (some usecases of SDK can completely be replaced by the Merchants API), or fetch exchange rates manually. This already gives you more control over how to do the fetching.

For the rest of the users, no breaking changes are made. In fact, the system is more reliable. It is now possible to add custom rate rules in store settings.

If your local currency is not supported, you can do something like

`X_MYCUR = X_USD * fiat(USD_MYCUR)`

You can use a variety of exchanges. Most of them are added via coingecko exchanges API, but `kraken` and `fiat` are added natively. fiat refers to currency API hosted by github pages, updated daily list of USD to other fiat currencies rates.

You can also use functions like `mean` or `median` to gather rate off multiple exchanges. In case one fails, others will be still counted in.

### Optimizations in daemons

We continue to optimize the performance and memory usage of the daemons. An issue with infinitely growing list of events for polling has been fixed, it's now capped by 100 events per wallet max. Polling is not used by merchants API, so it was a useless use of memory and performance.

### Store POS improvements

The store POS has received numerous improvements in this release.

An initial prototype of a keypad UI is now accessible. It is useful for in-person checkouts for example.

Also, store POS now uses admin panel's checkout page, which means there is now only one reference universal checkout page.

### Misc changes

- Fix order_id endpoint in large instances
- Fix issues in payouts sending
- Add batch delete for API tokens
- Handle ValidationError in OAuth2 endpoint
- Improve UX of admin panel's autocompletes

## 0.7.3.0

### Admin panel UI revamp

Admin panel has got a revamped UI - the datatables now display 10 items at a time in full screen mode. Also you will see horizontal scrollbars in less cases.

Navigation is now performed via a toolbar at the left. This allows us to expand the dashboard in future releases with new graphs and statistics

Zero-amount invoices have better formatting now

### Important: fixes for template rendering

In case your server is a public instance with many users, update is recommended. In short: in some cases template rendering could allow executing commands inside the worker containers

### Batch payouts

It is now possible to batch payouts in one transaction to save on costs, for btc-based coins only for now

### Lightning network send amount support

Lightning network now displays sent amount correctly, and payment hash is filled in transaction hashes value

### Important: fix memory leaks in daemons

After a large investigation, we've found the issues of the leak to be located in `malloc()` linux function. To resolve this complex issue, all our python docker images now include and use jemalloc memory allocator for better performance and to avoid memory fragmentation.

### Misc changes

- Don't process pending blocks for fresh created wallets to speed up some operations.
- Close wallet after performing diskless methods to avoid it being loaded in memory

## 0.7.2.3

Fix excessive memory usage of Lightning gossip and CLI not working

Make order id endpoint return invoice with any status other than expired. If it's expired, a new invoice is created

## 0.7.2.2

Fix incorrect use of `distinct()` when calculating some functions in database

## 0.7.2.1

Fix `/manage/policies` endpoint for non-superusers

## 0.7.2.0

This releases a ton of improvements and fixes in many different aspects of BitcartCC

### MIT license

We are back to being at MIT license, possible to be used in any environments!

### 2FA support

Yes, it is now possible to protect your account with additional layer (or layers) of security.

After entering password, you will be able to login via either Time-Based One-time Passwords (TOTP) via apps like Google Authenticator or via FIDO2 (hardware devices, i.e. Ledger, YubiKey). Enjoy!

### Email verification support

If the server owner has configured server's email server, it will be possible to ask users to verify their emails

### Password reset added everywhere

It might sound weird, but before this moment it was not possible for a user to change their own password without asking server admin. This is now fixed, with additional abilities like "Log out all devices".

### File upload support

It is possible to use your instance as a small file upload center. One of it's main application is to supply in e.g. Store Theme CSS URL setting or similar, but you can use it however you like

### Add ability to generate wallet from the UI

In case you don't want to find an xpub or similar for your wallet, just click on the "+" icon, and generate either watch-only or a hot wallet right from BitcartCC UI in a secure way! Note: don't forget to write down your seed phrase of course!

### Refunds support

The long-requested feature, you can now trigger refunds on any invoices with payments sent to them. You will be presented with a variety of options how much to refund, and BitcartCC can even send an email to your customer about the refund automatically.

When customer enters their address for refund, you will be notified via your configured notification providers. Two new templates were added to configure message sent to customer, and message sent to merchant

### Add ability to include network fee in invoices

On some blockchains, network fees are extremely big. To avoid spending money on them, you can include it's cost in invoice amount automatically. We might built up improved methods of payment detection for ETH based on this setting

### API docs improvements

Our API docs are autogenerated, and we fixed a number of issues preventing correct generation. Now you can see a clear description of when auth is needed or not, and when it is optional, as well as other fixes.

### Plugins schema 1.1.0

With new plugins schema, plugin authors can add new metadata, like plugin website, source code URL, docs URL and license. It will be displayed in the UI

### Plugin authors: improved BitcartCC CLI

Plugins author can now easily bootstrap their plugins via `bitcart-cli plugin init`, validate them via `bitcart-cli plugin validate` and package via `bitcart-cli plugin package`

BitcartCC CLI has been moved to https://github.com/bitcartcc/bitcart-cli, all further releases will be here

### Xpub field's label can now be customized

This means that if you select eth as your wallets currency, it won't tell you to enter confusing "Xpub", but instead it will ask you for an address

### Improvements in plugin APIs

The plugins API has been extended to allow plugins to register custom payment methods. Take a look at our [Lightning network + plugin](https://github.com/bitcartcc/bitcart-plugins/tree/master/lnplus)

### Misc improvements

- Script to disable multifactor auth in case of recovery
- Fix local deployment issues once and forever
- Make lightning network implementation use lightning gossip instead of trampoline: this means you would be able to open channels with other nodes just by node id again.
- Improve CLI autocompletion not working sometimes
- Avoid re-building plugins on updates if there's no plugin installed
- Fix store POS rendering for amounts > 1000
- Fix email presets
- Allow sending all balance in payouts
- Fix a long-standing bug where clicking on "Open wallet" button closed websockets and page didn't refresh on payment
- Better logs management UI
- Fix and improve order_id endpoint
- Fix for weird cases when you had a pending amount with sent amount of 0, but exception status paid_partial
- Fix an issue when invoice rate was not normalized in some cases, resulting in "rounding errors" in the UI
- Reduce memory usage of ETH-based daemons
- Tron: use native code for cryptography, speedups
- Improve performance of exchange_rate: avoid fetching unnecessary rates on every call when currency changes

## 0.7.1.0

This release packs a lot of small, but quality of life improvements and fixes

### Fix BTC payments processing

BTC payments processing was not working in some cases since 0.6.15.0 release. This is now fixed.

### Underpaid/overpaid payments detection

Now for each invoice you will be able to see sent amount - how much exactly the customer sent, and exception status: none if customer sent the exact required sum, `paid_partial` if customer underpaid, `paid_over` if customer overpaid.

In case a partial payment is sent, checkout UI now updates and notifies the user that they didn't pay in full yet

### Zero amount invoices

It is now possible to create zero amount invoices: such invoices will get complete upon any payment. They are useful for top-up operations in some services.

### Password reset

Finally possible! If server owner has configured email server in server policies, it will be possible to reset password by a link to email.

### Basic quantity management

The store POS has gained basic quantity management: when a product is bought, it's quantity reduces. Unlimited quantity can be specified by setting `-1` as product quantity.

### Allow running on bare ip

It is now possible to easily run without a domain, just set `BITCART_HOST` to server ip address and it will just work!

### Allow running staging updates

In case you want to test a new feature, you can enable new setting in store policies, then update button will build docker images directly from master branch, allowing to test fixes without a release

### DNS lookup in the configurator

The configurator now checks if `BITCART_HOST` specified actually has any DNS records configured. If it doesn't, it warns the user that the installation will likely fail

### Lunanode configurator shut down

The old lunanode configurator deprecated long time ago is now shut down. https://launch.bitcartcc.com now redirects to the configurator.

### New endpoint to get/create invoice by order id

A new endpoint POST `/invoices/order_id/{order_id}` was added. It gets a pending invoice by order id, or if it doesn't exist, creates one with params specified. This is useful for our plugin integrations and it will be used to avoid duplicate invoices created on i.e. page refresh.

### Misc changes and fixes

- In case Merchants API is not available, store POS displays a helpful troubleshooting page
- Use nodejs 18 in all frontends
- Display product name in admin panel invoices page
- Display if discount was applied
- Loading animation for management commands buttons
- Allow setting invoice expiration without modifying store checkout settings
- Fix alembic migrations bad logs
- Fix restoring backups from UI and other UI commands
- Fix invoice export
- Less verbose logging for backups
- Allow configuring debug setting for daemons via `COIN_DEBUG`
- Improve reliability of backup script
- Allow running older version via `BITCART_VERSION` in docker deployment
- Save plugins data in backups

## 0.7.0.1

Fixes in plugin API: metadata is now json-encodable, fixed calling product creation hooks, better UI slots in store

## 0.7.0.0

### Plugins support

It's finally here! Starting from this new major release series, BitcartCC is now fully extendable!

Anything is now possible

Server admins can now install plugins from the UI.

Just upload a plugin archive (`.bitcartcc` extension), and it will automatically re-build everything!

It is possible to customize backend (by adding new pages, database tables or adding metadata, hooks and filters), UI (new pages, extend in special UI slots, add new data), and docker deployment (new auto-loaded components and rules).

The opportunities are limitless!

See example here: https://github.com/bitcartcc/bitcart-plugin

The plugins support will get extended over time.

We encourage all plugin authors to start working on their first plugins, we will issue follow-up releases polishing the API

Anything that has ever been requested before which didn't fit well in BitcartCC core can be extracted to a plugin!

## 0.6.15.3

Fix important issue in processing XMR mempool

Make `underpaid_percentage` work the expected way again

Fix normalization of destination address in payouts and payouts on tron mainnet

Our fee prediction algorithm for tron should now account for 100% of cases.

Add `sent_amount` to internal invoices in the daemon everywhere

Fix payouts for BCH

Fix `tx_hashes` not working for multiple transactions in ETH

## 0.6.15.2

Fix payouts in Tron mainnet

Fix long-standing issue where backend logs where not transferred to log server. The server logs section will be way more detailed now.

Clarify why customer address is needed in eth-based methods

## 0.6.15.1

Fix XRG daemon

## 0.6.15.0

### Tx hashes of paid invoices in UI

A commonly requested feature, now you can view (and even instantly view in block explorer) tx hashes of paid invoices.

### New algorithm for detecting payments in ETH

While our current ETH support is great and previous method (unique amounts) seemed to be the most optimal one with zero costs to the merchant, it actually incurred some costs: costs for customer support to handle cases with users sending not exact amounts. This is not greatly automated.

That's why, we came up with a new way: ask customer for the address they will be sending from.

This allowed us to process payments in the same way as in other currencies, it even allows invoice to be paid in parts. If user over-pays, there is no issue anymore.

Checkout UI for eth-based currencies was reworked to present user with 3 choices: enter address manually, or pay via metamask or walletconnect (address gets pre-filled).

## 0.6.14.0

### Monero support

This release includes the long-awaited monero support!

This means that now BitcartCC supports all major coins and no other solutions are needed to accept payments

For now, payouts support and balance fetching is disabled for monero because it is not yet clear how to do that in a light-weight environment.

For it to work, just enter your secret viewkey and address, and enjoy!

We use integrated addresses to detect payments.

### Cleaner payment methods selection

Before it was not obvious that you can switch between currencies in admin panel's checkout UI. By adding a special icon, it is now way clearer

## 0.6.12.0

### Extreme speed

Due to the cutting-edge optimizations, invoice creation, balance fetching and other operations are up to 10x faster

### Captcha support

You can now protect login pages with hcaptcha. It is configurable in server policies. Login and registration pages will be protected and less spam will be possible

### Better stability

ETH daemon implementation is applying proper retry logic in more places, allowing for no blocks skipped due to temporary network errors

Fixed some crashes when processing a lot of wallets

### Misc changes

- Python 3.11 support
- Fixes for random selection of wallets
- Make it possible to make auth mandatory in invoice creation
- Disable EIP1559 in eth for more predictable fees and add `COIN_TX_SPEED` to configure default gas price being used in transactions
- Fix duplicate websocket notification sent from the daemon
- Display store name in store POS page title

## 0.6.11.2

Fix ETH-based daemons transaction processing

Fix admin panel's dialogs UI

## 0.6.11.1

This update includes Groestlcoin (GRS) support, as well as fixes for Tron RPC and allows to use Ankr RPCs for ETH too.

## 0.6.11.0

### WalletConnect button

While our current ETH support is great, many users may still get confused and send wrong amounts when not using metamask wallet.

On checkout there is now a new button available: Pay via WalletConnect. Users can then scan a QR code to connect their wallet, BitcartCC will do the rest

### Tron support

The long-requested Tron (TRX) support is there! It is supported fully and in a similar way to how ETH works. Each method have been implemented and tested.

BitcartCC might be even the only software which implemented the full transaction fee calculation algorithm except for full node itself. You can know the fee before sending via `get_default_fee` command.

Note: the volume of transactions in Tron network is way higher than in ETH or even BNB, but we found a solution to make it work under high loads. The only downside is that you should not keep your node offline, ideally try to never let it be offline for more than few minutes.

## 0.6.10.0

### Block explorer support

You can now instantly view tx hashes of your payouts (and invoices in the future, too) via block explorers.

BitcartCC provides a list of sane defaults, but you can easily customize for your own

### Randomize wallets used setting

For better privacy, UX and funds distribution, if you have multiple wallets of same currency connected, you can now enable a setting, and in invoices only one random wallet will be picked, not each of them

### Allow searching by payment methods

Ever needed to search by address of your invoice? It is now possible!

### Polygon (MATIC) support

Polygon is now supported

### CRITICAL: fixed exchange rate issue

Exchange rate issue introduced in 0.6.8.0 release series is finally fixed. Thanks to everyone who helped to coordinate a fix!

### Drop arm32 support

We no longer build arm32 images. You can build them from source if you still use arm32

## 0.6.9.1

### CLI improvements

Our `bitcart-cli` have been improved greatly! You can now pass keyword arguments, i.e.

```bash
bitcart-cli payto address amount --feerate
```

Also, better output was added in some cases.

Autocompletion is now available! Just press tab as usual, and you will be hinted the list of CLI commands supported

Also, you can get full help on any command like so now:

```bash
bitcart-cli help payto
```

### Misc changes

- Fixes for tor support in onedomain mode
- Added new settings for admin and store to allow integration to Citadel: `BITCART_ADMIN_ONION_API_URL` and `BITCART_ADMIN_ONION_HOST`. This allows skipping reading the hostname file and using env var as a source of tor hostname

## 0.6.9.0

### Payouts support

Yes, now it is possible to send payouts right from BitcartCC's admin panel!

For clarity, BitcartCC core supported this from day one due to our modular stucture, and now it is available at the highest level in BitcartCC: the UI.

A new tab was added to dashboard. Why is it useful? Because managing and opening wallets for many currencies is not convenient when you can do this from BitcartCC's unified UI. Send payouts, see tx hashes of sent transactions, limit fee usage by transaction, review payouts and see used fee stats!

If a wallet is a hot wallet, payouts are signed automatically. But most wallets in BitcartCC are watch-only.

You will be able to enter a private key for signing operations. It won't be saved anywhere on disk or shown in any commands output.

This is possible due to new mode in the daemon: diskless (in-memory) mode. Read below for details

### Diskless mode

For some operations, like signing, sometimes you have to use a private key. But it is not good when a wallet is cached to disk, together with all keys and wallet history. That's why we added a new mode to the daemon.

When from SDK, send diskless: True param as part of xpub's dict, i.e. `{"xpub": "seed here", "diskless": True}`

You can use such a mode from CLI like so:

```bash
bitcart-cli --diskless -w "seed here" signtransaction txdata
```

### Fixes to rounding of amounts

Now final, the way BitcartCC rounds amounts is stable. Now amount you see in the UI match the exchange rate displayed, and a bug where you could send exact amount and it still wouldn't be detected is fixed now

### Misc changes

- Fixed deployment's ssh key generation to a newer algorithm
- Cloudflare tunnel support
- Boxbilling plugin

## 0.6.8.1

Hotfix release: if you ssh to your server as root user, it could have been broken by 0.6.8.0 release. This is fixed now.

Please run `chown root /root/.ssh/authorized_keys` if it got broken.

Also added ability to customize API title and openapi file

## 0.6.8.0

### docker-compose v2

BitcartCC now uses docker-compose v2. It's faster and more secure. BitcartCC should try to update docker-compose automatically. All container names are now separated by `-` and not `_`. Example: if before you would use `compose_backend_1`, now it's `compose-backend-1`

### Secure images

All BitcartCC images are now built in a way that non-root user runs processes inside a container, helping avoid some docker vulnerabilities and making whole BitcartCC stack more secure. This also means less workarounds our side.

### Electrums upgrade

All electrums were upgraded to 4.3.0+. Minimum required version to run BitcartCC is now python 3.8+, base image version is now 3.9

### Other changes

- Onchain payment of same amount no longer can trigger contract payment confirmation
- BitcartCC should now properly install itself on Mac os, even M1 arch.
- Fixed a bug on binancecoin where exchange rates weren't fetched
- Added ability to pass `--contract` flag to `bitcart-cli` to load a wallet with a specific contract
- Fixed domain-less usage of BitcartCC via tor
- Fixed a bug where worker wouldn't start after deploy without a restart

## 0.6.7.8

Fixes gas estimation to work 100% of the time

Now contract payments don't get stuck on first error but will always get detected

Added retry mechanism to eth daemons - no temporary issues should ever interrupt payment processing!

## 0.6.7.7

Proper params casting + transfer function now accepts amount in ETH, not wei (and it does proper casting to needed divisibility by itself!)

No more server error on PATCH when you only pass i.e. `wallets`

New daemon method for eth-based coins: `get_default_gas` - it gets the gas value needed to execute a transaction. Before it was named `get_default_fee`. Now the `get_default_fee` method behaves like it did in other coins: it returns amount needed to pay the fees

## 0.6.7.6

Added ability to configure number of hours eth-based daemons can be left down (default: 1 hour). Configurable via `COIN_MAX_SYNC_HOURS` env variable.

For ETH, BNB and all the contracts the maximum number of decimal digits is artificially decreased to 8 decimals. That's because most exchanges and software doesn't support more than 8 decimals (noone's following the specs except for us), so to make it possible to send from i.e. binance this change was made.

Daemon is almost unmodified - it stores and returns balances in original 18 decimals precision, just that invoice amounts generation algorithm will use at max 8 decimals. As for the merchants API, the output formatting decimals were indeed changed to 8 (from 18), so checkout page now has 8 decimals, which is more readable.

## 0.6.7.5

Better UI for final statuses on invoice page

Simplified payment process via metamask: just one button state (pay via metamask) instead of separate connect/pay flows.

Smart contracts balances are now properly displayed in the admin panel

## 0.6.7.4

Fixed metamask icon loading

Fixed a rare bug in token payment processing

## 0.6.7.3

The create backup button now automatically downloads newly created backup, so you no longer need to access your server to get it saved locally!

## 0.6.7.2

Better checkout on eth-based payment methods on desktop: added pay via metamask button

## 0.6.7.1

Fix eth payment methods onchain qrcodes (put amount in wei)

There is also a message displayed telling customers to pay exact the needed amount

Also you can now customize the checkout hint for any wallet (payment method) you need

## 0.6.7.0

### Shopify integration

It is now possible to connect BitcartCC to your shopify stores! Check the shopify integration icon on stores page and our docs for more details

### Better invoice export

For better accounting, invoice export process have been improved.

The export button now has a dialog which allows to customize more options! By default it no longer includes payments as they were quite useless and added lots of unneccesary fields

There is a new "All users" option to export all complete invoices by all users (available only to server admins, this is useful for instances taking fee percent from transactions without interferring into payment flow)

Use current query allows you to apply some filters using the search bar (and sorting by columns), and then export that data

## 0.6.6.0

Normalize contract addresses: no matter where you've got contract address from, it should correctly detect payments now.

Upgrade is recommended for everyone accepting contract payment as before that fix payment processing maybe didn't work for you.

Please re-save all existing wallets with contracts for them to be normalized.

Added more bep20 tokens to pre-defined list

Better exchange rate normalization: it should now correctly work for coins with low exchange rates and in some edge cases

SmartBCH support

Fix BCH payment processing

Better handling for long currency names in checkout page

## 0.6.5.1

Fix BNB support

## 0.6.5.0

Added Binance Smart Chain (BNB) coin support and BEP20 tokens support

Added warnings about node sync status

Fixed token list not working sometimes

## 0.6.4.1

Fix UI issues and faster commands execution

## 0.6.4.0

Added ERC20 tokens support and fixed some bugs in ETH implementation

## 0.6.3.0

### Ethereum support

We have added experimental ethereum support in this release.

This was a complex task, but we did it.

Ethereum support allows you to use our SDK the same way as you would do with btc-based coins, even though there are lots of differences

Payment processing works too

We have implemented this via geth fullnodes' light syncmode.

It requires a bit higher system requirements than usual, more exactly:

2 GB of RAM is extremely recommended (1 gb may work if not using many other currencies)
As for disk, at least a few gigabytes of disk are needed (right now 1 GB is used)

We don't support some methods from electrum like those getting history, but other than that it all works via your local geth node.

In payment processing, as ethereum is fundamentally different from btc-based chains, we decided to use one address for each invoice, but with unique amounts.

That's because in ethereum all wallets are using only one address, and if you would have used multiple addresses it would require you to manually transfer your eth and tokens (which requires additional eth those addresses don't always have)

ETH support is based on our custom implementation, you may even call it CLI-only electrum wallet for ETH.

This prooves that BitcartCC is indeed as extensible as we thought.

## 0.6.2.0

- Maintenance package upgrades
- `email_required` is now a per-store setting instead of a global one
- almost all decimals are now pretty-formatted as strings (with correct number of digits)
- upgraded electrum to 4.1.5
- added ability to input shipping address/notes

## 0.6.1.0

This release contains quite a few bugfixes and new changes, but doesn't contain any breaking changes

During this release we started our efforts to localize and improve customization of BitcartCC parts.

Our website was translated into Belarussian, French and Hindi languages in addition to already existing English and Russian.

In 2022 many important changes are coming to make BitcartCC the easiest to use

### Better search engine

Search engine in admin panel is now way more advanced.

It is now possible to search by exact fields, like:

`store_id:someid some arbitrary text` will filter column `store_id` with value `someid`, and then search `some arbitrary text` like it did with previous
search engine.

You can also filter objects created in a certain time interval

### Theming support in BitcartCC store

You can now customize the UI of your store pages!
In admin panel you can set a link to css file used for themeing your admin (not supported yet) or store.

You can override different color variables to customize the look and feel of your store.

Here's example css:

```css
:root {
  --brand-color: #162d50;
  --primary: var(--brand-color) !important;
  --success: var(--brand-color) !important;
  --link: var(--brand-color) !important;
}
```

### Better store UI

The cart page was removed, instead by clicking on cart button a wonderful sidebar will appear (with nice animations too)

Also store can display more than 6 items per page now (6, 12, 18 or all items)

There were some accessibility improvements to the store

### Quality of life improvements

- In case of API issues, admin panel and store now display a better page explaining how to resolve the issue together with detailed logs
- In admin panel tooltips were added on hover to all icons
- On store page there is a new button to quickly jump to view all invoices of a store (via new search engine)
- Better lists UI
- Added an easter egg!
- Automatically upgrade faulty libseccomp2 on rpi to make setup flawless

### New library released: universalasync

We have released a new library under bitcartcc organization: `universalasync`. It allows library maintainers to write only async versions of their code, and sync version will be achieved automatically. Depending on call context, wrapped functions will either work as sync or async ones.

That's the same way our SDK has worked for quite a while, this functionality was extracted from SDK to a separate package.

Also the implementation was greatly improved, we now test all use cases and fixed some bugs.

### Other changes

- Postgres database in docker no longer sets a password: it accepts connections without any password set. This is fine because database is not exposed to the outside internet
- Added `py.typed` to SDK to allow type checkers to suggest better hints for user code
- Dropped leftovers of gzro coin
- We have rewritten many of our code to properly use event loop, therefore we can support python 3.7-3.10+ without issues
- All our test suites now run on testnet
- Our regtest tests now use fulcrum
- Fixed email notification provider and others that required integer types, also fixed broken notifications when changing notification providers
- Added `removelocaltx` command for bch-based coins and made bch daemon use official electron cash instead of our fork again
- Upgraded all packages
- Fixed backups
- New `get_tx_hash` RPC method to get tx hash of a raw tx
- Fixed worker start on Mac OS

## 0.6.0.1

Fixes admin panel weird UI of buttons near datatables

Now all exceptions are caught when creating invoices

## 0.6.0.0

### Major update

This update contains backwards-incompatible changes

This time we have included the changes from all BitcartCC repositories since previous version

### Breaking: unifying data directory

The app stores all it's data in one directory instead of separate directories within source code. This makes it work without permission errors.

With docker deployment only the datadir volume could be backed up, also it's separated from source tree now

This removes unnecessary volume mounts in compose dir, now all data is stored in named docker volumes. Also removes conf directory mounting and many fixes applied before, as it is actually not required now

This means that logs and images are not moved into new directory by default.

At docker deployment `bitcart_datadir` volume now stores all the data, `bitcart_logs` volume is removed, `compose/images` directory and `compose/conf` directory are not used anymore.

Run `contrib/upgrades/upgrade-to-0600.sh` upgrade helper to move your existing logs and images if you need it

### Multiarch support (ARM images now available)

Now we build all images for 3 architectures: amd64, arm32, arm64. This allows running BitcartCC on a Raspberry Pi and other portable devices.

We have updated all our docker components, not only main BitcartCC parts

bitcartcc/docker-gen gained arm support, updated with upstream changes to 0.7.7

updated bitcartcc/tor to 0.4.6.5 with arm support

bitcartcc/docker-compose was moved to bitcartcc/bitcart-docker-deps repo and updated to 1.28.6

Usually building images for ARM takes a while when being run in a emulation, but we found a solution:

We build amd64 image on amd64 machine without emulation, and in the same time arm64 machine on CI builds arm64 image without emulation and arm32
image with emulation, but this emulation provides minimal performance penalties, images are built in parallel with `docker buildx`.
After that, images are united into one tag with `docker buildx imagetools`, so that when pulling a release the right image gets chosen.

So if you are on a raspberry pi, same instructions as on regular servers apply, and everything will just work.

### Backups support

The long-awaited feature is there! All deployments now have `backup.sh` and `restore.sh` scripts performing backup and restore operations

Example:

`BACKUP_PROVIDER=scp SCP_TARGET=user@someip:backups ./backup.sh`

On another machine with ip `someip`:

`./restore.sh 20210918-220925-backup.tar.gz`

Will restore the identical state of your instance.

You can also perform manual backups from server management->backups page by just a click of a button.
Backup settings, like provider and environment variables are also configured here.

Current supported backup providers: local (save on local machine), scp (send via ssh to any machine), s3 (send to AWS s3)

You can also schedule backups, by default it is off. They are performed in one of selected frequencies: daily, weekly, monthly.

The app will store the remaining time by itself even after restarts.

All backup operations are also logged to server logs.

### Electrum 4.1 upgrade and various core daemon refactors and improvements

This is our scheduled upgrade of electrums from 4.0 series to 4.1 series

Breaking changes in electrum:

- Lightning gossip is not enabled by default as before, instead trampoline routing is used. You can enable gossip back by setting `COIN_LIGHTNING_GOSSIP` variable to true
- When invoice is paid, it's status is no longer `Paid`, but `Unconfirmed`. Invoice becomes `Paid` after first confirmation. This allows us to implement `transaction_speed` setting in a better way

Important changes in electrum:

- Deterministic lightning keys added. This means that you can't run two nodes on the same server with same seeds, because node_id would be the same. Important note: deterministic node id is enabled only for native segwit wallets created/restored from electrum seed (xprv won't work).
- Signet support added
- All lightning commands now have l tag, which allows us to provide better exceptions for lightning methods

Other changes related to electrum upgrade:

- Added tests for lightning payments to ensure they also work
- Improved handling of invoices, query only needed statuses, removed problem with first confirmation not always appearing
- Hide logging errors from electrum when not in debug mode
- Disabled rpc in electrumx and also removed ignore asyncio warnings in tests
- Implemented graceful stopping for all daemons
- Improved fee estimates handling

Together with electrum upgrades, BCH-based coins have gained some more feature-parity with btc-based coins:

- Removed lockfile creation for bch, it can now run in parallel with electron cash wallet
- Added feerate support for bch-based coins

### Important: deprecated lunanode installer

Our lunanode installer at https://launch.bitcartcc.com is deprecated. Use BitcartCC configurator instead, it is more feature-complete and can install
BitcartCC on any server. We might add some hosting provider presets to configurator in the future/
The lunanode installer will be removed with the next BitcartCC major release: 0.7.0.0. It will then redirect to the configurator.

### Many core daemons and invoice processing improvements

- Daemon refactor: it's settings are now passed as cli args. i.e. you can't use `setconfig("lightning",False)` and disable lightning if it was enabled via env var
- Added new `verified_tx` event, called when tx got it's first confirmation
- Experimental: `get_tx` SDK method (`get_transaction` daemon method) now supports `use_spv` flag to use SPV verification for getting confirmations, this works on all electrumx servers without verbose mode errors, but it is experimental because it is inefficient, we are waiting for electrum protocol 1.4
- Use coingecko for btc with tor as it no longer blocks tor exit nodes
- New `getaddressbalance_wallet` RPC method which gets address balance via local wallet balance and not network
- It is now possible to override daemon exception spec in other coins to extend it with custom errors
  So there are now two specs: base spec, by default btc.json for all coins, and the current coin spec, if used. Changing base spec may be useful for adding coins like ethereum
- `WalletNotLoadedError` is now properly raised by the daemon instead of not-easy-to-understand `KeyError`
- Commands which require wallet are now properly checked
- Fixed daemon xpub parsing
- Daemons are now properly documented
- Now `BaseDaemon` contains only base code common for all daemons, like config loading, and `BTCDaemon` contains code for electrum-based coins, it is useful for adding completely custom coins not based on electrum
- Fixed rare bug with event processing order for sync clients
- Fixed issue with IPN sending on `transaction_speed` >= 1 and added functional tests for it

### Added new coin: XRG

Added Ergon (XRG, port 5005) via it's electron cash fork oregano:
https://ergon.moe
https://ergon.moe/prop-reward.pdf

It is a fork with BCH with stable price. It is achieved by making the block reward proportional to the cost of producing a block. Earning a single unit of the currency by mining takes a fixed amount of effort.

### SDK improvements

- Use current package version in SDK docs
- SDK now doesn't crash on None rates
- Emulate `asyncio.run` behaviour, allow starting/stopping websockets in idle unlimited number of times
- Better error handling, no try/except required, all errors are logged instead, load_wallet can handle currencies case-insensitively

### BitCCL improvements

BitCCL is getting prepared for being integrated into BitcartCC in following releases.

Better, more secure compiler
It can now be used without issues even with untrusted code which tries to bypass the passed context, export only needed functions

### Quality of life improvements

The toolbar on admin panel is now unified. On desktop the left navigation bar doesn't open anymore, as it is replaced by main toolbar. On mobile the left navigation bar is now useful and contains links for navigation (before configurator link wouldn't fit in screen)
When logged in, it shows same links as before. When not logged in it shows configurator (if allowed by server policies), login and register buttons
Datatables are more responsive too now

Other improvements:

- Display fiat currency in balance stats instead of ephermal sum of balances, it is configurable in the profile page
- Support for custom payment methods labels, this is configurable via `label` field of a wallet
- Better reponsibility on mobile

### BitcartCC CLI is now included in docker deployments

You can access it with `bitcart-cli.sh` script, like so:

`./bitcart-cli.sh help`

It requires a running `worker` container

### Maintenance and other improvements

- We have disabled dependabot (spammy) on all our repositories and enabled renovate instead.
  https://github.com/bitcartcc/renovate-config is our global config repository
- Many improvements to circleci pipeline: now test results and artifacts are uploaded
- Install bitcoind from PPA in CI for tests to improve build times greatly
- Integrate `pre-commit` for better contribution experience, and to modernize and unify our codebase
- https://github.com/bitcartcc/bitcartcc-orb
  created to reduce duplication across our repos, can be used by others in circleci to efficiently build multiarch images and not only that
- Updated to Node 14 LTS in node-based images
- Many package upgrades, fixing some security issues found in them
- Added new `tor-relay` component allowing you to run your own tor relay as part of bitcartcc deployment and to support tor network
- Our go cli now supports specifying custom daemon url instead of defaults, uses our spec to show more readable exception messages and is built by our CI now
- Fix invoice products access control security issue
- We now use batch inserts where possible to improve performance on e.g. stores with many wallets connected

## 0.5.0.0

### Major update

This update contains many backwards-incompatible changes

This update is the biggest of all the time, with over 5000 line additions and deletions, more than 121 files changed.

It has finished most of the parts of our Backend Improvements in our roadmap.

There are lots of internal improvements, not all changes are user-facing, but there are lots of critical bug fixes and quality improvements.

This update also fixes some not very critical, but security issues, upgrade is recommended to everyone.

This update starts the era of refreshed, lighter and better BitcartCC.
New features should now be added way faster due to amount of work done on improving maintenance work

There should be no action required to upgrade, everything will be performed automatically.
If it has failed, please let us know.

This changelog contains quite a bit of additional technical information than usual due to the nature of this update.

### Major refactor of all our backend code

We have re-organized all our code into their corresponding directories, so it is now less cluttered, even more readable and easier to add new features (i.e. `crud.py` into `crud` directory, `utils.py` into `utils` directory, utils are now split into files by their category)

All the endpoints were re-organized into logical sub-urls.
See breaking changes below for more information on how to migrate.

Improved texts handling in the database

All imports now use absolute names, code is more readable

Added new utilities for database management and made all the code use it, it will allow easier database access from plugins (to be added later) and scripts.

This allowed us to greatly reduce code duplication, and in the process we found and fixed many bugs.

For example, loading related invoice's products, or store's wallets and notifications is now done automatically, as well as updating references in the database. Before it was duplicated and had some bugs.

As all database access is now done by those functions, in the future we may add additional events or logs for those queries to be used by scripts

In the future those refactors will allow us to batch insert needed data, greatly improving performance for stores with many wallets connected, for example

### Test suite rewriten from scratch, new regtest tests added

Our test suite was rewritten from scratch, now each test doesn't depend on each other, which means that our tests are fully correct and can't pass while some issue still exists.

So now if one test fails the whole test suite doesn't fail with it together.

Improved tests helped us indentify many bugs.

We now have added regtest functional tests which help us test the pay flow, here's how it is done:

We run tests in an isolated environment (fresh database) in regtest network

The test creates a store, then sets transaction_speed (we test all variants), creates an invoice, pays it from the full node

Beforehand it starts a simple http server, sets notification_url to that server's url. Server on POST request just sends it's message later on, and then we check that two IPNs were sent in each case: `paid` status, and `complete` status

That way the whole payment processing workflow is now tested

We now test invoice response structure (i.e. payment methods) better

We now test different validation we have better

Improved CI testing process, it is now possible to publicly view test reports by anyone

Our SDK is now tested in 3 python versions instead of one, with regtest tests running on the base BitcartCC version (currently python 3.7)

### Breaking: Unique string ID

Now all objects IDs are strings.

All previous IDs will remain the same.

Newly generated IDs will be generated from a cryptographically secure source.

This change is breaking, but has been requested for a while, because it greatly improves privacy. It is no longer possible to sequentically scan for all wallet's addresses by opening checkout pages with IDs from 1 to N. It is also not possible to know the exact number of invoices on an instance.

Object id length is 22 for invoices and products, and 32 for other products.

As IDs are now longer than few characters, in the admin panel, for object ids with length > 22 they will be truncated and it will be possible to copy them on click

Payment methods order is now fully guaranteed by having a created date, existing data should be migrated automatically (but the created date of existing methods will not match the actual date)

As All object IDs are now strings, not integers, you should remove integer checks and conversions in your calls to API.

Existing ids will be returned as strings, so instead of id 42 you will receive id "42"

All upgrades should be performed automatically

As unique id is now in place, existing deployments will be unaffected, but on new deployments, the first created store by server admin becomes the default store at the store POS. Before that, store POS displays no store.

### Important security fixes

Before it was possible to create a store with wallets current user doesn't own from API. It didn't leak privacy, but that was allowed. This issue is now fixed.

There was added a check that ensures that all related objects (i.e. wallets connected to store, products connected to invoice, etc) are owned by the current user.

Otherwise, a HTTP 403 Forbidden code is returned and operation is cancelled.

Also, it was possible to create products on store current user does not own, and other similar issues. Unfortunately there were quite a lot of such.

All access control issues were fixed, upgrade is recommended.

We try our best to build the most secure software possible, but we need your help. The bigger our community becomes, the more developers will be available to audit our code and help us identify some issues quickly.

As sometimes it's hard to find unpredictable behaviour in your own code.

Tests were added to proove that no such issues will arise in the future.

### Quality of life improvements

- Improved PATCH methods: to update objects from API no fields are required, there is no need to pass unnecessary fields (`user_id`, `wallets`) to just change store's name for example! Before it was impossible to update objects from API without additional API call to fetch those requires fields. Some fields required weren't required even on object creation. This shouldn't be an issue now.
- Added IPN sending logs: on success it will say that sending IPN succeeded, otherwise it will log an error message to help diagnose issues
- Added better pagination in admin panel to easily navigate between pages. The pagination buttons allow you to jump to the first, last page and some pages inbetween instead of constantly clicking "next" button.

### Breaking: removed PUT http method

We have Removed PUT http methods because they weren't used and not tested enough, therefore they could lead to unexpected issues if used.

Also see the PATCH method improvements

### Breaking: renamed endpoints

Due to our refactors and re-organization, here's a list of renamed endpoints:

`/rate` -> `/cryptos/rate`

`/fiatlist` -> `/cryptos/fiatlist`

`/categories` -> `/products/categories`

`/services` -> `/tor/services`

`/updatecheck` -> `/update/check`

`/crud/stats` -> `/users/stats`

`/wallet_history` -> `/wallets/history`

Note: it is no longer possible to open `/wallets/history/0` to get wallet history for all wallets on your account, added a new endpoint for that:

`/wallets/history/all`

### Misc changes

- Fixed search in admin panel in pages other than invoices page
- Fixed objects template editing
- Better logo rendering in dark mode
- New SDK method: get_invoice to get lightning invoice data
- Fixed rare bug with error on editing store checkout settings
- Fixed an issue with wallet's xpub validation not always running when creating from API
- PATCH: fixed issues with modifying store checkout settings from API, changes only changed settings, others remain unaffected (before they were reset to defaults)
- Disallowed modifying invoice products after creation
- When creating notification providers, we now validate that notification provider selected is supported, otherwise the operation is cancelled (to avoid issues with not-existing providers on invoice completion)
- Fixed policies update endpoints' returning incorrect response data (fields not updated) sometimes
- Fixed an issue where /wallet_history returned wallet history of all wallets on a server, not of current user
- Fixed bitcart-cli builds

## 0.4.0.0

### Major update

This update contains backwards-incompatible changes

### Changing current instance's settings via admin panel

It is now possible to change current instance's settings via admin panel's configurator.

Editing current instance settings (and pre-loading them via configurator) is only available to server admins.

By clicking on current instance mode, if you are server admin, your current settings will be loaded and filled in the form fields.

The app will automatically connect to your server via SSH and apply new settings.

Note: it is not possible to view deployment log when updating your current instance, as the process performing the update gets restarted.

Note: for that to work you should have working SSH support, see below.

Note that even though configurator should fit most use cases, if you are not using one-domain mode, or if you
have some completely custom and complex use-case, possibly involving multiple deployments on the same server, you should better
use setup scripts from CLI.

### Breaking: SSH support in setup scripts

Old method of executing commands on the host (for maintenance purposes, like updating the server) is no longer used.

It means that there will be no listener process started anymore.

Instead, both maintenance commands and configurator's current instance mode use SSH support.

When running `./setup.sh`, BitcartCC configures itself to use system host keys.

On first startup, it generates an SSH key, and adds it to the list of trusted keys in the host (usually `~/.ssh/authorized_keys`)

That way, it can connect to the host via ssh, which is a way better way of executing commands, which opens doors to new possibilities.

Note: SSH support is only enabled when `BITCART_ENABLE_SSH` is set to `true`, by default it is so.

Note: SSH support requires an ssh server (`openssh-server`/`sshd`) to be running on the host machine.

**IMPORTANT**: For existing deployments, after updating, for future updates to work, you will need to re-run `./setup.sh`

### Many improvements in the configurator

In Remote deployment mode, there is now a button "Load settings", which will connect to the server via SSH and fill in it's settings
in the form fields.

Configurator should now be responsive and look better on mobile devices.

Configurator now removes stale tasks data from redis (if it was created more than a day ago).

### Other improvements

- Fix cleanup command
- Fix bugs in configurator
- Improve wallet loading logic in BitcartCC Core daemons
- Added support for build-time environment variables to docker-compose generator
- Maintenance updates for dependencies

## 0.3.1.1

Fixed configurator long-running deployments

## 0.3.1.0

BitcartCC Configurator now supports installing to remote servers via ssh!

Added restart server management command

Added ability to make email optional on store POS

Improved additional components handling in the docker deployment, and added ability to preview settings

Fixed stats refresh in the admin panel

Made the tor services page more clear

## 0.3.0.1

Fixed underpaid amounts calculation

Fixed admin panel in one-domain mode

## 0.3.0.0

### Major update

This update contains backwards-incompatible changes

### Completely improved docker deployment

We now test if deployment works in our automated systems, so that it will always work

Set up formatting and proper linting

Major improvements to the setup scripts:

New scripts:

- `restart.sh`, to restart the server
- `changedomain.sh`, to change domain (usage: `./changedomain.sh newdomain.tld`)

Added more validation to `setup.sh` (i.e. it is not possible to enter an invalid host anymore)

Added ability to change the root path where service is running by setting `BITCART_SERVICE_ROOTPATH` (i.e. `BITCART_STORE_ROOTPATH`)

Added new settings to configure nginx reverse proxy:

- `REVERSEPROXY_HTTP_PORT` - the http port nginx is running on (default 80)
- `REVERSEPROXY_HTTPS_PORT` - the https port nginx is running on (443)
- `REVERSEPROXY_DEFAULT_HOST` - the host to be served by default from server ip (default: none)

Overall generator refactor

#### One domain support

Existing deployments will be unaffected.

If reverse proxy is enabled and `BITCART_ADMIN_HOST` and `BITCART_STORE_HOST` and `BITCART_ADMIN_API_URL` and `BITCART_STORE_API_URL` are all unset, one domain mode is enabled.

For one domain mode, only one setting is used: `BITCART_HOST`.

It will determine the only domain bitcartcc will run on.

The 3 main services will run under different routes.

There is a root service, running at domain root. The root service is selected in the following order (if available): store, admin, api

By default, assuming `BITCART_HOST` was `bitcart.local`:

- the store will run on `bitcart.local`
- admin on `bitcart.local/admin`
- api on `bitcart.local/api`

Everything will be configured to work on one domain.

To enable one domain mode for existing deployments:

```bash
unset BITCART_ADMIN_HOST
unset BITCART_STORE_HOST
unset BITCART_ADMIN_URL
unset BITCART_STORE_URL
./setup.sh
```

#### Breaking change to improve readability

The following environment variables were renamed to reduce confusion:

- `BITCART_ADMIN_URL` -> `BITCART_ADMIN_API_URL`
- `BITCART_STORE_URL` -> `BITCART_STORE_API_URL`
- `BITCART_ADMIN_ONION_URL` -> `BITCART_ADMIN_API_ONION_URL`
- `BITCART_STORE_ONION_URL` -> `BITCART_STORE_API_ONION_URL`

Please set them in order for your deployment to work

### BitcartCC Configurator

This release included an alpha version of BitcartCC Configurator.

For now only manual deployment is supported.

BitcartCC Configurator is an application in your admin panel, allowing to install new BitcartCC instances (via ssh or manual generated script) and to re-configure them with ease.

Just enter needed settings and you will get a copiable script.

By default it can be accessed by anonymous users.

Added a new server policy to make it available for authorized users only (default: False)

## 0.2.3.1

Fix invoice creation for fiat currencies without a symbol

Don't create duplicate make expired tasks on startup

## 0.2.3.0

Maintenance release. Use deterministic requirements, decrease docker image sizes, fix some fiat currencies not being displayed

## 0.2.2.0

This release is mostly a bugfix release, but with a few new features too.

### Full invoice tasks handling refactor

Now there is only one expired task created for an invoice, instead of N (where N is the number of payment methods).

It means that BitcartCC should use less RAM, and also there will be less edge cases and duplicate IPN sent.

Also, to handle some rare cases if gunicorn workers are restarting, we have changed the way background tasks are handled.

Technical details:
The idea is to make every background task, and every asyncio task run in background worker, and not gunicorn ones.

Background worker listens on a redis channel for events, and gunicorn workers publish messages to the channel. Worker parses messages and executes event handlers in separate asyncio tasks.

### Fixed local deployment

Now local deployment via .local domains works as before, and it now modifies /etc/hosts in a clever way, avoiding duplicate entries

### Other changes

- Admin panel now displays a helpful message when invoice has no payment methods connected
- Fixed recommended fee in case it's unavailable.
- Tor extension now doesn't log always, instead it logs only warnings if something was misconfigured.
- Fixed IPN sending
- Fixed logging in docker environment
- Fixed pagination for id 0
- Added ability to change fiat currency used in the /rate endpoint
- Fixed websockets' internal channel ids clash sometimes

## 0.2.1.1

Fix multiple store support on POS

## 0.2.1.0

Fix image uploading

Allow decimal values for `underpaid_percent`

Multiple stores on one store POS instance - new `/store/{id}` URLs added to serve any store

Default store served is still configured by server policies

## 0.2.0.2

Bugfixes in recommended fee calculation (GZRO)

## 0.2.0.1

Bugfixes in recommended fee calculation (BCH)

## 0.2.0.0

### Major update

This update contains numerous changes, some of which are not backwards-compatible

### New payment statuses

This update completely changes our status system, by adding new statuses: `paid` and `confirmed`.

`Pending` status was renamed to `pending`

New store setting, `transaction_speed` added, which controls when should invoice be marked as complete

New transaction flow:

Invoice created -> pending

Payment received -> paid

Payment has >= 1 confirmation -> confirmed

Payment number of confirmations is >= `transaction_speed` of the store OR it is a lightning invoice -> complete

Payment expired -> expired

If payment was detected within the invoice time frame, and the payment expired, it won't be set to expired but instead wait for confirmations.

For more details read this:
https://docs.bitcartcc.com/guides/transaction-speed

### A lot of new store checkout settings

- Underpaid invoices support. For example, if customer sends from an exchange wallet, it might deduct the fees from amount sent. This way you can accept customer's invoice.

  More details [here](https://docs.bitcartcc.com/support-and-community/faq/stores-faq#what-is-underpaid-percentage)

- Custom logo support. [Details](https://docs.bitcartcc.com/support-and-community/faq/stores-faq#what-is-custom-logo-link)
- Dark mode support. [Details](https://docs.bitcartcc.com/support-and-community/faq/stores-faq#what-is-the-use-dark-mode-setting)
- Recommended fee support. Recommended fee will be displayed in all onchain payments methods. [Details](https://docs.bitcartcc.com/support-and-community/faq/stores-faq#recommended-fee)

### Multiple wallets of the same currency support

Before, it was disallowed to create an invoice with multiple wallets of the same currency (only one was picked).

Now it is allowed, and in the checkout, payment methods will be indexed.
For example, if you have 2 btc and 2 ltc wallets connected with lightning enabled, here's how it would look:

- BTC (1)
- BTC (⚡) (1)
- BTC (2)
- BTC (⚡) (2)
- LTC (1)
- LTC (⚡) (1)
- LTC (2)
- LTC (⚡) (2)

A new `name` attribute was added to PaymentMethod's structure, which contains pre-formatted payment method name ready for display

### Maintenance

All dependencies of packages has been upgraded, and two maintenance releases were made: of SDK, to make new release with a new license,
and of BitCCL, to fix it's use together with SDK 1.0

### Quality of life improvements

- By pressing enter in the edit dialog, it will be automatically saved (like in login page, enter to login)
- Added new mark complete batch action, to be able to mark some invoices complete manually. All notifications, emails and scripts will be executed.
- Added filters to admin panel, it is now possible to easily filter out paid or invalid invoices

### Misc changes

- Fixed payment methods order being inconsistent sometimes
- Fixed scrollbars in checkout page being shown on different screen resolutions
- Tor extension logs are now DEBUG level instead of INFO (less log spam)
- Fixed patch/put methods, it is now possible to completely disconnect notifications from store
- Fixed stale expired invoices occuring in rare cases

## 0.1.0.2

Fixed html template rendering and product price is now properly formatted when using it in templates
Fixed UI issues with the new checkout in Firefox.
Details are now displayed differently in admin panel:
The name of the field is on one line, and the actual data on the next line.
Template's text is now hidden into item details.

## 0.1.0.1

Small bugfixes

Various visual, performance improvements and fixes in the admin panel (now using vuetify 2.3.x)

## 0.1.0.0

### Major update

This update contains numerous changes, some of which are not backwards-compatible

### Lightning network checkout

Lightning has been supported in BitcartCC Core Daemons for a long time, but not in our payment methods.

Now BitcartCC fully supports Lightning Network as a checkout method too!

Lightning Network is supported via BitcartCC daemons's lightning mode.

It means that, there is still no need to install additional software, lightning is enabled just by one setting.

To enable lightning, just run:

```bash
export COIN_LIGHTNING=true
```

For each `COIN` (i.e. `BTC`, `LTC`) where you want to enable lightning support.

It will start a lighning gossip in the daemon, and enable the ability to perform lightning operations.

Lightning is currently only supported in native segwit wallets (electrum implementation limitation).

To enable lightning, visit wallets page, click on lightning icon, read all the warnings displayed.

Currently there are lots of limitations and issues in the Lightning Network itself, and the Electrum implementation, so proceed only if you understand that you may risk losing your funds, as Lightning Network is experimental.

But if you agree, press the green button, and lightning in the wallet will be enabled.

Lightning network is supported individually in each wallet, so even non-admin users can utilize it!

Each wallet can be considered an individual lightning node, or, better said, an account on the same lightning node.

So for each wallet you will have to open new lightning channels.

As lightning implementation is built-in in BitcartCC, it is not possible to use other implementations, and you will have to open channels from scratch.

Please read the warning in the admin panel for more details.

When enabled, and when creating an invoice, along with the regular currency checkout method, a lightning one will be created too.

On checkout, the customer will be able to scan/copy lightning invoice, and your node id, if they need to open a channel with you.

When paid, instantly you will see that invoice has been paid.

As every wallet is a fresh node, you will need a way to manage your lightning channels.

If you click on lightning icon near the wallet again, you will see a lightning management page.

It will display your lightning balance, node id and your lightning channels.

You are able to close or force-close channels from there.

Also you can open a new lightning channel or pay an lightning invoice from your lightning node in that same page.

When invoice has been paid, you will see the paid currency will have the lightning icon near it.

Also, all paid currencies are now upper-case, your existing data will be migrated.

To support lightning network, invoice data returned from API was changed.

`payments` key is now a list, and not a dictionary.

There are other changes to the API, please read the other release features below.

Also, new endpoints were added:

- `/wallets/{wallet_id}/checkln` endpoint to check if lightning is supported for a wallet.
  Returns False if not supported, node id otherwise

- `/wallets/{wallet_id}/channels` endpoint, returning wallet's lightning channels
- `/wallets/{wallet_id}/channels/open` endpoint, allowing to open a new lightning channel
- `/wallets/{wallet_id}/channels/close` endpoint, allowing to close a lightning channel
- `/wallets/{wallet_id}/lnpay`, allowing to pay a lightning invoice from your lightning node

To support lightning network, the daemon now has a new method: `get_invoice`, to get invoice by it's `rhash`.

### Improved checkout page

To support lightning, as there are now even more checkout methods, will have listened to your suggestions, so now, currency selection is not tab-like,
but it's a select list.

Changed the checkout modal layout, now it is more minimalistic and takes less space.

The exchange rate is now displayed in a pretty rate, and formatted correctly.

Added open in wallet button, which should launch user's application to automatically paste all the details to perform a payment.

Instead of displaying qr code and texts at once, and, considering that lightning invoices are big, we now have split the checkout into two tabs:
Scan and Copy.

Scan tab will show a qr code

and Copy tab will display the texts, but as lightning invoices are long, it will display only parts of it, and by clicking on the fields, the full text
will be copied

When on a lightning payment method, you will be able to switch between lightning invoice qr code and node id qr code.

The checkout page in the store was changed in a similar way.

### Added help texts to some fields

To help newcomers, some special fields now have a question mark icon near them, by clicking on which, user will be redirected to our docs.

It should help to understand some basics without asking, right from your instance.

### Added ID field everywhere

As requested, ID field was added to each datatable. It was possible to copy id before by clicking on copy icon, but now it's also displayed as a field

### Better money formatting

Do you remember weird amounts in the checkout before, like

1 BTC = 25000.424242 USD

When USD can have maximum of 2 decimal places?

It is finally fixed!

Now, every amount will be formatted as per it's currency settings.

Also, the rate string is now fancier than before, it can contain currency symbol and it's code.

There are some breaking changes to make it working

Now every amount in the payment methods is not a Decimal, but a string, which was already formatted for you.

Also, every payment method now has a `rate` field, which will contain a computer-readable formatted Decimal of the exchange rate at the moment of invoice creation.

Also every payment method now has a `rate_str` field, which is a human-readable pretty-formatted rate string, ready to be used in checkout

### Major task system and logging refactor

Now all background tasks are running only in the worker
process, and not in every worker ran by gunicorn

Instead of using local process state, fetched and parsed data is now
placed in redis, and fetched from there by workers serving requests.

Now, instead of each process logging concurrently, which lead to race
condition (like, having logs from yesterday contain today's logs), each worker uses sends request to logging
server, which is ran as part of the main background worker.

What does it mean?

It means that BitcartCC deployments should use way less RAM, should have less issues and work more stable.

Plus it means that logging system now works correctly

Logs in the admin panel are now sorted, and it is now possible to remove individual logs or clean them all.

Tor extension is now refreshed every 15 minutes instead of every 2 minutes to reduce logs spam.

### Added configuration samples and documented every setting

Every setting supported by BitcartCC that is configured by an environment variable is supported.

Now, the conf directory of your cloned BitcartCC repo contains more samples:

- .env.sample was cleaned up from unused settings, and now every setting is documented
- .env.dev.sample was added, which contains the configuration we use when developing BitcartCC

### Misc changes

- Fixed worker start on Mac OS
- Pending invoice processing will no longer stop processing on error in one of the invoices
- Added wallet balance endpoint, `/wallets/{wallet_id}/balance`, which returns a dictionary with 4 keys:
  `confirmed`, `unconfirmed`, `lightning` and `unmatured`.
- Various bugfixes and performance improvements
- Added an easter egg (:

## 0.0.0.3

### Logging system

We now have logging system set up for our merchants API.

It means that it'll be easier to debug issues, as it is now possible to view logs from admin panel.

You can view logs (collected each day), and download them if needed for others to help to fix your issue.

### Admin panel responsibility improvements

Admin panel should now work better on mobile, especially in server management page.

### Other changes

Search input in admin panel now no longer searches all related tables, but only the one you are currently viewing.

Fixed a bug where if you have passed products=`None` to API it would crash.

Update check now doesn't even start to run if update url is not set

Admin panel's wallets creation dialog currency field is now a dropdown-to avoid entering invalid fields.

## 0.0.0.2

Removed non-working settings page from admin panel

## 0.0.0.1

First BitcartCC release with a version!
