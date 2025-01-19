import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3000;

// Serve static files from the public directory
app.use(express.static('public'));

// Serve node_modules directory for ES modules
app.use('/node_modules', express.static('node_modules', {
  setHeaders: (res, path) => {
    if (path.endsWith('.js')) {
      res.setHeader('Content-Type', 'application/javascript');
    } else if (path.endsWith('.css')) {
      res.setHeader('Content-Type', 'text/css');
    }
  }
}));

// Pass environment variables to frontend
app.get('/config.js', (req, res) => {
  res.type('application/javascript');
  res.send(`window.CESIUM_ACCESS_TOKEN = "${process.env.CESIUM_ACCESS_TOKEN}";`);
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});