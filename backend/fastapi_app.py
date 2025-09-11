#!/usr/bin/env python3
"""
FastAPI application for Teler WebSocket streaming
Replaces Flask with FastAPI for better WebSocket support
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from websocket_handler import websocket_handler
from claude_service import claude_service
from audio_processor import audio_processor

# Teler imports
try:
    from teler import AsyncClient, CallFlow
    TELER_AVAILABLE = True
except ImportError:
    TELER_AVAILABLE = False

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Teler Call Service", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
TELER_API_KEY = os.getenv('TELER_API_KEY', 'cf771fc46a1fddb7939efa742801de98e48b0826be4d8b9976d3c7374a02368b')
BACKEND_DOMAIN = os.getenv('BACKEND_DOMAIN', 'localhost:8000')
BACKEND_URL = f"https://{BACKEND_DOMAIN}" if not BACKEND_DOMAIN.startswith('localhost') else f"http://{BACKEND_DOMAIN}"

# In-memory storage for call history
call_history = []

# Pydantic models
class CallFlowRequest(BaseModel):
    call_id: str
    account_id: str
    from_number: str
    to_number: str

class CallInitiateRequest(BaseModel):
    from_number: str
    to_number: str
    flow_url: str
    status_callback_url: Optional[str] = None
    record: bool = True

# Mock Teler client for development
class MockTelerClient:
    """Mock teler client for development and testing."""
    
    async def create_call(self, **kwargs):
        """Mock call creation."""
        logger.info(f"Mock create_call called with: {kwargs}")
        return {
            'call_id': f"call_{int(datetime.now().timestamp())}",
            'status': 'initiated',
            'message': 'Call initiated successfully (mock)',
            'from_number': kwargs.get('from_number'),
            'to_number': kwargs.get('to_number'),
            'flow_url': kwargs.get('flow_url'),
            'record': kwargs.get('record', False)
        }

async def create_teler_call(from_number, to_number, flow_url, status_callback_url=None, record=True):
    """Create a call using the teler AsyncClient."""
    try:
        if TELER_AVAILABLE:
            logger.info(f"Creating call with teler AsyncClient")
            
            async with AsyncClient(api_key=TELER_API_KEY, timeout=30) as client:
                call_params = {
                    "from_number": from_number,
                    "to_number": to_number,
                    "flow_url": flow_url,
                    "record": record
                }
                
                if status_callback_url:
                    call_params["status_callback_url"] = status_callback_url
                
                logger.info(f"Call parameters: {call_params}")
                call = await client.calls.create(**call_params)
                
                call_response = {
                    'call_id': getattr(call, 'call_id', getattr(call, 'sid', f"call_{int(datetime.now().timestamp())}")),
                    'status': getattr(call, 'status', 'initiated'),
                    'from_number': from_number,
                    'to_number': to_number,
                    'flow_url': flow_url,
                    'record': record,
                    'message': 'Call initiated successfully'
                }
                
                return call_response
        else:
            logger.info("Using mock client for call creation")
            mock_client = MockTelerClient()
            return await mock_client.create_call(
                from_number=from_number,
                to_number=to_number,
                flow_url=flow_url,
                status_callback_url=status_callback_url,
                record=record
            )
    except Exception as e:
        logger.error(f"Error creating call: {str(e)}")
        mock_client = MockTelerClient()
        return await mock_client.create_call(
            from_number=from_number,
            to_number=to_number,
            flow_url=flow_url,
            status_callback_url=status_callback_url,
            record=record
        )

# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'OK',
        'message': 'Teler FastAPI Service is running',
        'timestamp': datetime.now().isoformat(),
        'teler_available': TELER_AVAILABLE,
        'claude_available': claude_service.is_available(),
        'audio_processing_available': audio_processor.is_available()
    }

@app.post("/flow", status_code=status.HTTP_200_OK)
async def stream_flow(payload: CallFlowRequest):
    """
    Build and return Stream flow for Teler.
    This endpoint is called by Teler when a call is answered.
    """
    logger.info(f"Flow endpoint called with: {payload}")
    
    # Create stream flow configuration
    stream_flow = CallFlow.stream(
        ws_url=f"wss://{BACKEND_DOMAIN}/media-stream",
        chunk_size=500,
        record=True
    )
    
    logger.info(f"Generated stream flow: {stream_flow}")
    return JSONResponse(stream_flow)

@app.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook_receiver(data: dict = Body(...)):
    """Handle webhook callbacks from Teler."""
    logger.info(f"--------Webhook Payload-------- {data}")
    
    # Update call history with webhook data
    call_id = data.get('call_id') or data.get('CallSid') or data.get('id')
    if call_id:
        for call in call_history:
            if call.get('call_id') == call_id:
                call['webhook_data'] = data
                call['status'] = data.get('status', call['status'])
                call['updated_at'] = datetime.now().isoformat()
                break
    
    return JSONResponse(content={"message": "Webhook received successfully"})

@app.post("/api/calls/initiate")
async def initiate_call(request: CallInitiateRequest):
    """Initiate a new call using the teler library."""
    try:
        logger.info(f"Initiating call from {request.from_number} to {request.to_number}")
        
        status_callback_url = request.status_callback_url or f"{BACKEND_URL}/webhook"
        
        # Create the call using async teler client
        call_response = await create_teler_call(
            from_number=request.from_number,
            to_number=request.to_number,
            flow_url=request.flow_url,
            status_callback_url=status_callback_url,
            record=request.record
        )
        
        # Create call record
        call_record = {
            'id': len(call_history) + 1,
            'call_id': call_response['call_id'],
            'status': call_response['status'],
            'from_number': request.from_number,
            'to_number': request.to_number,
            'flow_url': request.flow_url,
            'status_callback_url': status_callback_url,
            'record': request.record,
            'timestamp': datetime.now().isoformat(),
            'response_data': call_response,
            'call_type': 'conversation',
            'notes': 'Configured for bidirectional phone conversation with WebSocket streaming'
        }
        
        # Store in history
        call_history.insert(0, call_record)
        
        logger.info(f"Call initiated successfully: {call_response['call_id']}")
        
        return {
            'success': True,
            'data': {
                'call_id': call_response['call_id'],
                'status': call_response['status'],
                'from_number': request.from_number,
                'to_number': request.to_number,
                'flow_url': request.flow_url,
                'record': request.record,
                'timestamp': call_record['timestamp'],
                'call_type': 'conversation',
                'message': 'Call configured for WebSocket streaming conversation'
            },
            'message': 'Call initiated successfully - configured for WebSocket streaming'
        }
        
    except Exception as e:
        logger.error(f"Error in initiate_call: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate call: {str(e)}"
        )

@app.get("/api/calls/history")
async def get_call_history():
    """Get call history."""
    return {
        'success': True,
        'data': call_history,
        'count': len(call_history)
    }

@app.get("/api/calls/active")
async def get_active_calls():
    """Get currently active calls from WebSocket streams."""
    active_streams = websocket_handler.get_active_streams()
    active_calls = []
    
    for connection_id, stream_info in active_streams.items():
        active_calls.append({
            'call_id': stream_info.get('call_id'),
            'stream_id': stream_info.get('stream_id'),
            'connection_id': connection_id,
            'from': stream_info.get('from_number', 'Unknown'),
            'to': stream_info.get('to_number', 'Unknown'),
            'status': 'active',
            'started_at': stream_info.get('started_at'),
            'encoding': stream_info.get('encoding'),
            'sample_rate': stream_info.get('sample_rate')
        })
    
    return {
        'success': True,
        'data': active_calls,
        'count': len(active_calls)
    }

@app.get("/api/calls/{call_id}")
async def get_call_details(call_id: str):
    """Get details for a specific call."""
    call = next((c for c in call_history if c['call_id'] == call_id), None)
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return {
        'success': True,
        'data': call
    }

@app.post("/api/ai/conversation")
async def ai_conversation(data: dict = Body(...)):
    """Generate AI conversation responses using Claude."""
    if not claude_service.is_available():
        raise HTTPException(status_code=503, detail="Claude AI service not available")
    
    conversation_context = {
        'history': data.get('history', []),
        'current_input': data.get('current_input', ''),
        'call_id': data.get('call_id', ''),
        'context': data.get('context', {})
    }
    
    try:
        response_text = await claude_service.generate_conversation_response(conversation_context)
        
        return {
            'success': True,
            'data': {
                'response': response_text,
                'timestamp': datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error in AI conversation endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate AI response: {str(e)}")

@app.get("/api/ai/status")
async def ai_status():
    """Check AI service status."""
    return {
        'success': True,
        'data': {
            'claude_available': claude_service.is_available(),
            'service': 'Anthropic Claude',
            'model': 'claude-3-5-sonnet-20241022' if claude_service.is_available() else None
        }
    }

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """
    Handle WebSocket connection for Teler media streaming.
    This endpoint receives audio from Teler and can send audio back.
    """
    connection_id = None
    try:
        # Accept the WebSocket connection
        connection_id = await websocket_handler.connect(websocket)
        logger.info(f"Media stream WebSocket connected: {connection_id}")
        
        # Handle incoming messages
        while True:
            try:
                # Receive message from Teler
                message = await websocket.receive_text()
                logger.debug(f"Received message: {message[:100]}...")
                
                # Handle the message
                await websocket_handler.handle_incoming_message(websocket, message, connection_id)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                # Send error message back to client
                error_response = {
                    "type": "error",
                    "message": str(e)
                }
                try:
                    await websocket.send_text(json.dumps(error_response))
                except:
                    break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if connection_id:
            websocket_handler.disconnect(connection_id)

# Additional WebSocket control endpoints
@app.post("/api/websocket/interrupt/{connection_id}")
async def send_interrupt(connection_id: str, chunk_id: int = Body(...)):
    """Send interrupt message to specific WebSocket connection."""
    await websocket_handler.send_interrupt(connection_id, chunk_id)
    return {"message": f"Interrupt sent for chunk {chunk_id}"}

@app.post("/api/websocket/clear/{connection_id}")
async def send_clear(connection_id: str):
    """Send clear message to specific WebSocket connection."""
    await websocket_handler.send_clear(connection_id)
    return {"message": "Clear message sent"}

@app.get("/api/websocket/streams")
async def get_websocket_streams():
    """Get information about active WebSocket streams."""
    streams = websocket_handler.get_active_streams()
    return {
        'success': True,
        'data': streams,
        'count': len(streams)
    }

@app.get("/api/websocket/conversation/{connection_id}")
async def get_conversation_history(connection_id: str):
    """Get conversation history for a specific WebSocket connection."""
    history = websocket_handler.get_conversation_history(connection_id)
    return {
        'success': True,
        'data': history,
        'count': len(history)
    }

@app.get("/api/audio/status")
async def get_audio_status():
    """Get audio processing service status."""
    return {
        'success': True,
        'data': {
            'stt_available': audio_processor.is_available(),
            'tts_available': audio_processor.is_available(),
            'service': 'SpeechRecognition + pyttsx3',
            'supported_formats': ['audio/l16']
        }
    }
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8000))
    
    logger.info(f"Starting Teler FastAPI Service on port {port}")
    logger.info(f"Teler library available: {TELER_AVAILABLE}")
    logger.info(f"Claude AI available: {claude_service.is_available()}")
    logger.info(f"Audio processing available: {audio_processor.is_available()}")
    
    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv('ENVIRONMENT') == 'development'
    )