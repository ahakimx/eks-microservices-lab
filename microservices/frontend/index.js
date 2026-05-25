const express = require('express');
const axios = require('axios');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3002;

const API_GATEWAY_URL = process.env.API_GATEWAY_URL || 'http://api-gateway:3001';

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'frontend', timestamp: new Date().toISOString() });
});

// Proxy API calls to gateway
app.get('/api/*', async (req, res) => {
  try {
    const response = await axios.get(`${API_GATEWAY_URL}${req.path}`, { params: req.query });
    res.json(response.data);
  } catch (err) {
    if (err.response) {
      return res.status(err.response.status).json(err.response.data);
    }
    res.status(502).json({ error: 'API Gateway unavailable' });
  }
});

// Serve frontend HTML
app.get('/', (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EKS Lab - Cloud Products</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }
    .container { max-width: 900px; margin: 0 auto; }
    h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #38bdf8; }
    .subtitle { color: #94a3b8; margin-bottom: 2rem; }
    .status { display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }
    .status-card { background: #1e293b; border-radius: 8px; padding: 1rem 1.5rem; flex: 1; min-width: 200px; }
    .status-card h3 { font-size: 0.8rem; text-transform: uppercase; color: #64748b; margin-bottom: 0.5rem; }
    .status-card .value { font-size: 1.5rem; font-weight: bold; }
    .healthy { color: #4ade80; }
    .products { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1rem; }
    .product-card { background: #1e293b; border-radius: 8px; padding: 1.5rem; border: 1px solid #334155; }
    .product-card h3 { color: #f1f5f9; margin-bottom: 0.5rem; }
    .product-card .price { color: #38bdf8; font-size: 1.25rem; font-weight: bold; }
    .product-card .category { color: #64748b; font-size: 0.85rem; margin-top: 0.5rem; }
    .footer { margin-top: 2rem; text-align: center; color: #475569; font-size: 0.85rem; }
  </style>
</head>
<body>
  <div class="container">
    <h1>☁️ Cloud Products</h1>
    <p class="subtitle">EKS Lab Microservices Demo</p>
    <div class="status">
      <div class="status-card"><h3>Cluster</h3><div class="value healthy">● Healthy</div></div>
      <div class="status-card"><h3>Services</h3><div class="value">3 / 3</div></div>
      <div class="status-card"><h3>Version</h3><div class="value">v1.0.0</div></div>
    </div>
    <div class="products" id="products">Loading...</div>
    <div class="footer">
      <p>Frontend → API Gateway → Backend Service | Running on EKS 1.34</p>
    </div>
  </div>
  <script>
    fetch('/api/v1/products')
      .then(r => r.json())
      .then(res => {
        const products = res.data || [];
        document.getElementById('products').innerHTML = products.map(p => 
          '<div class="product-card"><h3>' + p.name + '</h3><div class="price">$' + p.price + '/mo</div><div class="category">' + p.category + '</div></div>'
        ).join('');
      })
      .catch(() => {
        document.getElementById('products').innerHTML = '<p style="color:#f87171">Failed to load products. API Gateway may be down.</p>';
      });
  </script>
</body>
</html>`);
});

// Metrics
app.get('/metrics', (req, res) => {
  res.set('Content-Type', 'text/plain');
  res.send(`
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{service="frontend"} ${Math.floor(Math.random() * 3000)}
# HELP service_up Service health status
# TYPE service_up gauge
service_up{service="frontend"} 1
  `.trim());
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend running on port ${PORT}`);
});
