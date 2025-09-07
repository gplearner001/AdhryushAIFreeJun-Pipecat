# Teler Call Service

A professional full-stack application for initiating voice calls using the official Teler Python library. Built with React, TypeScript, and Python Flask.

## 🚀 Features

- **Professional UI**: Modern gradient design with responsive layout
- **AI-Powered**: Integrated with Anthropic Claude for dynamic call flows and conversations
- **Real-time Call Management**: Initiate calls and track history
- **Backend API**: RESTful Python Flask service with official teler library integration
- **Type Safety**: Full TypeScript implementation
- **Easy Deployment**: Ready for Vercel (frontend) and Railway/Render/Heroku (backend)

## 📁 Project Structure

```
├── backend/              # Python Flask API server
│   ├── app.py           # Main Flask application
│   ├── requirements.txt # Python dependencies
│   ├── Dockerfile       # Docker configuration
│   └── README.md        # Backend documentation
├── src/                 # React frontend
│   ├── components/      # React components
│   ├── services/        # API service layer
│   ├── types/          # TypeScript definitions
│   └── App.tsx         # Main app component
└── README.md           # This file
```

## 🛠 Development Setup

### Frontend (React)
```bash
npm install
npm run dev
```

### Backend (Python Flask)
```bash
cd backend
pip install -r requirements.txt
python app.py
```

## 🌐 Deployment

### Frontend - Vercel (Recommended)
1. Connect your GitHub repository to Vercel
2. Set environment variable: `VITE_API_URL` to your backend URL
3. Deploy automatically on git push

### Backend - Railway (Recommended for Python)
1. Connect your GitHub repository to Railway
2. Select the `backend` folder as root directory
3. Railway auto-detects Python and installs dependencies
4. Set environment variables from `.env.example`
5. Deploy automatically

### Alternative Backend Platforms:
- **Render**: Easy Python deployment with free tier
- **Heroku**: Popular platform with excellent Python support
- **Google Cloud Run**: Serverless container platform

## 🔧 Environment Variables

### Frontend (.env)
```
VITE_API_URL=https://your-backend-url.com
```

### Backend (.env)
```
TELER_API_KEY=cf771fc46a1fddb7939efa742801de98e48b0826be4d8b9976d3c7374a02368b
ANTHROPIC_API_KEY=your_anthropic_api_key_here
BACKEND_DOMAIN=your-backend-domain.com
FLASK_ENV=development
PORT=5000
```

## 📱 API Integration

The application uses the official teler Python library for voice call initiation. Key endpoints:

- `POST /api/calls/initiate` - Start a new call
- `GET /api/calls/history` - Get call history  
- `GET /api/calls/:callId` - Get call details
- `GET /api/calls/:callId/status` - Get real-time call status
- `GET /health` - Health check endpoint
- `POST /api/ai/conversation` - Generate AI responses using Claude
- `GET /api/ai/status` - Check AI service status

## 🎨 Design Features

- Modern gradient color scheme (blue to purple)
- Responsive design for all devices
- Professional typography and spacing
- Smooth animations and hover effects
- Real-time status indicators

## 🔒 Security

- Environment variable configuration
- Input validation and sanitization  
- CORS protection
- Error handling without exposing internals

## 📞 Official Teler Library Integration

This application uses the official teler Python library enhanced with Anthropic Claude AI:

1. **Direct Integration**: Uses `teler.TelerClient` for call initiation
2. **AI-Enhanced Flows**: Claude generates dynamic call flows based on context
2. **Real-time Status**: Supports call status monitoring
3. **Intelligent Conversations**: AI-powered conversation responses during calls
3. **Error Handling**: Comprehensive error handling for API failures
4. **Production Ready**: Built for production deployment

### Key Integration Points:
```python
from teler import AsyncClient, CallFlow

# Create async client
async with AsyncClient(api_key=TELER_API_KEY, timeout=30) as client:
    # Initiate call
    call = await client.calls.create(
        from_number="+918065193776",
        to_number="+916360154904", 
        flow_url="https://your-domain.com/flow",
        status_callback_url="https://your-domain.com/webhook",
        record=True
    )

# Create call flow
flow_config = CallFlow.stream(
    ws_url="wss://your-domain.com/media-stream",
    chunk_size=500,
    record=True
)
```
## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License.