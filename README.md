# Facebook Marketplace Alert

This Python script monitors Facebook Marketplace through the ScrapeAtlas MCP API and sends new listing notifications to a Discord channel using a Discord webhook.

## Features

- Searches Marketplace for a configurable item.
- Supports multiple places and a configurable radius.
- Supports minimum and maximum price filters.
- Checks for new listings on a recurring schedule.
- Avoids sending duplicate alerts.
- Sends listing title, price, location, image, and link to Discord.
- Can run continuously or perform one check with `--once`.
- Caches resolved place coordinates locally.

## Requirements

- Python 3.8 or newer.
- A ScrapeAtlas API key.
- A Discord webhook URL.
- Internet access.

The script uses only Python's standard library. No extra packages are required.

## Configuration

Open [alert.py](./alert.py) and edit the settings near the top:

```python
ITEM       = "Motor"
MIN_PRICE  = None
MAX_PRICE  = 200000
PLACES     = ["Pasig"]
RADIUS_KM  = 20
CHECK_EVERY_SECONDS = 300
WEBHOOK_URL = "your Discord webhook URL"
API_KEY     = "your ScrapeAtlas API key"
ALERT_ON_EXISTING = False
```

### Settings

| Setting | Description |
| --- | --- |
| `ITEM` | Marketplace search term. |
| `MIN_PRICE` | Minimum listing price, or `None` for no minimum. |
| `MAX_PRICE` | Maximum listing price, or `None` for no maximum. |
| `PLACES` | List of city, town, or province names to search. |
| `RADIUS_KM` | Search radius around each place. |
| `CHECK_EVERY_SECONDS` | Number of seconds between searches. |
| `WEBHOOK_URL` | Discord webhook destination. |
| `API_KEY` | ScrapeAtlas API key. |
| `ALERT_ON_EXISTING` | If `True`, alerts for listings already present on the first run. |

For better security, do not commit real API keys or webhook URLs. If a credential has been exposed, revoke or rotate it before using the project.

## Running

Open PowerShell or Command Prompt in this folder:

```powershell
cd C:\path\to\marketplace_alert
```

Run continuously:

```powershell
python alert.py
```

Run one search and exit:

```powershell
python alert.py --once
```

The program prints the resolved places, search status, new alerts, and errors in the terminal.

## First run behavior

By default, the first run creates a baseline of currently available listings and does not alert for those existing listings:

```python
ALERT_ON_EXISTING = False
```

Set it to `True` if the existing listings should also generate Discord notifications.

## Local files

The script creates and updates:

- `marketplace_state.json` — stores listing IDs already seen and completed search baselines.
- `places_cache.json` — stores resolved coordinates for configured places.

These files are local runtime data and are ignored by Git. Removing them resets the alert history and causes places to be resolved again.

## Optional environment variables

The following variables can override the ScrapeAtlas connection settings:

| Variable | Default |
| --- | --- |
| `SCRAPEATLAS_MCP_URL` | `https://api.scrapeatlas.com/mcp` |
| `SCRAPEATLAS_AUTH_HEADER` | `Authorization` |
| `SCRAPEATLAS_AUTH_PREFIX` | `Bearer ` |

Example in PowerShell:

```powershell
$env:SCRAPEATLAS_MCP_URL = "https://api.scrapeatlas.com/mcp"
$env:SCRAPEATLAS_AUTH_HEADER = "Authorization"
$env:SCRAPEATLAS_AUTH_PREFIX = "Bearer "
```

## Troubleshooting

### No valid places to search

Check the names in `PLACES`. Use recognizable city, town, or province names. The first matching location returned by ScrapeAtlas is cached.

### No alerts on the first run

This is expected when `ALERT_ON_EXISTING` is `False`. The script is establishing its baseline.

### Out of credits

ScrapeAtlas searches consume credits. Increase `CHECK_EVERY_SECONDS`, reduce the number of places, or add credits to the ScrapeAtlas account.

### Discord webhook errors

Confirm that the webhook URL is complete, active, and connected to the expected Discord channel.

### Duplicate or missing notifications

The script tracks listing IDs in `marketplace_state.json`. Delete that file only if you intentionally want to reset the alert history.

## Security and usage

- Treat the ScrapeAtlas API key and Discord webhook URL as secrets.
- Do not publish credentials in source code or screenshots.
- Rotate credentials that have been exposed.
- Keep the webhook channel restricted to trusted users.
- Use the script in accordance with Facebook Marketplace, ScrapeAtlas, Discord, and applicable local terms.
