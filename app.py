# app.py
from flask import Flask, render_template, request, jsonify, session, send_file, after_this_request
from functools import wraps
import os
import tempfile
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

sftp_connections = {}


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

@app.route('/sftp')
def sft():
    return render_template('sftp.html')

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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)