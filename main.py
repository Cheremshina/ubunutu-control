from os.path import join

from flask import Flask, render_template, request, jsonify, session, send_file, after_this_request
from flask_socketio import SocketIO, emit
import paramiko
import threading
import queue
import time
import os
import secrets
import random as r
import tempfile
import logging
import traceback
from functools import wraps

num = r.randint(100000000, 999999999)
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['DEBUG'] = False  # Отключаем debug режим для избежания проблем
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Используем простой async_mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Хранилище SSH сессий
ssh_sessions = {}
sftp_connections = {}

selecti = {
    "numcode": f"{num}"
}

def get_sftp_handler():
    session_id = session.get('session_id')
    if session_id and session_id in sftp_connections:
        return sftp_connections[session_id]
    return None

def sftp_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        handler = get_sftp_handler()
        if not handler:
            return jsonify({'error': 'Not connected'}), 401
        return f(handler, *args, **kwargs)

    return decorated_function

@app.route('/api/connect', methods=['POST'])
def connect():
    try:
        data = request.get_json()
        host = data.get('host')
        port = data.get('port', 22)
        username = data.get('username')
        password = data.get('password')

        if not host or not username:
            return jsonify({'error': 'Host and username required'}), 400

        from sftp import SFTPHandler
        handler = SFTPHandler(host, int(port), username, password)

        if handler.connect():
            import time
            session_id = str(time.time())
            session['session_id'] = session_id
            sftp_connections[session_id] = handler

            # Пытаемся перейти в домашнюю директорию
            try:
                home_dir = f'/home/{username}'
                handler.sftp.stat(home_dir)
                current_dir = home_dir
            except:
                current_dir = handler.get_current_directory()

            return jsonify({
                'success': True,
                'message': f'Connected to {host} as {username}',
                'current_dir': current_dir
            })
        else:
            return jsonify({'error': 'Connection failed'}), 401

    except Exception as e:
        logger.error(f"Connect error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    session_id = session.get('session_id')
    if session_id and session_id in sftp_connections:
        try:
            sftp_connections[session_id].disconnect()
            del sftp_connections[session_id]
        except:
            pass
    session.clear()
    return jsonify({'success': True})


@app.route('/api/list', methods=['GET'])
@sftp_required
def list_directory(handler):
    try:
        path = request.args.get('path', '/')
        items = handler.list_directory(path)
        current_dir = path if path != '/' else handler.get_current_directory()

        parent_dir = None
        if current_dir and current_dir != '/':
            parent_dir = os.path.dirname(current_dir)
            if not parent_dir:
                parent_dir = '/'

        return jsonify({
            'success': True,
            'current_dir': current_dir,
            'parent_dir': parent_dir,
            'items': items
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<path:filepath>', methods=['GET'])
@sftp_required
def download_file(handler, filepath):
    temp_path = None
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_path = temp_file.name
        temp_file.close()

        if handler.download_file(filepath, temp_path):
            @after_this_request
            def cleanup(response):
                try:
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
                return response

            return send_file(
                temp_path,
                as_attachment=True,
                download_name=os.path.basename(filepath)
            )
        else:
            return jsonify({'error': 'Download failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
@sftp_required
def upload_file(handler):
    temp_path = None
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400

        file = request.files['file']
        remote_path = request.form.get('remote_path', '/')

        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_path = temp_file.name
        file.save(temp_path)
        temp_file.close()

        if remote_path == '/':
            full_path = '/' + file.filename
        else:
            full_path = remote_path.rstrip('/') + '/' + file.filename

        if handler.upload_file(temp_path, full_path):
            return jsonify({'success': True, 'message': f'Uploaded {file.filename}'})
        else:
            return jsonify({'error': 'Upload failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


@app.route('/api/read/<path:filepath>', methods=['GET'])
@sftp_required
def read_file(handler, filepath):
    """Прочитать содержимое файла для редактирования"""
    try:
        content = handler.read_file_content(filepath)
        if content is not None:
            return jsonify({
                'success': True,
                'content': content,
                'path': filepath,
                'name': os.path.basename(filepath)
            })
        else:
            return jsonify({'error': 'Failed to read file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save/<path:filepath>', methods=['POST'])
@sftp_required
def save_file(handler, filepath):
    """Сохранить содержимое файла"""
    try:
        data = request.get_json()
        content = data.get('content', '')

        if handler.write_file_content(filepath, content):
            return jsonify({'success': True, 'message': 'File saved successfully'})
        else:
            return jsonify({'error': 'Failed to save file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete', methods=['POST'])
@sftp_required
def delete_item(handler):
    try:
        data = request.get_json()
        path = data.get('path')

        if handler.delete_file(path):
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Delete failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/mkdir', methods=['POST'])
@sftp_required
def create_directory(handler):
    try:
        data = request.get_json()
        path = data.get('path')

        if handler.create_directory(path):
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Create failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rename', methods=['POST'])
@sftp_required
def rename_item(handler):
    try:
        data = request.get_json()
        old_path = data.get('old_path')
        new_path = data.get('new_path')

        if handler.rename_file(old_path, new_path):
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Rename failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

class WebSSHSession:
    def __init__(self, sid, host, port, username, password):
        self.sid = sid
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None
        self.channel = None
        self.running = False
        self.thread = None

    def connect(self):
        """Подключение к SSH серверу"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )

            # Создаем интерактивную оболочку
            self.channel = self.client.invoke_shell(term='xterm')
            self.channel.settimeout(1)

            self.running = True
            self.thread = threading.Thread(target=self._read_output)
            self.thread.daemon = True
            self.thread.start()

            return True, "Подключено успешно"
        except Exception as e:
            return False, str(e)

    def _read_output(self):
        """Чтение вывода из SSH канала"""
        while self.running and self.channel:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(4096)
                    if data:
                        try:
                            decoded_data = data.decode('utf-8', errors='replace')
                            socketio.emit('ssh_output', {
                                'data': decoded_data
                            }, room=self.sid)
                        except:
                            pass

                # Проверка статуса канала
                if self.channel.exit_status_ready():
                    self.running = False
                    socketio.emit('ssh_disconnected', {
                        'message': 'Соединение закрыто'
                    }, room=self.sid)
                    break

                time.sleep(0.05)
            except Exception as e:
                if self.running:
                    socketio.emit('ssh_error', {
                        'error': str(e)
                    }, room=self.sid)
                break

    def send_command(self, command):
        """Отправка команды в SSH сессию"""
        if self.channel and self.running:
            try:
                self.channel.send(command)
                return True
            except Exception as e:
                print(f"Ошибка отправки команды: {e}")
                return False
        return False

    def resize_pty(self, cols, rows):
        """Изменение размера терминала"""
        if self.channel and self.running:
            try:
                self.channel.resize_pty(width=cols, height=rows)
                return True
            except:
                pass
        return False

    def close(self):
        """Закрытие SSH соединения"""
        self.running = False
        if self.channel:
            self.channel.close()
        if self.client:
            self.client.close()

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html', **selecti)

@app.route('/sshterminal')
def ssh():
    """Главная страница"""
    return render_template('ssh_terminal.html')

@app.route('/sftp')
def sft():
    return render_template('sftp.html')

@socketio.on('connect')
def handle_connect():
    """Обработка подключения WebSocket"""
    print(f'✅ Клиент подключен: {request.sid}')


@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения WebSocket"""
    if request.sid in ssh_sessions:
        ssh_sessions[request.sid].close()
        del ssh_sessions[request.sid]
    print(f'❌ Клиент отключен: {request.sid}')


@socketio.on('ssh_connect')
def handle_ssh_connect(data):
    """Обработка подключения к SSH"""
    host = data.get('host')
    port = data.get('port', 22)
    username = data.get('username')
    password = data.get('password')

    print(f"Попытка подключения к {host}:{port} пользователем {username}")

    if not all([host, username, password]):
        emit('ssh_error', {'error': 'Не все поля заполнены'})
        return

    # Создаем новую SSH сессию
    session = WebSSHSession(
        sid=request.sid,
        host=host,
        port=int(port),
        username=username,
        password=password
    )

    success, message = session.connect()

    if success:
        ssh_sessions[request.sid] = session
        emit('ssh_connected', {'message': message})
        print(f"✅ SSH подключен: {host}")
    else:
        emit('ssh_error', {'error': message})
        print(f"❌ Ошибка SSH: {message}")


@socketio.on('ssh_command')
def handle_ssh_command(data):
    """Обработка отправки команды"""
    command = data.get('command')
    if request.sid in ssh_sessions:
        session = ssh_sessions[request.sid]
        session.send_command(command)


@socketio.on('ssh_resize')
def handle_ssh_resize(data):
    """Обработка изменения размера терминала"""
    cols = data.get('cols', 80)
    rows = data.get('rows', 24)
    if request.sid in ssh_sessions:
        session = ssh_sessions[request.sid]
        session.resize_pty(cols, rows)


@socketio.on('ssh_disconnect')
def handle_ssh_disconnect():
    """Принудительное отключение от SSH"""
    if request.sid in ssh_sessions:
        ssh_sessions[request.sid].close()
        del ssh_sessions[request.sid]
        emit('ssh_disconnected', {'message': 'Отключено по запросу'})


if __name__ == '__main__':
    print("---------------------------------")
    print(f"Ваш одноразовый код подключения: {num}")
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,  # Отключаем debug для стабильности
        use_reloader=False,  # Отключаем авто-перезагрузку
        allow_unsafe_werkzeug = True
    )
