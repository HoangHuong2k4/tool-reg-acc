/**
 * Proxy server - forward requests to dongvanfb API with correct Origin
 * Run: node proxy.js
 * Open: http://localhost:3000
 */
const http  = require('http');
const https = require('https');
const fs    = require('fs');
const path  = require('path');
const url   = require('url');

const PORT         = 3000;
const FAKE_ORIGIN  = 'https://dongvanfb.net';
const FAKE_REFERER = 'https://dongvanfb.net/';
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js'  : 'application/javascript; charset=utf-8',
  '.css' : 'text/css; charset=utf-8',
  '.ico' : 'image/x-icon',
};

function proxyRequest(req, res, hostname, apiPath) {
  var chunks = [];
  req.on('data', function(d) { chunks.push(d); });
  req.on('end', function() {
    var body = Buffer.concat(chunks);
    var options = {
      hostname: hostname,
      port: 443,
      path: apiPath,
      method: 'POST',
      headers: {
        'Content-Type'  : 'application/json',
        'Content-Length': Buffer.byteLength(body),
        'Origin'        : FAKE_ORIGIN,
        'Referer'       : FAKE_REFERER,
        'User-Agent'    : UA,
        'Accept'        : 'application/json',
      }
    };

    var proxyReq = https.request(options, function(proxyRes) {
      var data = [];
      proxyRes.on('data', function(c) { data.push(c); });
      proxyRes.on('end', function() {
        var result = Buffer.concat(data);
        res.writeHead(proxyRes.statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(result);
      });
    });

    proxyReq.on('error', function(e) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: false, error: e.message }));
    });

    proxyReq.write(body);
    proxyReq.end();
  });
}

const server = http.createServer(function(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  if (req.method === 'POST' && req.url === '/api/get_messages_oauth2') {
    proxyRequest(req, res, 'tools.dongvanfb.net', '/api/get_messages_oauth2');
    return;
  }

  if (req.method === 'POST' && req.url === '/api/getOauth2') {
    proxyRequest(req, res, 'api.dongvanfb.net', '/api/getOauth2');
    return;
  }

  // Serve static files
  var parsedUrl = url.parse(req.url);
  var pathname  = parsedUrl.pathname === '/' ? '/read_mail.html' : parsedUrl.pathname;
  var filePath  = path.join(__dirname, pathname);
  var ext       = path.extname(filePath);

  fs.readFile(filePath, function(err, data) {
    if (err) { res.writeHead(404, { 'Content-Type': 'text/plain' }); res.end('404 Not Found: ' + pathname); return; }
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(data);
  });
});

server.listen(PORT, function() {
  console.log('\n  Proxy server dang chay!\n  http://localhost:' + PORT + '\n');
});
