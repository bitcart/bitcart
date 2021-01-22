# Release Notes

## Latest changes

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
