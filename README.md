# C63AMG Paper Tracker

7-day **simulation only** of following public Polymarket trades of [C63AMG](https://polymarket.com/ru/@c63amg). Initial balance: $1,000. No wallet credentials or real trading.

GitHub Actions will collect public fills about every 5 minutes (scheduling can be delayed). The dashboard will be published with GitHub Pages once Pages is enabled. It is not suitable for sub-second execution or real-money trading.

**Setup:** Settings → Pages → Build and deployment → Source: GitHub Actions; then Actions → C63AMG Paper Tracker → Run workflow.

The first successful poll only establishes a baseline, and the seven-day paper test starts at that point. This program simulates taker prices from visible bids/asks and records missed signals and price slippage. Its results are illustrative rather than assured trading returns.

**Public visibility:** GitHub Pages sites are public unless a supported private Pages feature is configured. The tracker publishes synthetic balances and public-market positions; no secrets.


## Telegram alerts (optional)

The bot **never places real trades**. Notifications are delivered only after public source trades are detected by the scheduled GitHub Actions job, so they may be delayed by several minutes.

**One-time setup:**

1. Open the official [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot`, and create a bot. **Keep its token secret**; do not paste it into chat or commit it to the repository.
2. Open [GitHub Actions secrets](https://github.com/dgorshenin555-commits/c63amg-tracker/settings/secrets/actions). Create repository secret `TELEGRAM_BOT_TOKEN` with the token you received.
3. In Telegram, open **your newly created bot** and press **Start** (or send `/start`).
4. Open [C63AMG Paper Tracker Actions](https://github.com/dgorshenin555-commits/c63amg-tracker/actions/workflows/paper-tracker.yml), click **Run workflow**, choose **discover** as `telegram_action`, and run it. Open that run's **Discover Telegram chat ID** step: it will print the numeric ID of the Telegram conversation that sent `/start`.
5. On the GitHub Actions secrets page, create `TELEGRAM_CHAT_ID` with that ID.
6. Run the workflow again with `telegram_action = test`. You should receive a test Telegram message. A run may take a few minutes to start.

**Default:** one consolidated Telegram alert per polling run *only when paper trades have actually been copied*. Skipped trades do not produce notifications.

To also receive alerts about new observed C63AMG trades that were **not** copied, create a repository **Actions variable** named `TELEGRAM_NOTIFY_MODE` with value `all`. The default is `copied`. Avoid `all` if the trader is very active: it can be noisy.

If either Telegram secret is missing, the notification step skips delivery without affecting the monitoring or dashboard. Telegram errors are shown in Actions logs but do not fail the paper-trading job. No historical alerts will be sent retroactively.
