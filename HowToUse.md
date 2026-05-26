# 📖 How To Use — Instagram MCP Server

Complete setup and usage guide for macOS (Apple Silicon & Intel).

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Setup (Recommended)](#2-quick-setup-recommended)
3. [Manual Installation Steps](#3-manual-installation-steps)
   - [Python Installation](#31-python-installation)
   - [Virtual Environment Setup](#32-virtual-environment-setup)
   - [Install Dependencies](#33-install-dependencies)
   - [Playwright Installation](#34-playwright-installation)
4. [macOS Permissions](#4-macos-permissions)
5. [Browser Setup](#5-browser-setup)
6. [Configure .env](#6-configure-env)
7. [AI Client MCP Configs](#7-ai-client-mcp-configs)
   - [Claude Desktop](#71-claude-desktop)
   - [Gemini CLI](#72-gemini-cli)
   - [Cursor](#73-cursor)
   - [Antigravity](#74-antigravity)
8. [Running the MCP Server](#8-running-the-mcp-server)
9. [Session Management & Multi-Account Support](#9-session-management--multi-account-support)
10. [Example Prompts](#10-example-prompts)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

| Requirement | Version | Check command |
|-------------|---------|---------------|
| macOS / Windows | macOS 12+ / Win 10+ | `sw_vers` / systeminfo |
| Python | 3.11+ | `python3 --version` |
| Chrome or Brave | Latest | Open browser |
| pip | Latest | `pip --version` |

---

## 2. Quick Setup (Recommended)

This project features a fully automated, **venv-first and interpreter-isolated** bootstrap installer. It probes available system Python paths, verifies version/module requirements, builds a local virtual environment (`.venv`), installs all dependencies, downloads Playwright's Chromium binary inside `.venv`, registers Claude Desktop, and runs validation checks.

### macOS & Linux
```bash
cd /Users/devdaskumar/Desktop/Code/instagram-mcp
./quick_setup.sh
```

### Windows
```cmd
cd /d C:\path\to\instagram-mcp
quick_setup.bat
```

The script will guide you through the process, outputting a clean log:
```
==========================================
🤖 Bootstrapping Instagram MCP Setup...
==========================================
[✓] Python 3.12 detected
[✓] Virtual environment created
[✓] Dependencies installed
[✓] Playwright Chromium installed
[✓] Claude MCP config updated
[✓] Startup validation passed
==========================================
🎉 Setup completed successfully!
==========================================
```

---

## 3. Manual Installation Steps

If the automated bootstrap installer fails or you prefer to configure components step-by-step:

### 3.1. Python Installation

#### Option A: Homebrew (macOS)
```bash
brew install python@3.12
```

#### Option B: Official Installer (macOS/Windows)
1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Run installer (On Windows: Check **"Add Python to PATH"**)

### 3.2. Virtual Environment Setup
Ensure you initialize and activate the local environment directly:
```bash
# Create environment
python3 -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# Activate (Windows CMD)
.venv\Scripts\activate.bat
```

### 3.3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Expected packages: `mcp`, `fastmcp`, `playwright`, `aiosqlite`, `python-dotenv`, `pydantic`, `rich`.

### 3.4. Playwright Installation
Install Playwright Chromium binary directly into the virtual environment:
```bash
playwright install chromium
```

---

## 6. macOS Permissions

Playwright needs Accessibility permissions to control the browser.

### Grant Accessibility Access

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Click **+** and add your Terminal app (Terminal, iTerm2, Warp, etc.)
3. Toggle it **ON**

### Grant Screen Recording (for screenshots)

1. Open **System Settings** → **Privacy & Security** → **Screen & System Audio Recording**
2. Add your Terminal app
3. Toggle it **ON**

### Grant Automation

When running for the first time, macOS may ask:
> *"Terminal" wants to control "Google Chrome"*

Click **OK** to allow.

---

## 7. Browser Setup

### Google Chrome

1. Ensure Chrome is installed at:
   ```
   /Applications/Google Chrome.app/
   ```
2. Log in to Instagram in Chrome manually once
3. The MCP server will reuse your session

### Brave Browser

1. Ensure Brave is installed at:
   ```
   /Applications/Brave Browser.app/
   ```
2. Set in `.env`: `BROWSER_TYPE=brave`
3. Log in to Instagram in Brave manually once

### Which browser will be used?

The server auto-detects:
- If `BROWSER_TYPE=chrome` → looks for `/Applications/Google Chrome.app/`
- If `BROWSER_TYPE=brave` → looks for `/Applications/Brave Browser.app/`
- If neither found → uses Playwright's bundled Chromium (still works)

---

## 8. Configure .env

```bash
# Copy the example file
cp .env.example .env

# Edit options
nano .env
# or
open -a TextEdit .env
```

Set browser options:

```env
BROWSER_TYPE=chrome        # or brave
HEADLESS=false             # false = visible browser window (required for login)
```

**Security:** `.env` never leaves your machine. It is in `.gitignore`.

---

## 9. AI Client MCP Configs

All configs use `stdio` transport — the AI client launches the server as a subprocess.

### 9.1 Claude Desktop

**Config file location:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Add this content** (create file if it doesn't exist):

```json
{
  "mcpServers": {
    "instagram-mcp": {
      "command": "/Users/devdaskumar/Desktop/Code/instagram-mcp/.venv/bin/python",
      "args": [
        "/Users/devdaskumar/Desktop/Code/instagram-mcp/server.py",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "/Users/devdaskumar/Desktop/Code/instagram-mcp"
      }
    }
  }
}
```

**Steps:**
1. Open the config file:
   ```bash
   open ~/Library/Application\ Support/Claude/
   ```
2. Create or edit `claude_desktop_config.json`
3. Paste the config above
4. **Restart Claude Desktop**
5. The 🔌 tools icon should appear in the chat input

---

### 9.2 Gemini CLI

**Config file location:**
```
~/.gemini/settings.json
```

**Add to settings.json:**

```json
{
  "mcpServers": {
    "instagram-mcp": {
      "command": "/Users/devdaskumar/Desktop/Code/instagram-mcp/.venv/bin/python",
      "args": [
        "/Users/devdaskumar/Desktop/Code/instagram-mcp/server.py",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "/Users/devdaskumar/Desktop/Code/instagram-mcp"
      },
      "timeout": 60
    }
  }
}
```

**Steps:**
```bash
# Create/edit settings.json
nano ~/.gemini/settings.json
```

Paste the config and save. Then run:
```bash
gemini
# The instagram-mcp tools will be available
```

---

### 9.3 Cursor

**Config file location:**
```
~/.cursor/mcp.json
```

**Content:**

```json
{
  "mcpServers": {
    "instagram-mcp": {
      "command": "/Users/devdaskumar/Desktop/Code/instagram-mcp/.venv/bin/python",
      "args": [
        "/Users/devdaskumar/Desktop/Code/instagram-mcp/server.py",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "/Users/devdaskumar/Desktop/Code/instagram-mcp"
      }
    }
  }
}
```

**Steps:**
1. Open Cursor Settings → MCP
2. Or create `~/.cursor/mcp.json` manually
3. Restart Cursor

---

### 9.4 Antigravity

**Config file location:**
```
~/.gemini/antigravity-cli/settings.json
```

**Content** (same format):

```json
{
  "mcpServers": {
    "instagram-mcp": {
      "command": "/Users/devdaskumar/Desktop/Code/instagram-mcp/.venv/bin/python",
      "args": [
        "/Users/devdaskumar/Desktop/Code/instagram-mcp/server.py",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "/Users/devdaskumar/Desktop/Code/instagram-mcp"
      }
    }
  }
}
```

---

## 10. Running the MCP Server

### Stdio Mode (for AI clients — recommended)

The AI client launches the server automatically. You do **not** need to run it manually when using Claude Desktop, Cursor, etc.

### Manual Test Mode

```bash
cd /Users/devdaskumar/Desktop/Code/instagram-mcp
source .venv/bin/activate
python server.py
```

You'll see:
```
╭──────────────────────────────────────────────╮
│        🤖 Instagram MCP Server               │
│  Local-only · No cloud · No APIs             │
│                                              │
│  browser_type   chrome                       │
│  headless       False                        │
│  session_file   data/sessions/...            │
│  mcp_server     127.0.0.1:8765               │
╰──────────────────────────────────────────────╯
✓ MCP server starting…
```

---

## 11. Session Management & Multi-Account Support

This server supports a **100% manual login, session-only authentication model**. No passwords or credentials are stored or needed.

### First Run (Manual Authentication Flow)

1. Launch a browser session or ask the AI to "open browser". A visible browser window will open.
2. Instagram's login page will load automatically.
3. Manually enter your username and password in the browser window, completing any 2FA checks.
4. Once logged in, tell the AI `"I am logged in"` or run the `check_login_status` tool.
5. The server dynamically scrapes your username, creates an isolated profile subdirectory under `data/sessions/<username>/`, and saves your authenticated session state.

### Multi-Account Support

You can register and manage multiple Instagram accounts on the same machine:

- **Adding a New Account**: Call `logout_current_account` (or tell the AI `"logout"`). This clears the active tracker and opens a fresh login page. Complete the login for the new account, then run `check_login_status`.
- **Listing Accounts**: Run `list_accounts` to see all saved profiles, their last used timestamps, active status, and custom aliases.
- **Switching Accounts**: Run `switch_account(username="target_username")`. The browser context will restart using the selected account's isolated session.
- **Renaming Profiles**: Use `rename_account_alias(username="username", alias="Work Account")` to set human-readable labels.
- **Removing Accounts**: Use `remove_account(username="username")` to permanently delete an account's folder and session data.

### Storage Layout

Each account has a dedicated folder under `data/sessions/` preserving isolation:

```
data/
└── sessions/
    ├── active_account.json         ← Tracks currently active username
    ├── username_1/
    │   ├── storage_state.json      ← Cookies + LocalStorage state
    │   ├── storage_state.json.bak  ← Automatic session backup
    │   ├── metadata.json           ← Timestamps and custom alias
    │   └── screenshots/            ← Screenshots taken for this account
    └── username_2/
        ├── storage_state.json
        └── ...
```

---

## 12. Example Prompts

Use these prompts with any connected AI (Claude, Gemini, Cursor, Antigravity):

### Basic Navigation
```
Open the browser and navigate to Instagram
```

```
Take a screenshot of the current Instagram page
```

```
What is the current URL?
```

### Login & Session
```
Log in to Instagram using my saved credentials
```

```
Check if I'm logged into Instagram
```

```
Save my current Instagram session
```

### Feed & Content
```
Read my Instagram home feed and show me the first 5 posts
```

```
Scroll down my feed 5 times and show me what you find
```

```
Summarize everything visible on the current Instagram page
```

### Profile Analysis
```
Analyze the Instagram profile @natgeo and tell me their follower count, bio, and recent posts
```

```
Visit the profile @therock and save it to memory
```

```
Show me all the Instagram profiles I've analyzed before
```

### Posts & Engagement
```
Open this Instagram post and read all the comments: https://www.instagram.com/p/XXXXX/
```

```
Like the current post
```

```
Post the comment "Great shot! 📸" on the current post
```

### Reels
```
Open this reel and describe what you see: https://www.instagram.com/reel/XXXXX/
```

```
Read the comments on this reel
```

### Notifications
```
Check my Instagram notifications
```

### Memory & Notes
```
Show me all my saved screenshots
```

```
Search my memory for mentions of "travel"
```

```
Save a note: Title "Instagram Ideas", Content "Post about sunset photos"
```

```
Show me the session history
```

### Multi-step Workflow
```
1. Open Instagram
2. Check if I'm logged in
3. Read my home feed
4. Take a screenshot
5. Tell me what my top 3 most liked posts are
```

---

## 13. Troubleshooting

### ❌ "Browser not found"

**Cause:** Chrome/Brave not installed in expected location.

**Fix:**
```bash
# Check if Chrome exists
ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# If not found, either:
# 1. Install Chrome from https://www.google.com/chrome/
# 2. Or set HEADLESS=false and let Playwright use bundled Chromium
```

---

### ❌ "playwright: command not found"

**Fix:**
```bash
# Make sure venv is active
source .venv/bin/activate

# Reinstall playwright
pip install playwright
playwright install chromium
```

---

### ❌ Login status not registering

**Causes:**
- Manual login was not completed in the browser window.
- Instagram is showing a CAPTCHA or security challenge.
- Account requires 2FA that has not been approved yet.

**Fix:**
1. Ensure the browser window is open. If not, call `open_browser` or `login_instagram`.
2. Make sure you complete the authentication flow fully in the browser window until you see your feed.
3. Once logged in, run `check_login_status` to scan your profile page and save the session.
4. If the page is blocked on a security check, complete the challenge in the browser window first.

---

### ❌ "Permission denied" or "Operation not permitted"

**Fix:**

Grant Accessibility access:
```
System Settings → Privacy & Security → Accessibility → Add Terminal → Enable
```

---

### ❌ "ModuleNotFoundError: No module named 'mcp'"

**Fix:**
```bash
# Activate venv
source .venv/bin/activate

# Reinstall
pip install -r requirements.txt
```

---

### ❌ MCP tools not appearing in Claude Desktop

**Fix:**
1. Check that `claude_desktop_config.json` has correct paths
2. Ensure the Python path points to `.venv/bin/python` (not system Python)
3. Restart Claude Desktop completely
4. Check Claude Desktop logs:
   ```bash
   tail -f ~/Library/Logs/Claude/mcp*.log
   ```

---

### ❌ Session expired / keeps logging in

**Fix:**
- Delete old session and re-login:
  ```bash
  rm -rf data/sessions/
  ```
- Ensure `HEADLESS=false` so you can complete any login challenges

---

### 🐛 Enable Debug Logging

```bash
# In .env
LOG_LEVEL=DEBUG
```

Or check the log file:
```bash
tail -f logs/instagram_mcp.log
```

---

### 📋 Verify Everything Works

```bash
cd /Users/devdaskumar/Desktop/Code/instagram-mcp
source .venv/bin/activate

# Test imports
python -c "import mcp, playwright, aiosqlite, rich; print('All imports OK')"

# Test config
python -c "from config import Config; print(Config.summary())"

# Start server
python server.py
```

---

## 📁 Data Directory Reference

```
data/
├── sessions/
│   ├── instagram_session.json     ← Session cookies & storage
│   └── playwright_profile/        ← Persistent browser profile dir
├── screenshots/
│   ├── screenshot_20240101_120000.png
│   └── ...
└── memory.db                      ← SQLite database

logs/
└── instagram_mcp.log              ← Server logs (rotated, max 10MB × 5)
```

---

*Built with ❤️ — 100% local, 100% private, 0% cloud.*
