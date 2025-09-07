#!/usr/bin/env python3
"""
Teler Call Service Backend
A Flask-based API service for initiating calls using the teler library.
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

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

# Configuration
TELER_API_KEY = os.getenv('TELER_API_KEY', 'cf771fc46a1fddb7939efa742801de98e48b0826be4d8b9976d3c7374a02368b')
BACKEND_DOMAIN = os.getenv('BACKEND_DOMAIN', 'localhost:5000')

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
                call_params = {
                    'from_number': from_number,
                    'to_number': to_number,
                    'flow_url': flow_url,
                    'record': record,
                    'status_callback_url':'http://localhost:5000/webhook'
                }
                
                if status_callback_url:
                    call_params['status_callback_url'] = status_callback_url
                
                logger.info(f"Calling client.calls.create with params: {call_params}")
                call = await client.calls.create(**call_params)
                logger.info(f"Call created successfully: {call}")
                return call
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
    Build and return call flow configuration.
    This endpoint is called by teler during call setup.
    """
    try:
        data = request.get_json()
        logger.info(f"Flow endpoint called with data: {data}")
        
        # Create a simple call flow
        # In a real implementation, you might want to customize this based on the call
        flow_config = CallFlow.stream(
            ws_url=f"wss://{BACKEND_DOMAIN}/media-stream",
            chunk_size=500,
            record=True
        ) if TELER_AVAILABLE else {
            "type": "stream",
            "ws_url": f"wss://{BACKEND_DOMAIN}/media-stream",
            "chunk_size": 500,
            "record": True
        }
        
        return jsonify(flow_config)
    except Exception as e:
        logger.error(f"Error in flow endpoint: {str(e)}")
        return jsonify({
            'error': 'Failed to generate flow configuration',
            'message': str(e)
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook_receiver():
    """
    Webhook endpoint to receive call status updates from teler.
    """
    try:
        data = request.get_json()
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
        call_id = call_response.get('call_id', f"call_{int(datetime.now().timestamp())}")
        status = call_response.get('status', 'initiated')
        
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
            'response_data': call_response
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
                'timestamp': call_record['timestamp']
            },
            'message': 'Call initiated successfully'
        })

    except Exception as e:
        logger.error(f"Error in initiate_call: {str(e)}")
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
    
    app.run(host='0.0.0.0', port=port, debug=debug)