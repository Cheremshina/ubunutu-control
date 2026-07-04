# sftp.py
import paramiko
import os
from datetime import datetime
from typing import List, Dict, Optional
import logging
import stat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SFTPHandler:
    def __init__(self, host: str, port: int, username: str, password: str = None, key_filename: str = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.client = None
        self.sftp = None

    def connect(self) -> bool:
        """Подключение к SFTP серверу"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if self.password:
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10,
                    allow_agent=False,
                    look_for_keys=False
                )
            else:
                return False

            self.sftp = self.client.open_sftp()
            logger.info(f"Connected to SFTP server: {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            return False

    def disconnect(self):
        """Отключение"""
        try:
            if self.sftp:
                self.sftp.close()
            if self.client:
                self.client.close()
        except:
            pass

    def list_directory(self, path: str = '/') -> List[Dict]:
        """Получить содержимое директории"""
        try:
            if not self.sftp:
                return []

            if not path or path == '.':
                target_path = '/'
            else:
                target_path = path

            items = []
            for item in self.sftp.listdir_attr(target_path):
                if item.filename in ['.', '..']:
                    continue

                if target_path == '/':
                    full_path = '/' + item.filename
                else:
                    full_path = target_path.rstrip('/') + '/' + item.filename

                is_directory = stat.S_ISDIR(item.st_mode)

                items.append({
                    'name': item.filename,
                    'size': item.st_size,
                    'is_directory': is_directory,
                    'modified': datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'path': full_path
                })

            items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
            return items

        except Exception as e:
            logger.error(f"List error: {str(e)}")
            return []

    def get_current_directory(self) -> str:
        try:
            return self.sftp.getcwd() if self.sftp else '/'
        except:
            return '/'

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Скачать файл"""
        try:
            self.sftp.get(remote_path, local_path)
            return True
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return False

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Загрузить файл"""
        try:
            # Создаем директорию если нужно
            remote_dir = os.path.dirname(remote_path)
            if remote_dir and remote_dir != '/':
                try:
                    self.sftp.stat(remote_dir)
                except:
                    self._create_directories(remote_dir)

            self.sftp.put(local_path, remote_path)
            return True
        except Exception as e:
            logger.error(f"Upload error: {str(e)}")
            return False

    def read_file_content(self, remote_path: str) -> Optional[str]:
        """Прочитать содержимое текстового файла"""
        try:
            with self.sftp.open(remote_path, 'r') as f:
                content = f.read()
                # Пытаемся декодировать как UTF-8
                try:
                    return content.decode('utf-8')
                except:
                    return content.decode('latin-1')
        except Exception as e:
            logger.error(f"Read error: {str(e)}")
            return None

    def write_file_content(self, remote_path: str, content: str) -> bool:
        """Записать содержимое в файл"""
        try:
            with self.sftp.open(remote_path, 'w') as f:
                f.write(content.encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"Write error: {str(e)}")
            return False

    def delete_file(self, path: str) -> bool:
        """Удалить файл или папку"""
        try:
            attrs = self.sftp.stat(path)
            if stat.S_ISDIR(attrs.st_mode):
                self._delete_directory_recursive(path)
            else:
                self.sftp.remove(path)
            return True
        except Exception as e:
            logger.error(f"Delete error: {str(e)}")
            return False

    def create_directory(self, path: str) -> bool:
        """Создать директорию"""
        try:
            self.sftp.mkdir(path)
            return True
        except Exception as e:
            logger.error(f"Mkdir error: {str(e)}")
            return False

    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Переименовать"""
        try:
            self.sftp.rename(old_path, new_path)
            return True
        except Exception as e:
            logger.error(f"Rename error: {str(e)}")
            return False

    def _create_directories(self, path: str):
        """Рекурсивно создать директории"""
        clean_path = path.lstrip('/')
        if not clean_path:
            return

        dirs = clean_path.split('/')
        current_path = ''

        for dir_name in dirs:
            if not dir_name:
                continue

            if current_path:
                current_path += '/' + dir_name
            else:
                current_path = '/' + dir_name

            try:
                self.sftp.stat(current_path)
            except:
                self.sftp.mkdir(current_path)

    def _delete_directory_recursive(self, path: str):
        """Рекурсивное удаление директории"""
        for item in self.sftp.listdir(path):
            item_path = path.rstrip('/') + '/' + item
            attrs = self.sftp.stat(item_path)
            if stat.S_ISDIR(attrs.st_mode):
                self._delete_directory_recursive(item_path)
            else:
                self.sftp.remove(item_path)
        self.sftp.rmdir(path)