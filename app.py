from flask import Flask, render_template, jsonify, request
import sqlite3
import json
import requests
import threading
import time
from datetime import datetime
import os

app = Flask(__name__)

DB_PATH = '/tmp/devices.db'

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
    
    # Проверяем, было ли устройство онлайн
    c.execute('SELECT status FROM devices WHERE id = ?', (data['id'],))
    row = c.fetchone()
    prev_status = row[0] if row else None
    
    # Если пришло "offline" — проверяем, не было ли онлайн 5 минут назад
    if data.get('status') == 'offline' and prev_status == 'online':
        # Оставляем онлайн ещё 5 минут (чтобы не моргало)
        data['status'] = 'online'
    
    c.execute('''INSERT OR REPLACE INTO devices (id, name, model, status, battery, ip, last_seen)
                 VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
              (data['id'], data['name'], data['model'], data['status'], data.get('battery', 0), data.get('ip', '')))
    conn.commit()
    conn.close()
    return 'OK'

@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    device_id = data.get('deviceId')
    command = data.get('command')
    
    # Здесь можно сохранить команду в очередь или отправить через Telegram бота
    # Пока просто логируем
    print(f"📩 Команда для {device_id}: {command}")
    
    # Отправляем команду через Telegram бота (опционально)
    try:
        import requests
        token = "8876390846:AAELEYzUJAUpH3ysUeOO9IdMMBy3mKYzxig"
        admin_id = "6178711912"
        text = f"📩 КОМАНДА ДЛЯ УСТРОЙСТВА\nID: {device_id}\nКоманда: {command}"
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": admin_id, "text": text})
    except:
        pass
    
    return jsonify({"status": "ok"})

# ===== АВТО-ПИНГ (чтобы Render не уснул) =====
def keep_alive():
    """Каждые 10 минут стучит сам себе, чтобы Render не усыплял"""
    with app.app_context():
        while True:
            try:
                # Стучим сами себе
                url = f"http://localhost:{os.environ.get('PORT', 5000)}/api/devices"
                requests.get(url, timeout=5)
                print(f"✅ Пинг в {datetime.now()}")
            except:
                pass
            time.sleep(600)  # 10 минут

# Запускаем поток с пингом
threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)