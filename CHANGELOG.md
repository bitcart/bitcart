# Release Notes

## Latest changes

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
