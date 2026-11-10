const cluster = require('cluster');
const http = require('http');
const os = require('os');

const port = parseInt(process.env.MOCK_PORT || '9099', 10);
const numCPUs = Math.min(os.cpus().length || 4, 4);

if (cluster.isPrimary) {
  for (let i = 0; i < numCPUs; i++) {
    cluster.fork();
  }
  cluster.on('exit', () => {
    cluster.fork();
  });
} else {
  http.createServer((req, res) => {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Content-Length': '27',
      'Connection': 'keep-alive'
    });
    res.end('{"status":"ok","speed":"c"}');
  }).listen(port, '127.0.0.1');
}
