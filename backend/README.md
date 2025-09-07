# Teler Backend Service

A Python Flask backend service for initiating calls using the official teler library.

## Features

- **Teler Integration**: Direct integration with the official teler Python library
- **AI-Powered**: Enhanced with Anthropic Claude for dynamic call flows and conversations
- **RESTful API**: Clean API endpoints for call management
- **Call History**: Track and manage call history
- **Status Monitoring**: Real-time call status updates
- **Error Handling**: Comprehensive error handling and logging

## Setup

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment Configuration

Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

Update the `.env` file with your actual Teler API credentials.

### 3. Start the Server

```bash
python app.py
```

The server will start on `http://localhost:5000`

## API Endpoints

### POST /api/calls/initiate
Initiate a new call using the teler library.

**Request Body:**
```json
{
  "from_number": "+918065193776",
  "to_number": "+916360154904",
  "flow_url": "https://webhook.site/a7163743-c704-418d-8b7d-2b5ac7889528",
  "status_callback_url": ""
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "call_id": "call_123456789",
    "status": "initiated",
    "from_number": "+918065193776",
    "to_number": "+916360154904",
    "flow_url": "https://webhook.site/...",
    "timestamp": "2025-01-27T10:30:00"
  },
  "message": "Call initiated successfully"
}
```

### GET /api/calls/history
Get call history.

### GET /api/calls/:callId
Get specific call details.

### GET /api/calls/:callId/status
Get current status of a specific call.

### GET /health
Health check endpoint.

### POST /api/ai/conversation
Generate AI conversation responses using Claude.

**Request Body:**
```json
{
  "history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "current_input": "How can you help me?",
  "call_id": "call_123456789",
  "context": {}
}
```

### GET /api/ai/status
Check AI service status and availability.

## Deployment Recommendations

### Railway (Recommended for Python)
- Excellent Python support with automatic dependency detection
- Built-in environment variable management
- Easy scaling and monitoring
- Automatic deployments from GitHub

**Setup:**
1. Connect your GitHub repository to Railway
2. Select the `backend` folder as the root directory
3. Railway will automatically detect it's a Python app
4. Set environment variables in Railway dashboard
5. Deploy automatically

### Render (Great Free Tier)
- Free tier with 750 hours/month
- Automatic deployments from GitHub
- Built-in SSL certificates
- Good for development and small projects

**Setup:**
1. Connect GitHub repository to Render
2. Choose "Web Service" and select `backend` folder
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python app.py`
5. Configure environment variables

### Google Cloud Run (Serverless)
- Pay-per-use serverless platform
- Automatic scaling to zero
- Great for variable traffic

**Setup:**
1. Create a `Dockerfile` in the backend folder
2. Build and push to Google Container Registry
3. Deploy to Cloud Run
4. Configure environment variables

### Heroku (Popular Choice)
- Easy deployment with Git integration
- Extensive add-on ecosystem
- Good documentation and community

**Setup:**
1. Install Heroku CLI
2. Create Heroku app: `heroku create your-app-name`
3. Set environment variables: `heroku config:set TELER_ACCESS_TOKEN=your_token`
4. Deploy: `git push heroku main`

## Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["python", "app.py"]
```

Build and run:
```bash
docker build -t teler-backend .
docker run -p 5000:5000 --env-file .env teler-backend
```

## Integration with teler Library

This backend uses the official teler Python library for call initiation. The key integration points:

1. **Client Creation**: `teler.TelerClient(access_token=TELER_ACCESS_TOKEN)`
2. **Call Initiation**: `client.initiate_call(**call_params)`
3. **Status Checking**: `client.get_call_status(call_id)`

## Error Handling

The API includes comprehensive error handling:
- Input validation for required fields
- Teler API error handling and logging
- Graceful error responses with appropriate HTTP status codes
- Detailed logging for debugging

## Security

- Environment variable configuration for sensitive data
- Input validation and sanitization
- CORS protection for cross-origin requests
- Error messages that don't expose internal details

## Development

For development, set `FLASK_ENV=development` in your `.env` file to enable:
- Debug mode with detailed error messages
- Automatic reloading on code changes
- Development-specific logging

## Production Considerations

1. **Database**: Replace in-memory storage with a proper database (PostgreSQL, MongoDB)
2. **Authentication**: Add API key authentication for production use
3. **Rate Limiting**: Implement rate limiting to prevent abuse
4. **Monitoring**: Add application monitoring and alerting
5. **Logging**: Configure structured logging for production