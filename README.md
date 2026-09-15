# MyFitnessPal Web App

A self-hosted web application for logging food and tracking calories, built on top of the MyFitnessPal API.

## Features

- **Username/Password Login**: Sign in with your MyFitnessPal credentials
- **Food Logging**: Log foods with plaintext input like "lettuce 85" (quantity in grams)
- **Food Search**: Search MyFitnessPal's database with macro breakdown
- **Calorie Tracking**: View daily calorie totals, exercise, and remaining calories
- **Meal Organization**: Log foods to breakfast, lunch, dinner, or snacks

## Requirements

- Python 3.10+
- pip

## Quick Start

### Prerequisites
- Python 3.10+
- `uv` for dependency management (`pip install uv`)

### Using Make (Recommended)

```bash
make install  # Install dependencies
make run      # Start the server
make test     # Run tests
```

### Manual Setup

```bash
# Install dependencies
uv pip install -e .

# Start the server
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Quick Start Script

```bash
./run.sh
```

Then open `http://localhost:8000` in your browser.

## API Endpoints

- `POST /api/login` - Login with username/password
- `POST /api/logout` - Logout and clear session
- `GET /api/today` - Get today's diary summary
- `POST /api/search` - Search for foods
- `POST /api/log` - Log food to diary
- `DELETE /api/entry/{entry_id}` - Delete a diary entry

## How to Use

1. **Login**: Enter your MyFitnessPal username/email and password
2. **Log Food**: 
   - Select a meal (breakfast, lunch, dinner, snacks)
   - Enter food in the input box, e.g. "lettuce 85" or "chicken breast 150g"
   - Click Search to see alternatives
   - Click Add to log the food
3. **View Summary**: See your daily calorie totals, exercise, and remaining calories
4. **Manage Entries**: View all logged foods and delete as needed

## Technical Details

- **Backend**: Python FastAPI with myfitnesspal library
- **Frontend**: Plain HTML/CSS/JavaScript (no framework)
- **Authentication**: NextAuth flow via curl_cffi (bypasses Cloudflare)
- **Session Storage**: In-memory (suitable for single-user or small deployments)

## Notes

- Sessions are stored in memory and will be lost if the server restarts
- The app does not consume Claude API tokens - it's a pure Python/JavaScript implementation
- Food search and logging use the same undocumented APIs as the MyFitnessPal web app
