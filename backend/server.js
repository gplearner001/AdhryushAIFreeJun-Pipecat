const express = require('express');
const cors = require('cors');
const axios = require('axios');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Teler configuration
const TELER_CONFIG = {
  access_token: process.env.TELER_ACCESS_TOKEN || 'cf771fc46a1fddb7939efa742801de98e48b0826be4d8b9976d3c7374a02368b',
  base_url: 'https://api.teler.ai/v1' // Assuming this is the base URL
};

// In-memory storage for call history (in production, use a database)
let callHistory = [];

// Routes
app.get('/health', (req, res) => {
  res.json({ status: 'OK', message: 'Teler Backend Service is running' });
});

app.post('/api/calls/initiate', async (req, res) => {
  try {
    const { from_number, to_number, flow_url, status_callback_url } = req.body;

    // Validate required fields
    if (!from_number || !to_number || !flow_url) {
      return res.status(400).json({
        error: 'Missing required fields: from_number, to_number, and flow_url are required'
      });
    }

    // Create call payload
    const callPayload = {
      from_number,
      to_number,
      flow_url,
      status_callback_url: status_callback_url || '',
      access_token: TELER_CONFIG.access_token
    };

    // Note: Since we can't actually install teler-py in WebContainer,
    // this simulates the API call structure
    console.log('Initiating call with payload:', callPayload);
    
    // Simulate API call to teler service
    // In real implementation, you would use the teler-py library or make HTTP requests to teler API
    const mockResponse = {
      call_id: `call_${Date.now()}`,
      status: 'initiated',
      from_number,
      to_number,
      flow_url,
      timestamp: new Date().toISOString()
    };

    // Store in history
    callHistory.push({
      ...mockResponse,
      id: callHistory.length + 1
    });

    res.json({
      success: true,
      data: mockResponse,
      message: 'Call initiated successfully'
    });

  } catch (error) {
    console.error('Error initiating call:', error);
    res.status(500).json({
      error: 'Failed to initiate call',
      message: error.message
    });
  }
});

app.get('/api/calls/history', (req, res) => {
  res.json({
    success: true,
    data: callHistory.reverse(), // Show newest first
    count: callHistory.length
  });
});

app.get('/api/calls/:callId', (req, res) => {
  const { callId } = req.params;
  const call = callHistory.find(c => c.call_id === callId);
  
  if (!call) {
    return res.status(404).json({
      error: 'Call not found'
    });
  }

  res.json({
    success: true,
    data: call
  });
});

app.listen(PORT, () => {
  console.log(`🚀 Teler Backend Service running on port ${PORT}`);
  console.log(`📱 Ready to handle call requests`);
});