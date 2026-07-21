# Dev Server Instructions

## Quick Start

```bash
# Start server (fastest method - use venv python directly)
setsid venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8001 </dev/null > /tmp/uvicorn.log 2>&1 &

# Verify it started (check for 200 response)
sleep 2 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/login
```

**Expected output**: `200`

## First-time Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Known Issues

### FastAPI/Starlette Compatibility
- **Problem**: FastAPI 0.139.x + Starlette 1.x causes `TypeError: cannot use 'tuple' as a dict key` in Jinja2
- **Solution**: Pin versions in requirements.txt:
  ```
  fastapi==0.114.2
  starlette==0.38.6
  ```
- **Root cause**: Starlette 1.x passes unhashable dicts as Jinja2 cache keys

## Login Credentials

| Username | Password | Role |
|----------|----------|------|
| Mate | mate123 | child |
| Maja | maja123 | child |
| drunyd | admin123 | admin |

## Useful Commands

```bash
# Check if server is running
pgrep -f uvicorn

# View server logs
cat /tmp/uvicorn.log

# Kill server
pkill -f uvicorn

# Restart server
pkill -f uvicorn; sleep 1; setsid venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8001 </dev/null > /tmp/uvicorn.log 2>&1 &
```

## Project Structure

- `app.py` - FastAPI application
- `templates/` - Jinja2 HTML templates
- `quizzes/` - YAML quiz files
- `users.json` - User accounts
- `quiz_app.db` - SQLite database (auto-created)
