# Setup and Development Guide

## Project Structure

```
myfitnesspal-api/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── mfp_auth.py          # MyFitnessPal authentication
│   ├── requirements.txt      # Python dependencies
│   └── vendor/              # Vendored code from myfitnesspal-mcp
│       ├── __init__.py
│       ├── mfp_client.py    # Cloudflare-bypassing client
│       └── diary.py         # Food search & logging
├── static/
│   ├── index.html           # Frontend SPA
│   ├── style.css            # Styling
│   └── app.js               # JavaScript app logic
├── README.md                # User documentation
└── run.sh                   # Quick start script
```

## Installation

### Prerequisites
- Python 3.10 or higher
- pip

### Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Note**: `curl-cffi` requires a C compiler. On some systems, you may need:
- Ubuntu/Debian: `sudo apt-get install build-essential python3-dev`
- macOS: Xcode Command Line Tools (install via `xcode-select --install`)
- Windows: Microsoft C++ Build Tools

## Running the Server

### Option 1: Using the startup script
```bash
./run.sh
```

### Option 2: Manual startup
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The app will be available at `http://localhost:8000`

## Testing

### 1. Health Check
```bash
curl http://localhost:8000
# Should return the index.html page
```

### 2. Login Endpoint
```bash
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your_mfp_username","password":"your_mfp_password"}'
```

Expected response:
```json
{
  "session_id": "uuid-string",
  "username": "your_username"
}
```

### 3. Get Today's Data
```bash
curl http://localhost:8000/api/today \
  -H "Authorization: Bearer your_session_id"
```

Expected response structure:
```json
{
  "date": "2026-09-15",
  "goal_calories": 2000,
  "calories_eaten": 1200,
  "exercise_calories": 300,
  "remaining": 1100,
  "meals": {
    "breakfast": [...],
    "lunch": [...],
    "dinner": [...],
    "snacks": [...]
  }
}
```

### 4. Search Foods
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_session_id" \
  -d '{"query":"chicken"}'
```

Expected response:
```json
{
  "results": [
    {
      "name": "Chicken Breast",
      "brand": "Generic",
      "calories": 165,
      "protein": 31,
      "carbs": 0,
      "fat": 3.6,
      "serving": "100 g",
      "verified": true,
      "food_id": "...",
      "weight_id": "..."
    }
  ]
}
```

### 5. Log Food
```bash
curl -X POST http://localhost:8000/api/log \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_session_id" \
  -d '{
    "food_id":"123456",
    "weight_id":"654321",
    "quantity":150,
    "meal":"breakfast"
  }'
```

## Architecture Notes

### Authentication Flow
1. User enters MyFitnessPal credentials in the web app
2. Backend calls MyFitnessPal's NextAuth CSRF endpoint
3. Backend posts credentials to the callback endpoint
4. Session cookie (`__Secure-next-auth.session-token`) is extracted
5. Backend creates a `CurlCffiClient` with the session cookie
6. Client is stored in memory, indexed by session UUID
7. Session UUID returned to frontend and stored in localStorage

### Session Management
- Sessions are stored in memory on the backend
- Each session ID maps to a `CurlCffiClient` instance
- Sessions are lost if the server restarts
- For production, implement persistent session storage (Redis, database, etc.)

### Cloudflare Bypass
- `curl_cffi` library impersonates Chrome TLS/JA3 fingerprint
- This allows requests to MyFitnessPal bypassing Cloudflare checks
- Alternative: Use Playwright for login (see refresh.py in the original MCP)

### Frontend
- Pure HTML/CSS/JavaScript (no framework)
- Single-page app architecture
- Session ID stored in localStorage
- All subsequent requests include `Authorization: Bearer {session_id}` header

## Troubleshooting

### "Failed to get CSRF token from MFP"
- MFP website may have changed its auth endpoints
- Try accessing https://www.myfitnesspal.com directly to verify it's accessible

### "Login failed — check username/password"
- Verify credentials are correct
- Check if MFP account requires email verification
- Try logging in at myfitnesspal.com to verify account is active

### "Session expired" or 401 errors
- Sessions are stored in memory and are lost when the server restarts
- Log in again to create a new session

### Import errors or module not found
- Ensure you've run `pip install -r requirements.txt` from the backend directory
- Check that Python version is 3.10 or higher: `python3 --version`

## Environment Variables

Currently none are required, but the code could be extended to support:
- `MFP_HOST` - MyFitnessPal server hostname
- `MFP_IMPERSONATE` - Browser fingerprint to use (default: "chrome")
- `SESSION_TTL` - Session timeout in seconds

## Development Tips

1. **Enable hot-reload**: Use `uvicorn main:app --reload`
2. **Debug mode**: FastAPI auto-generates interactive API docs at `/docs`
3. **CORS**: Currently not enabled; add if needed for external API consumption
4. **Logging**: Extend FastAPI logging to trace authentication issues

## Production Considerations

1. **Session Storage**: Replace in-memory dict with Redis or database
2. **Rate Limiting**: Add rate limits on login and search endpoints
3. **HTTPS**: Deploy with proper SSL/TLS certificates
4. **Static Files**: Use a reverse proxy (nginx) to serve static files
5. **Monitoring**: Add logging and error tracking (Sentry, etc.)
6. **Auth Improvements**: Add session refresh tokens and expiration
7. **Database**: Store user data and preferences persistently
