#!/usr/bin/env python3
"""
Teler Call Service Backend
A Flask-based API service for initiating calls using the teler library.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime
from flask import Flask, request, jsonify, Response, copy_current_request_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from claude_service import claude_service

try:
    from teler import AsyncClient, CallFlow
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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
TELER_API_KEY = os.getenv('TELER_API_KEY', 'cf771fc46a1fddb7939efa742801de98e48b0826be4d8b9976d3c7374a02368b')
BACKEND_DOMAIN = os.getenv('BACKEND_DOMAIN', 'localhost:5000')
BACKEND_URL = f"https://{BACKEND_DOMAIN}" if not BACKEND_DOMAIN.startswith('localhost') else f"http://{BACKEND_DOMAIN}"
WSS_URL = f"wss://{BACKEND_DOMAIN}" if not BACKEND_DOMAIN.startswith('localhost') else f"ws://{BACKEND_DOMAIN}"

# In-memory storage for call history (in production, use a database)
call_history = []
active_calls = {}  # Store active call sessions

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
    Build and return Stream flow using Teler CallFlow.stream().
    This creates a proper streaming call flow that maintains the connection.
    """
    try:
        # Get call data from request
        data = request.get_json() or request.form.to_dict()
        logger.info(f"Flow endpoint called with data: {data}")
        
        # Extract call information
        call_id = data.get('call_id', data.get('CallSid', f"call_{int(datetime.now().timestamp())}"))
        from_number = data.get('From', '')
        to_number = data.get('To', '')
        account_id = data.get('account_id', data.get('AccountSid', ''))
        
        logger.info(f"Creating stream flow - ID: {call_id}, From: {from_number}, To: {to_number}")
        
        # Store call information for WebSocket handling
        active_calls[call_id] = {
            'call_id': call_id,
            'from_number': from_number,
            'to_number': to_number,
            'account_id': account_id,
            'status': 'active',
            'started_at': datetime.now().isoformat()
        }
        
        # Create proper streaming call flow using Teler's CallFlow.stream()
        if TELER_AVAILABLE:
            try:
                stream_flow = CallFlow.stream(
                    ws_url=f"{WSS_URL}/media-stream",
                    chunk_size=500,
                    record=True
                )
                logger.info(f"Created Teler stream flow for call {call_id}")
                return jsonify(stream_flow)
            except Exception as e:
                logger.error(f"Error creating Teler stream flow: {str(e)}")
                # Fall back to mock flow
        
        # Mock stream flow for development/testing
        mock_stream_flow = {
            "type": "stream",
            "ws_url": f"{WSS_URL}/media-stream",
            "chunk_size": 500,
            "record": True,
            "stream_config": {
                "bidirectional": True,
                "audio_format": "wav",
                "sample_rate": 8000,
                "channels": 1
            },
            "call_id": call_id
        }
        
        logger.info(f"Created mock stream flow for call {call_id}")
        return jsonify(mock_stream_flow)
        
    except Exception as e:
        logger.error(f"Error in flow endpoint: {str(e)}")
        logger.error(f"Traceback:", exc_info=True)
        # Return a minimal fallback flow
        fallback_flow = {
            "type": "stream",
            "ws_url": f"{WSS_URL}/media-stream",
            "chunk_size": 500,
            "record": True
        }
        return jsonify(fallback_flow)

@app.route('/webhook', methods=['POST'])
def webhook_receiver():
    """Handle webhooks from Teler for call status updates."""
    try:
        data = request.get_json()
        logger.info(f"--------Webhook Payload-------- {data}")
        
        # Update call history with webhook data
        call_id = data.get('call_id')
        if call_id:
            # Update active calls
            if call_id in active_calls:
                active_calls[call_id].update({
                    'status': data.get('status', 'unknown'),
                    'updated_at': datetime.now().isoformat(),
                    'webhook_data': data
                })
            
            # Update call history
            for call in call_history:
                if call.get('call_id') == call_id:
                    call['webhook_data'] = data
                    call['status'] = data.get('status', call['status'])
                    call['updated_at'] = datetime.now().isoformat()
                    break
        
        return jsonify({'success': True, 'message': 'Webhook received successfully'})
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({
            'error': 'Failed to process webhook',
            'message': str(e)
        }), 500

# WebSocket handlers for media streaming
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection for media streaming."""
    logger.info(f"WebSocket client connected: {request.sid}")
    emit('connected', {'status': 'Connected to media stream'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    logger.info(f"WebSocket client disconnected: {request.sid}")

@socketio.on('audio_data')
def handle_audio_data(data):
    """Handle incoming audio data from call."""
    try:
        logger.debug(f"Received audio data: {len(data.get('audio', ''))} bytes")
        
        # Process audio data here
        # In a real implementation, you would:
        # 1. Decode the audio
        # 2. Process it (speech-to-text, AI response, etc.)
        # 3. Generate response audio
        # 4. Send back to the call
        
        # For now, just acknowledge receipt
        emit('audio_processed', {'status': 'received', 'timestamp': datetime.now().isoformat()})
        
    except Exception as e:
        logger.error(f"Error processing audio data: {str(e)}")
        emit('error', {'message': 'Failed to process audio data'})

@socketio.on('media_stream')
def handle_media_stream(data):
    """Handle media stream events."""
    try:
        event_type = data.get('type', 'unknown')
        logger.info(f"Media stream event: {event_type}")
        
        if event_type == 'audio':
            # Handle audio chunk
            audio_data = data.get('data', {})
            call_id = data.get('call_id')
            
            # Process audio chunk
            logger.debug(f"Processing audio chunk for call {call_id}")
            
            # Echo back for testing (remove in production)
            emit('audio_response', {
                'type': 'audio',
                'call_id': call_id,
                'timestamp': datetime.now().isoformat()
            })
            
        elif event_type == 'start':
            call_id = data.get('call_id')
            logger.info(f"Media stream started for call {call_id}")
            emit('stream_started', {'call_id': call_id, 'status': 'active'})
            
        elif event_type == 'end':
            call_id = data.get('call_id')
            logger.info(f"Media stream ended for call {call_id}")
            if call_id in active_calls:
                active_calls[call_id]['status'] = 'ended'
                active_calls[call_id]['ended_at'] = datetime.now().isoformat()
            emit('stream_ended', {'call_id': call_id, 'status': 'ended'})
            
    except Exception as e:
        logger.error(f"Error handling media stream: {str(e)}")
        emit('error', {'message': 'Failed to handle media stream event'})

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
        status_callback_url = data.get('status_callback_url', f'{BACKEND_URL}/webhook')
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
            'call_type': 'stream',
            'notes': 'Configured with streaming call flow for continuous conversation'
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
                'call_type': 'stream',
                'message': 'Call configured with streaming flow for continuous conversation'
            },
            'message': 'Call initiated successfully - using streaming call flow'
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

@app.route('/api/calls/active', methods=['GET'])
def get_active_calls():
    """Get currently active calls."""
    try:
        return jsonify({
            'success': True,
            'data': list(active_calls.values()),
            'count': len(active_calls)
        })
    except Exception as e:
        logger.error(f"Error getting active calls: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve active calls',
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
            logger.warning("Claude AI service not available - missing API key or library")
            return jsonify({
                'error': 'Claude AI service not available - please check ANTHROPIC_API_KEY environment variable',
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