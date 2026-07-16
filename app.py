from flask import Flask, render_template, jsonify, request, send_file
import sqlite3
import json
import requests
import threading
import time
from datetime import datetime, timedelta
import os
import io

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

@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    device_id = data.get('deviceId')
    command = data.get('command')
    
    try:
        token = "8876390846:AAELEYzUJAUpH3ysUeOO9IdMMBy3mKYzxig"
        admin_id = "6178711912"
        text = f"📩 КОМАНДА\nID: {device_id}\nКоманда: {command}"
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": admin_id, "text": text}, timeout=5)
        return jsonify({"status": "ok", "message": "Команда отправлена"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

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
            except Exception as e:
                print(f"❌ Ошибка: {e}")
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