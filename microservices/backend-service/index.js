const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'backend-service', timestamp: new Date().toISOString() });
});

// Sample data - simulating a product catalog
const products = [
  { id: 1, name: 'Cloud Server', price: 29.99, category: 'compute' },
  { id: 2, name: 'Object Storage', price: 9.99, category: 'storage' },
  { id: 3, name: 'Load Balancer', price: 19.99, category: 'network' },
  { id: 4, name: 'Database Instance', price: 49.99, category: 'database' },
  { id: 5, name: 'CDN Service', price: 14.99, category: 'network' },
];

// GET all products
app.get('/api/products', (req, res) => {
  const { category } = req.query;
  if (category) {
    return res.json(products.filter(p => p.category === category));
  }
  res.json(products);
});

// GET single product
app.get('/api/products/:id', (req, res) => {
  const product = products.find(p => p.id === parseInt(req.params.id));
  if (!product) return res.status(404).json({ error: 'Product not found' });
  res.json(product);
});

// POST create product
app.post('/api/products', (req, res) => {
  const { name, price, category } = req.body;
  if (!name || !price || !category) {
    return res.status(400).json({ error: 'name, price, and category are required' });
  }
  const newProduct = { id: products.length + 1, name, price, category };
  products.push(newProduct);
  res.status(201).json(newProduct);
});

// Metrics endpoint (for Prometheus)
app.get('/metrics', (req, res) => {
  res.set('Content-Type', 'text/plain');
  res.send(`
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{service="backend-service"} ${Math.floor(Math.random() * 1000)}
# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1"} ${Math.floor(Math.random() * 500)}
http_request_duration_seconds_bucket{le="0.5"} ${Math.floor(Math.random() * 800)}
http_request_duration_seconds_bucket{le="1.0"} ${Math.floor(Math.random() * 900)}
# HELP service_up Service health status
# TYPE service_up gauge
service_up{service="backend-service"} 1
  `.trim());
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Backend service running on port ${PORT}`);
});
