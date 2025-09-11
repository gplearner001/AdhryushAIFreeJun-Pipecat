# Teler Backend Service

A Python FastAPI backend service for initiating calls using the official teler library with WebSocket streaming support.

## Features

- **Teler Integration**: Direct integration with the official teler Python library
- **WebSocket Streaming**: Full bidirectional audio streaming support as per Teler documentation
- **AI-Powered**: Enhanced with Anthropic Claude for dynamic call flows and conversations
- **RESTful API**: Clean API endpoints for call management
- **Real-time Audio**: WebSocket support for real-time audio streaming with proper message handling
- **Call History**: Track and manage call history
- **Active Call Monitoring**: Real-time tracking of active calls
- **Status Monitoring**: Real-time call status updates
- **Webhook Handling**: Comprehensive webhook processing for call events
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
python fastapi_app.py
```

The server will start on `http://localhost:8000`

## WebSocket Streaming Implementation

The backend now implements proper Teler WebSocket streaming as per the official documentation:

### Incoming Messages (Teler -> App)

1. **start**: Contains stream metadata (first message)
2. **audio**: Contains base64-encoded audio chunks

### Outgoing Messages (App -> Teler)

1. **audio**: Send audio responses with chunk_id
2. **interrupt**: Stop specific chunk playback
3. **clear**: Clear entire audio buffer

### WebSocket Endpoint

- **WebSocket /media-stream**: Main streaming endpoint for Teler integration
- Handles bidirectional audio streaming
- Processes incoming audio chunks
- Can send audio responses back to Teler
- Supports interrupt and clear commands

## API Endpoints

### POST /api/calls/initiate
Initiate a new call using the teler library.

**Request Body:**
```json
{
  "from_number": "+918065193776",
  "to_number": "+916360154904",
  "flow_url": "https://your-backend-domain.com/flow",
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
    "flow_url": "https://your-backend-domain.com/flow",
    "timestamp": "2025-01-27T10:30:00"
  },
  "message": "Call initiated successfully"
}
```

### GET /api/calls/active
Get currently active calls.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "call_id": "call_123456789",
      "stream_id": "stream_abc123",
      "connection_id": "conn_xyz789",
      "from": "+918065193776",
      "to": "+916360154904",
      "status": "active",
      "started_at": "2025-01-27T10:30:00",
      "encoding": "audio/l16",
      "sample_rate": 8000
    }
  ],
  "count": 1
}
```

### GET /api/calls/history
Get call history.

### GET /api/calls/:callId
Get specific call details.

### GET /api/calls/:callId/status
Get current status of a specific call.

### POST /flow
Main call flow endpoint that handles call routing and maintains continuous conversation.

**Response:**
```json
{
  "action": "stream",
  "ws_url": "wss://your-domain.com/media-stream",
  "chunk_size": 500,
  "record": true
}
```

### POST /webhook
Webhook endpoint for receiving call status updates from Teler.

### WebSocket /media-stream
WebSocket endpoint for real-time media streaming during calls.

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

## Call Flow Implementation

The backend implements proper Teler call flow handling with WebSocket streaming:

1. **Call Initiation**: Uses Teler AsyncClient to create calls
2. **Flow Endpoint**: Returns stream flow configuration for WebSocket connection
3. **WebSocket Streaming**: Full bidirectional audio streaming with proper message handling
4. **Webhook Processing**: Handles all call status updates and events
5. **Active Call Tracking**: Monitors currently active calls in real-time

### WebSocket Message Handling

The WebSocket handler processes messages according to Teler documentation:

```python
# Incoming from Teler
{
  "type": "start",
  "account_id": "uuid",
  "call_id": "uuid",
  "stream_id": "uuid",
  "data": {
    "encoding": "audio/l16",
    "sample_rate": 8000,
    "channels": 1
  }
}

{
  "type": "audio",
  "stream_id": "uuid",
  "message_id": 123,
  "data": {
    "audio_b64": "base64_encoded_audio"
  }
}

# Outgoing to Teler
{
  "type": "audio",
  "audio_b64": "base64_encoded_audio",
  "chunk_id": 123
}

{
  "type": "interrupt",
  "chunk_id": 123
}

{
  "type": "clear"
}
```

### Additional WebSocket Control Endpoints

- **POST /api/websocket/interrupt/{connection_id}**: Send interrupt message
- **POST /api/websocket/clear/{connection_id}**: Send clear message  
- **GET /api/websocket/streams**: Get active WebSocket stream information

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