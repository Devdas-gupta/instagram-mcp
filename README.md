# 🤖 Instagram MCP — Local Browser Automation Server

> **100% Local · No Cloud · No API Keys · Real Chrome / Brave**

An MCP (Model Context Protocol) server that gives AI assistants (Claude Desktop, Gemini CLI, Cursor, Antigravity) full control of your real installed browser to automate Instagram — using manual-login browser sessions. No passwords or credentials are stored or needed.

---

## Architecture

```
Claude Desktop / Gemini CLI / Cursor / Antigravity
             ↓  MCP Protocol (stdio)
         server.py  ←─── FastMCP
             ↓
    browser_controller.py  ←─── Playwright
             ↓
    instagram_tools.py
             ↓
   Real Chrome or Brave Browser
             ↓
   Logged-in Instagram Session
             ↓
   memory.py  ←─── SQLite (local)
```

---

## ✅ Features

### Browser Control (30 tools)
| Tool | Description |
|------|-------------|
| `open_browser` | Launch browser with session |
| `open_url` | Navigate to any URL |
| `click_element` | Click by CSS/XPath/text selector |
| `type_text` | Type into inputs |
| `scroll_page` | Scroll in any direction |
| `hover_element` | Hover over elements |
| `press_key` | Press keyboard keys |
| `switch_tab` | Switch browser tabs |
| `close_tab` | Close a tab |
| `list_tabs` | List all open tabs |
| `current_url` | Get current URL |
| `page_title` | Get page title |
| `extract_text` | Extract page/element text |
| `inspect_element` | Get element attributes & bounds |
| `take_screenshot` | Capture page screenshot |
| `new_tab` | Open new browser tab |
| `evaluate_js` | Run JavaScript in browser |

### Instagram Tools
| Tool | Description |
|------|-------------|
| `open_instagram` | Navigate to Instagram |
| `login_instagram` | Log in (auto-saves session) |
| `save_session` | Save cookies/storage state |
| `load_session` | Load saved session |
| `read_feed` | Read home feed posts |
| `open_reel` | Open a specific Reel |
| `read_comments` | Read post comments |
| `like_post` | Like a post |
| `post_comment` | Post a comment |
| `monitor_notifications` | Check notifications |
| `analyze_profile` | Analyze a user profile |
| `summarize_visible_content` | Summarize current page |

### Memory Tools (SQLite)
| Tool | Description |
|------|-------------|
| `memory_stats` | DB row counts |
| `list_screenshots` | Saved screenshots |
| `list_visited_profiles` | Previously analyzed profiles |
| `save_note` | Save a text note |
| `list_notes` | List all notes |
| `search_memory` | Search extracted text |
| `session_history` | View session event log |

---

## 🗂 Project Structure

```
instagram-mcp/
├── server.py              # MCP server entry point
├── browser_controller.py  # Low-level Playwright tools
├── instagram_tools.py     # Instagram-specific automation
├── session_manager.py     # Session persistence & login
├── memory.py              # SQLite local memory
├── config.py              # Configuration & env loading
├── logger.py              # Rich-enhanced logging
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── HowToUse.md
├── configs/
│   ├── claude_desktop_config.json
│   ├── cursor_mcp_config.json
│   ├── gemini_cli_config.json
│   └── antigravity_config.json
├── data/                  # Auto-created at runtime
│   ├── sessions/          # Saved browser sessions
│   ├── screenshots/       # Captured screenshots
│   └── memory.db          # SQLite database
└── logs/                  # Log files
```

---

## ⚡ Quick Start

```bash
# 1. Clone / navigate to project
cd /Users/devdaskumar/Desktop/Code/instagram-mcp

# 2. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium

# 5. Copy and configure .env
cp .env.example .env
# Configure BROWSER_TYPE (chrome or brave) in .env if desired

# 6. Run the server (for testing)
python server.py

# 7. Or run in stdio mode (for MCP clients)
python server.py --transport stdio
```

---

## 🔐 Security

- **No password storage** — session cookies and metadata are stored locally under `data/sessions/`
- **No network requests** are made by this server except through your browser
- **No telemetry, no cloud sync, no external APIs**
- `.gitignore` protects `.env` and `data/` from accidental commits

---

## ⚠️ Responsible Use

This tool controls a real browser session. Please:

- Do **not** spam likes/comments (Instagram rate limits)
- Do **not** use this to violate Instagram's Terms of Service
- Add **delays** between automated actions
- Use **headless=false** when developing to monitor what's happening

---

## 📄 License

MIT — personal and educational use.
