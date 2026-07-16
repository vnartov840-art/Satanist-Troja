from flask import Flask, render_template, jsonify, request, send_file
import sqlite3
import json
import requests
import threading
import time
from datetime import datetime, timedelta
import os
import io
import base64

app = Flask(__name__, instance_path='/tmp/instance')

DB_PATH = '/tmp/devices.db'
FILES_DIR = '/tmp/files'
os.makedirs(FILES_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id TEXT PRIMARY KEY, 
                  name TEXT, 
                  model TEXT, 
                  status TEXT, 
                  battery INTEGER,
                  ip TEXT,
                  last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  device_id TEXT,
                  command TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS files
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  device_id TEXT,
                  filename TEXT,
                  data TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/devices')
def get_devices():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM devices ORDER BY last_seen DESC')
    devices = []
    for row in c.fetchall():
        devices.append({
            'id': row[0],
            'name': row[1],
            'model': row[2],
            'status': row[3],
            'battery': row[4],
            'ip': row[5],
            'last_seen': row[6]
        })
    conn.close()
    return jsonify(devices)

@app.route('/api/update', methods=['POST'])
def update_device():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO devices (id, name, model, status, battery, ip, last_seen)
                 VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
              (data['id'], data['name'], data['model'], 'online', data.get('battery', 0), data.get('ip', '')))
    conn.commit()
    conn.close()
    return 'OK'

# ===== ОЧЕРЕДЬ КОМАНД =====
@app.route('/api/command', methods=['POST'])
def add_command():
    data = request.json
    device_id = data.get('deviceId')
    command = data.get('command')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO commands (device_id, command) VALUES (?, ?)', (device_id, command))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'ok'})

@app.route('/api/poll/<device_id>')
def poll_commands(device_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, command FROM commands WHERE device_id = ? AND status = "pending" ORDER BY id LIMIT 1', (device_id,))
    row = c.fetchone()
    if row:
        c.execute('UPDATE commands SET status = "sent" WHERE id = ?', (row[0],))
        conn.commit()
        conn.close()
        return jsonify({'command': row[1]})
    conn.close()
    return jsonify({'command': None})

# ===== ЗАГРУЗКА ФАЙЛОВ =====
@app.route('/api/upload', methods=['POST'])
def upload_file():
    data = request.json
    device_id = data.get('deviceId')
    filename = data.get('filename')
    content = data.get('content')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO files (device_id, filename, data) VALUES (?, ?, ?)', 
              (device_id, filename, content))
    conn.commit()
    conn.close()
    return 'OK'

@app.route('/api/download/<device_id>/<filename>')
def download_file(device_id, filename):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT data FROM files WHERE device_id = ? AND filename = ? ORDER BY id DESC LIMIT 1', 
              (device_id, filename))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            data = base64.b64decode(row[0])
            return send_file(
                io.BytesIO(data),
                as_attachment=True,
                download_name=filename
            )
        except:
            pass
    return 'File not found', 404

# ===== АВТОМАТИЧЕСКИЙ ПЕРЕВОД В ОФФЛАЙН =====
def check_offline():
    with app.app_context():
        while True:
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                five_min_ago = datetime.now() - timedelta(minutes=5)
                c.execute('''UPDATE devices 
                             SET status = 'offline' 
                             WHERE status = 'online' 
                             AND last_seen < ?''', (five_min_ago,))
                conn.commit()
                conn.close()
            except:
                pass
            time.sleep(60)

threading.Thread(target=check_offline, daemon=True).start()

# ===== АВТО-ПИНГ =====
def keep_alive():
    with app.app_context():
        while True:
            try:
                url = f"http://localhost:{os.environ.get('PORT', 5000)}/api/devices"
                requests.get(url, timeout=5)
            except:
                pass
            time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)