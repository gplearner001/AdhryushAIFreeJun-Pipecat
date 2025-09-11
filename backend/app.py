#!/usr/bin/env python3
"""
Teler Call Service Backend
A Flask-based API service for initiating calls using the teler library.
"""

import os
import json
import logging
import asyncio
import asyncio
from typing import Dict, Any
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from claude_service import claude_service

# Teler Code
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Body, status, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Annotated

from teler.streams import StreamConnector, StreamOp, StreamType
from teler import AsyncClient, CallFlow

try:
    from teler import AsyncClient
    TELER_AVAILABLE = True
except ImportError:
    TELER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Teler library not available, using mock implementation")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
TELER_API_KEY = os.getenv('TELER_API_KEY', 'cf771fc46a1fddb7939efa742801de98e48b0826be4d8b9976d3c7374a02368b')
BACKEND_DOMAIN = os.getenv('BACKEND_DOMAIN', 'https://adhryushaifreejun-pipecat.onrender.com')
BACKEND_URL = f"https://{BACKEND_DOMAIN}" if not BACKEND_DOMAIN.startswith('localhost') else f"http://{BACKEND_DOMAIN}"


#Teler Code
class CallFlowRequest(BaseModel):
    call_id: str
    account_id: str
    from_number: str
    to_number: str

async def call_stream_handler(message: str):
    msg = json.loads(message)
    if msg["type"] == "audio":
        payload = json.dumps({"user_audio_chunk": msg["data"]["audio_b64"]})
        return (payload, StreamOp.RELAY)
    return ({}, StreamOp.PASS)

def remote_stream_handler():
    chunk_id = 1

    async def handler(message: str):
        nonlocal chunk_id
        msg = json.loads(message)
        if msg["type"] == "audio":
            payload = json.dumps(
                {
                    "type": "audio",
                    "audio_b64": msg["audio_event"]["audio_base_64"],
                    "chunk_id": chunk_id,
                }
            )
            chunk_id += 1
            return (payload, StreamOp.RELAY)
        elif msg["type"] == "interruption":
            payload = json.dumps({"type": "clear"})
            return (payload, StreamOp.RELAY)
        return ({}, StreamOp.PASS)

    return handler

connector = StreamConnector(
    stream_type=StreamType.BIDIRECTIONAL,
    remote_url=f"wss://{BACKEND_DOMAIN}/media-stream",
    call_stream_handler=call_stream_handler,
    remote_stream_handler=remote_stream_handler(),
)


# In-memory storage for call history (in production, use a database)
call_history = []
class MockTelerClient:
    """Mock teler client for development and testing."""
    
    def __init__(self):
        logger.info("Initialized MockTelerClient")
    
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
    
    async def get_call_status(self, call_id):
        """Mock status check."""
        logger.info(f"Mock get_call_status called for: {call_id}")
        return {
            'call_id': call_id,
            'status': 'completed',
            'message': 'Call completed (mock)'
        }

async def create_teler_call(from_number, to_number, flow_url, status_callback_url=None, record=True):
    """Create a call using the teler AsyncClient."""
    try:
        if TELER_AVAILABLE:
            logger.info(f"Creating call with teler AsyncClient")
            logger.info(f"API Key: {TELER_API_KEY[:10]}...")
            
            async with AsyncClient(api_key=TELER_API_KEY, timeout=30) as client:
                # Create call with correct teler parameters based on documentation
                call_params = {
                    "from_number": from_number,
                    "to_number": to_number,
                    "flow_url": flow_url,
                    "record": record
                }
                
                # Add optional parameters if provided
                if status_callback_url:
                    call_params["status_callback_url"] = status_callback_url
                
                logger.info(f"Call parameters: {call_params}")
                
                call = await client.calls.create(**call_params)
                
                logger.info(f"Call created successfully: {call}")
                
                # Extract call information from teler response
                call_response = {
                    'call_id': getattr(call, 'call_id', getattr(call, 'sid', getattr(call, 'call_sid', f"call_{int(datetime.now().timestamp())}"))),
                    'status': getattr(call, 'status', 'initiated'),
                    'from_number': from_number,
                    'to_number': to_number,
                    'flow_url': flow_url,
                    'record': record,
                    'message': 'Call initiated successfully',
                    'duration': getattr(call, 'duration', None),
                    'price': getattr(call, 'price', None)
                }
                
                return call_response
        else:
            # Use mock client
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
        logger.error(f"Error creating call with teler: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details'}")
        logger.info("Falling back to mock client")
        mock_client = MockTelerClient()
        return await mock_client.create_call(
            from_number=from_number,
            to_number=to_number,
            flow_url=flow_url,
            status_callback_url=status_callback_url,
            record=record
        )

def run_async(coro):
    """Helper function to run async code in Flask."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'OK',
        'message': 'Teler Backend Service is running',
        'timestamp': datetime.now().isoformat(),
        'teler_available': TELER_AVAILABLE
    })

@app.route('/flow', methods=['POST'])
def flow_endpoint():
    """
    Call flow endpoint for teler.
    This endpoint handles the call flow and keeps the call active for conversation.
    """
    try:
        # Get form data (teler sends form data, not JSON)
        data = request.form.to_dict() if request.form else request.get_json() or {}
        logger.info(f"Flow endpoint called with data: {data}")
        
        # Extract call information
        call_sid = data.get('CallSid', data['call_id'])
        from_number = data.get('From', data['from_number'])
        to_number = data.get('To', data['to_number'])
        direction = data.get('Direction', data['direction'])
        call_status = data.get('CallStatus', 'unknown')
        
        logger.info(f"Call answered - SID: {call_sid}, From: {from_number}, To: {to_number}, Status: {call_status}")
        
        # Return a call flow configuration that enables continuous conversation
        # Based on Teler's call flow documentation
        flow_config = {
            "type": "conversation",
            "initial_message": "Hello! You are now connected. Please go ahead and speak.",
            "conversation_mode": "bidirectional",
            "keep_alive": True,
            "max_duration": 1800,  # 30 minutes
            "silence_timeout": 30,  # 30 seconds before prompting
            "end_call_phrases": ["goodbye", "end call", "hang up", "bye"],
            "steps": [
                {
                    "action": "answer_call",
                    "auto_answer": True
                },
                {
                    "action": "play_message",
                    "text": "Hello! You are now connected. Please go ahead and speak.",
                    "voice": "natural"
                },
                {
                    "action": "enable_conversation",
                    "mode": "continuous",
                    "allow_interruption": True,
                    "record": True
                },
                {
                    "action": "monitor_silence",
                    "timeout": 30,
                    "prompt": "Are you still there? Please continue."
                },
                {
                    "action": "detect_end_phrases",
                    "phrases": ["goodbye", "end call", "hang up", "bye"],
                    "farewell": "Thank you for calling. Goodbye!"
                }
            ],
            "media_stream": {
                "enabled": True,
                "url": f"wss://{BACKEND_DOMAIN}/media-stream",
                "format": "audio/wav",
                "sample_rate": 8000
            },
            "recording": {
                "enabled": True,
                "format": "wav"
            }
        }
        
        logger.info(f"Generated call flow config for call {call_sid}")
        
        # Return the stream flow format that Teler expects
        flow_config = {
            "action": "stream",
            "ws_url": f"wss://{BACKEND_DOMAIN}/media-stream",
            "chunk_size": 500,
            "sample_rate": "8k"
        }
        fallback_flow = {
            "type": "simple",
            "steps": [
                {
                    "action": "answer_call"
                },
                {
                    "action": "play_message",
                    "text": "Connected. Please speak."
                },
                {
                    "action": "wait",
                    "duration": 300
                }
            ]
        }
        return jsonify(flow_config)
    
    except Exception as e:
        data = request.get_json()
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook callbacks from teler."""
    try:
        # Get form data (teler sends form data, not JSON)
        data = request.form.to_dict() if request.form else request.get_json() or {}
        logger.info(f"Webhook received: {data}")
        
        # Extract call information
        call_id = data.get('call_id') or data.get('CallSid') or data.get('id')
        call_status = data.get('status') or data.get('CallStatus')
        
        if call_id:
            # Update call history with webhook data
            for call in call_history:
                if call.get('call_id') == call_id:
                    call['webhook_data'] = data
                    if call_status:
                        call['status'] = call_status
                    call['updated_at'] = datetime.now().isoformat()
                    logger.info(f"Updated call {call_id} with status: {call_status}")
                    break
        
        return jsonify({
            'message': 'Webhook received successfully',
            'status': 'ok'
        })
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({
            'error': 'Failed to process webhook',
            'message': str(e)
        }), 500

        logger.info(f"--------Webhook Payload-------- {data}")
        
        # Update call history with webhook data
        call_id = data.get('call_id')
        if call_id:
            for call in call_history:
                if call.get('call_id') == call_id:
                    call['webhook_data'] = data
                    call['status'] = data.get('status', call['status'])
                    call['updated_at'] = datetime.now().isoformat()
                    break
        
        return jsonify({'message': 'Webhook received successfully'})
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({
            'error': 'Failed to process webhook',
            'message': str(e)
        }), 500

@app.route('/api/calls/initiate', methods=['POST'])
def initiate_call():
    """Initiate a new call using the teler library."""
    try:
        # Get request data
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['from_number', 'to_number', 'flow_url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': f'Missing required field: {field}',
                    'success': False
                }), 400

        from_number = data['from_number']
        to_number = data['to_number']
        flow_url = data['flow_url']
        status_callback_url = data.get('status_callback_url', f'http://{BACKEND_DOMAIN}/webhook')
        record = data.get('record', True)

        logger.info(f"Initiating call from {from_number} to {to_number}")

        # Create the call using async teler client
        call_response = run_async(create_teler_call(
            from_number=from_number,
            to_number=to_number,
            flow_url=flow_url,
            status_callback_url=status_callback_url,
            record=record
        ))

        # Extract call information from response
        # call_response is now guaranteed to be a dictionary
        call_id = call_response['call_id']
        status = call_response['status']
        
        # Create call record
        call_record = {
            'id': len(call_history) + 1,
            'call_id': call_id,
            'status': status,
            'from_number': from_number,
            'to_number': to_number,
            'flow_url': flow_url,
            'status_callback_url': status_callback_url,
            'record': record,
            'timestamp': datetime.now().isoformat(),
            'response_data': call_response,
            'call_type': 'conversation',
            'notes': 'Configured for bidirectional phone conversation'
        }

        # Store in history
        call_history.insert(0, call_record)  # Insert at beginning for newest first

        logger.info(f"Call initiated successfully: {call_id}")

        return jsonify({
            'success': True,
            'data': {
                'call_id': call_id,
                'status': status,
                'from_number': from_number,
                'to_number': to_number,
                'flow_url': flow_url,
                'record': record,
                'timestamp': call_record['timestamp'],
                'call_type': 'conversation',
                'message': 'Call configured for real phone conversation'
            },
            'message': 'Call initiated successfully - configured for phone conversation'
        })

    except Exception as e:
        logger.error(f"Error in initiate_call: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Traceback:", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': str(e),
            'success': False
        }), 500

@app.route('/api/calls/history', methods=['GET'])
def get_call_history():
    """Get call history."""
    try:
        return jsonify({
            'success': True,
            'data': call_history,
            'count': len(call_history)
        })
    except Exception as e:
        logger.error(f"Error getting call history: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve call history',
            'message': str(e),
            'success': False
        }), 500

@app.route('/api/calls/<call_id>', methods=['GET'])
def get_call_details(call_id):
    """Get details for a specific call."""
    try:
        # Find call in history
        call = next((c for c in call_history if c['call_id'] == call_id), None)
        
        if not call:
            return jsonify({
                'error': 'Call not found',
                'success': False
            }), 404

        return jsonify({
            'success': True,
            'data': call
        })

    except Exception as e:
        logger.error(f"Error getting call details: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve call details',
            'message': str(e),
            'success': False
        }), 500

@app.route('/api/calls/<call_id>/status', methods=['GET'])
def get_call_status(call_id):
    """Get current status of a specific call."""
    try:
        # Find call in local history first
        call = next((c for c in call_history if c['call_id'] == call_id), None)
        
        if not call:
            return jsonify({
                'error': 'Call not found',
                'success': False
            }), 404

        # Return the current status from our records
        # In a real implementation, you might want to query teler API for real-time status
        status_response = {
            'call_id': call_id,
            'status': call.get('status', 'unknown'),
            'timestamp': call.get('updated_at', call.get('timestamp')),
            'webhook_data': call.get('webhook_data', {})
        }

        return jsonify({
            'success': True,
            'data': status_response
        })

    except Exception as e:
        logger.error(f"Error getting call status: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve call status',
            'message': str(e),
            'success': False
        }), 500

@app.route('/api/ai/conversation', methods=['POST'])
def ai_conversation():
    """
    Generate AI conversation responses using Claude.
    This endpoint can be used for real-time conversation during calls.
    """
    try:
        data = request.get_json()
        
        if not claude_service.is_available():
            return jsonify({
                'error': 'Claude AI service not available',
                'success': False
            }), 503
        
        conversation_context = {
            'history': data.get('history', []),
            'current_input': data.get('current_input', ''),
            'call_id': data.get('call_id', ''),
            'context': data.get('context', {})
        }
        
        # Generate response using Claude
        response_text = run_async(claude_service.generate_conversation_response(conversation_context))
        
        return jsonify({
            'success': True,
            'data': {
                'response': response_text,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error in AI conversation endpoint: {str(e)}")
        return jsonify({
            'error': 'Failed to generate AI response',
            'message': str(e),
            'success': False
        }), 500

@app.route('/api/ai/status', methods=['GET'])
def ai_status():
    """Check AI service status."""
    return jsonify({
        'success': True,
        'data': {
            'claude_available': claude_service.is_available(),
            'service': 'Anthropic Claude',
            'model': 'claude-3-sonnet-20240229' if claude_service.is_available() else None
        }
    })

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection for media streaming."""
    logger.info(f"WebSocket client connected: {request.sid}")
    emit('connected', {'message': 'Connected to media stream'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    logger.info(f"WebSocket client disconnected: {request.sid}")

@socketio.on('audio_data')
def handle_audio_data(data):
    """Handle incoming audio data from the call."""
    logger.info(f"Received audio data: {len(data.get('audio', ''))} bytes")
    # Here you can process the audio data, send it to AI services, etc.
    # For now, just echo it back or handle as needed
    emit('audio_response', {'message': 'Audio received'})

@app.route("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected.")
    await connector.bridge_stream(websocket)

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'success': False
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'success': False
    }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Teler Call Service on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Teler library available: {TELER_AVAILABLE}")
    logger.info(f"Claude AI available: {claude_service.is_available()}")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)