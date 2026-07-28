const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const rootDir = __dirname;
const uploadsDir = path.join(rootDir, 'uploads');
const statsFile = path.join(rootDir, 'data', 'stats.json');
const videosFile = path.join(rootDir, 'data', 'videos.json');

fs.mkdirSync(uploadsDir, { recursive: true });
fs.mkdirSync(path.dirname(statsFile), { recursive: true });
fs.mkdirSync(path.dirname(videosFile), { recursive: true });

if (!fs.existsSync(statsFile)) {
  fs.writeFileSync(statsFile, JSON.stringify({ downloads: 1240, users: 86, episodes: 124, series: 28 }, null, 2));
}

if (!fs.existsSync(videosFile)) {
  fs.writeFileSync(videosFile, JSON.stringify([], null, 2));
}

const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.mp4': 'video/mp4',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
};

const readJSON = (filePath) => {
  try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); } catch { return []; }
};

const writeJSON = (filePath, data) => {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
};

const server = http.createServer((req, res) => {
  const requestUrl = new URL(req.url, `http://${req.headers.host}`);
  const pathname = decodeURIComponent(requestUrl.pathname);

  if (req.method === 'GET' && pathname === '/api/stats') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(readJSON(statsFile)));
    return;
  }

  if (req.method === 'GET' && pathname === '/api/videos') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(readJSON(videosFile)));
    return;
  }

  if (req.method === 'POST' && pathname === '/api/upload') {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const boundary = req.headers['content-type']?.split('boundary=')[1];
      if (!boundary) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: 'boundary manquant' }));
        return;
      }

      const body = Buffer.concat(chunks).toString('binary');
      const filenameMatch = body.match(/filename="([^"]+)"/);
      const filename = filenameMatch ? filenameMatch[1] : 'video.mp4';
      const filePath = path.join(uploadsDir, filename);
      const start = body.indexOf('\r\n\r\n') + 4;
      const end = body.lastIndexOf('\r\n--' + boundary);
      const fileData = Buffer.from(body.slice(start, end), 'binary');
      fs.writeFileSync(filePath, fileData);

      const videos = readJSON(videosFile);
      videos.unshift({
        id: Date.now(),
        name: filename,
        path: `/uploads/${filename}`,
        size: fileData.length,
        uploadedAt: new Date().toISOString()
      });
      writeJSON(videosFile, videos);

      const stats = readJSON(statsFile);
      stats.downloads += 1;
      stats.episodes += 1;
      writeJSON(statsFile, stats);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, file: `/uploads/${filename}` }));
    });
    return;
  }

  if (pathname.startsWith('/uploads/')) {
    const filePath = path.join(rootDir, pathname.replace(/^\//, ''));
    if (fs.existsSync(filePath)) {
      const ext = path.extname(filePath).toLowerCase();
      res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
      fs.createReadStream(filePath).pipe(res);
      return;
    }
  }

  if (pathname === '/admin/upload.html') {
    const filePath = path.join(rootDir, 'admin', 'upload.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/admin/dashboard.html') {
    const filePath = path.join(rootDir, 'admin', 'dashboard.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/admin/statistics.html') {
    const filePath = path.join(rootDir, 'admin', 'statistics.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/admin/series.html') {
    const filePath = path.join(rootDir, 'admin', 'series.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/admin/films.html') {
    const filePath = path.join(rootDir, 'admin', 'films.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/admin/users.html') {
    const filePath = path.join(rootDir, 'admin', 'users.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/admin/settings.html') {
    const filePath = path.join(rootDir, 'admin', 'settings.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/admin/login.html') {
    const filePath = path.join(rootDir, 'admin', 'login.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  if (pathname === '/') {
    const filePath = path.join(rootDir, 'index.html');
    const data = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
    return;
  }

  const filePath = path.join(rootDir, pathname.replace(/^\//, ''));
  if (fs.existsSync(filePath)) {
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('Not found');
});

server.listen(3000, () => {
  console.log('Serveur lancé sur http://localhost:3000');
});
