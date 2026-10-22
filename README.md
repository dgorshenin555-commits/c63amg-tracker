# C63AMG Paper Tracker

7-day **simulation only** of following public Polymarket trades of [C63AMG](https://polymarket.com/ru/@c63amg). Initial balance: $1,000. No wallet credentials or real trading.

GitHub Actions will collect public fills about every 5 minutes (scheduling can be delayed). The dashboard will be published with GitHub Pages once Pages is enabled. It is not suitable for sub-second execution or real-money trading.

**Setup:** Settings → Pages → Build and deployment → Source: GitHub Actions; then Actions → C63AMG Paper Tracker → Run workflow.

The first successful poll only establishes a baseline, and the seven-day paper test starts at that point. This program simulates taker prices from visible bids/asks and records missed signals and price slippage. Its results are illustrative rather than assured trading returns.

**Public visibility:** GitHub Pages sites are public unless a supported private Pages feature is configured. The tracker publishes synthetic balances and public-market positions; no secrets.
