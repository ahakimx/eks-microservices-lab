const express = require('express');
const axios = require('axios');
const app = express();
const PORT = process.env.PORT || 3001;

const BACKEND_URL = process.env.BACKEND_URL || 'http://backend-service:3000';

app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'api-gateway', timestamp: new Date().toISOString() });
});

// Proxy to backend - GET products
app.get('/api/v1/products', async (req, res) => {
  try {
    const response = await axios.get(`${BACKEND_URL}/api/products`, { params: req.query });
    res.json({ data: response.data, source: 'api-gateway', backend: 'backend-service' });
  } catch (err) {
    res.status(502).json({ error: 'Backend unavailable', details: err.message });
  }
});

// Proxy to backend - GET single product
app.get('/api/v1/products/:id', async (req, res) => {
  try {
    const response = await axios.get(`${BACKEND_URL}/api/products/${req.params.id}`);
    res.json({ data: response.data, source: 'api-gateway' });
  } catch (err) {
    if (err.response && err.response.status === 404) {
      return res.status(404).json({ error: 'Product not found' });
    }
    res.status(502).json({ error: 'Backend unavailable', details: err.message });
  }
});

// Proxy to backend - POST product
app.post('/api/v1/products', async (req, res) => {
  try {
    const response = await axios.post(`${BACKEND_URL}/api/products`, req.body);
    res.status(201).json({ data: response.data, source: 'api-gateway' });
  } catch (err) {
    if (err.response) {
      return res.status(err.response.status).json(err.response.data);
    }
    res.status(502).json({ error: 'Backend unavailable', details: err.message });
  }
});

// Aggregate health check (checks all downstream services)
app.get('/api/v1/health', async (req, res) => {
  const services = {};
  try {
    const backendHealth = await axios.get(`${BACKEND_URL}/health`, { timeout: 2000 });
    services.backend = backendHealth.data;
  } catch {
    services.backend = { status: 'unhealthy' };
  }

  const allHealthy = Object.values(services).every(s => s.status === 'healthy');
  res.status(allHealthy ? 200 : 503).json({
    status: allHealthy ? 'healthy' : 'degraded',
    service: 'api-gateway',
    downstream: services,
    timestamp: new Date().toISOString(),
  });
});

// Metrics endpoint
app.get('/metrics', (req, res) => {
  res.set('Content-Type', 'text/plain');
  res.send(`
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{service="api-gateway"} ${Math.floor(Math.random() * 2000)}
# HELP upstream_latency_seconds Upstream service latency
# TYPE upstream_latency_seconds histogram
upstream_latency_seconds_bucket{service="backend-service",le="0.1"} ${Math.floor(Math.random() * 400)}
upstream_latency_seconds_bucket{service="backend-service",le="0.5"} ${Math.floor(Math.random() * 700)}
# HELP service_up Service health status
# TYPE service_up gauge
service_up{service="api-gateway"} 1
  `.trim());
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`API Gateway running on port ${PORT}`);
});
