# UConn Course Waitlist Monitor

Automated course availability monitor for UConn Student Admin. Checks the student admin Shopping Cart to determine whether classes are open.

## Architecture

**Two-Phase Design:**
- **Phase 1 (agent.py):** Selenium-based authentication
  - Handles CAS login
  - Processes Duo MFA
  - Captures session cookies, headers, and state tokens
  - Only runs when session expires or is missing

- **Phase 2 (worker.py):** HTTP-based polling
  - Uses saved session data
  - Fetches and parses Shopping Cart
  - Detects session expiration
  - Automatically triggers Selenium refresh
  - Sends Discord notifications

## Requirements

- Python 3.8+
- Microsoft Edge browser
- Edge WebDriver (must be in PATH)
- Discord webhook URLs

## Installation

1. Clone or download this repository

2. Install dependencies
```
pip install -r requirements.txt
```
3. Create a Discord server and configure webhooks

**Create webhooks**
   - Go to Server Settings → Integrations → Webhooks
   - Click New Webhook
   - Select the text channel you want the webhook to post to
   - Copy the Webhook URL and paste to `creds.json`
   - Repeat for each channel (you need at least 3 channels/webhooks total)

4. Adjust or create credentials file at `creds/creds.json`:
```json
{
    "username": "your_netid",
    "password": "your_password", 
    "duo_webhook_url": "https://discord.com/api/webhooks/...",
    "course_webhook_url": "https://discord.com/api/webhooks/...",
    "error_webhook_url": "https://discord.com/api/webhooks/..."
}
```
## Usage

### Manual Execution

Run the worker directly:
```bash
python3 worker.py
```

The worker will:
1. Load or refresh session data
2. Fetch Shopping Cart page
3. Parse course availability
4. Send Discord notification
5. Exit

### Automated Monitoring (Cron)

Add to crontab for periodic monitoring:
```bash
crontab -e
```

Example (check every 15 minutes):
```cron
*/15 * * * * /usr/bin/python3 /full/path/to/worker.py
```

**Important:** Only schedule `worker.py` in cron. Never schedule `agent.py` directly.

## How It Works

### First Run
1. `worker.py` detects missing `session.json`
2. Calls `agent.py` to perform Selenium login
3. Duo verification code sent to Discord (duo_webhook_url)
4. User approves Duo push notification
5. Session data saved to `creds/session.json`
6. Worker fetches and parses Shopping Cart
7. Results sent to Discord (course_webhook_url)

### Subsequent Runs
1. Worker loads existing session from `session.json`
2. Fetches Shopping Cart via HTTP (no browser needed)
3. Parses course data
4. Sends Discord notification

### Session Expiration
When session expires:
1. Worker detects CAS error message in response
2. Automatically triggers Selenium refresh
3. New Duo approval required
4. Session data updated
5. Worker continues polling

## Logs

Two separate log files in `logs/`:

**activities.txt**
- INFO level only
- Normal workflow, successful fetches, etc.

**errors.txt**
- ERROR level only
- Selenium failures, HTTP errors, etc.

Both logs use 5MB rotation with 3 backup files

## Troubleshooting

### "Edge WebDriver not found"
Ensure Edge WebDriver is installed and in PATH:
For Linux
```bash
which msedgedriver
```
For Windows

```cmd
where msedgedriver
```

### Session keeps expiring
- Check system time accuracy
- Verify UConn hasn't changed authentication flow
- Check logs/errors.txt for details

### No courses found
- Verify Shopping Cart has courses added in PeopleSoft
- Check that course grid HTML structure hasn't changed
- Review logs/activities.txt for parsing details

### Discord webhook failures
- Verify webhook URLs are correct
- Check Discord server permissions
- Ensure webhook hasn't been deleted

### Duo not working
- Verify Duo is enabled on your account
- Check duo_webhook_url is correct
- Ensure you approve push notification within timeout (30 seconds)

## Security Notes

- `creds/creds.json` contains plaintext credentials (don't push creds.json onto GitHub)
- Use file permissions to restrict access:
  ```bash
  chmod 600 creds/creds.json
  ```
- Consider using environment variables instead of creds


## Known Limitations

- Element IDs in PeopleSoft are dynamic and may change
- Only Edge is officially supported

## TO DO
- Refactor code for clarity and optimization
- Add support for alternative browsers (Chrome, Firefox)
- Optional: Rewrite worker.py in compiled language for faster HTTP requests
