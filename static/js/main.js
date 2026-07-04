// static/js/main.js
let currentPath = '/';
let currentEditor = null;
let currentEditPath = null;

function showMessage(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show alert-fixed`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);

    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}

async function connect() {
    const host = document.getElementById('host').value.trim();
    const port = document.getElementById('port').value;
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!host || !username) {
        showMessage('Заполните хост и имя пользователя', 'warning');
        return;
    }

    showMessage('Подключение...', 'info');

    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port, username, password })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showMessage(data.message, 'success');
            document.getElementById('connectionForm').style.display = 'none';
            document.getElementById('fileBrowser').style.display = 'block';
            currentPath = data.current_dir || '/';
            await loadDirectory();
        } else {
            showMessage(data.error || 'Ошибка подключения', 'danger');
        }
    } catch (error) {
        showMessage('Ошибка: ' + error.message, 'danger');
    }
}

async function disconnect() {
    try {
        await fetch('/api/disconnect', { method: 'POST' });
        showMessage('Отключено', 'info');
        document.getElementById('connectionForm').style.display = 'block';
        document.getElementById('fileBrowser').style.display = 'none';
        currentPath = '/';
    } catch (error) {
        showMessage('Ошибка отключения', 'danger');
    }
}

async function loadDirectory(path = null) {
    const tbody = document.getElementById('fileList');
    tbody.innerHTML = '<tr><td colspan="4" class="text-center"><div class="spinner-border spinner-border-sm"></div> Загрузка...</td</tr>';

    const targetPath = path !== null ? path : currentPath;

    try {
        const response = await fetch(`/api/list?path=${encodeURIComponent(targetPath)}`);
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || 'Ошибка загрузки');

        if (data.success) {
            currentPath = data.current_dir;
            document.getElementById('currentDir').textContent = currentPath;
            renderFileList(data.items, data.parent_dir);
        }
    } catch (error) {
        showMessage('Ошибка загрузки: ' + error.message, 'danger');
        renderFileList([], null);
    }
}

function getFileIcon(filename, isDirectory) {
    if (isDirectory) return '<i class="fas fa-folder folder-icon"></i>';

    const ext = filename.split('.').pop().toLowerCase();
    const textExts = ['txt', 'md', 'log', 'cfg', 'conf', 'ini', 'json', 'xml', 'yaml', 'yml'];
    const codeExts = ['py', 'js', 'html', 'css', 'php', 'java', 'c', 'cpp', 'go', 'rs', 'rb'];
    const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'ico'];

    if (textExts.includes(ext)) return '<i class="fas fa-file-alt text-icon"></i>';
    if (codeExts.includes(ext)) return '<i class="fas fa-code code-icon"></i>';
    if (imageExts.includes(ext)) return '<i class="fas fa-image image-icon"></i>';
    return '<i class="fas fa-file file-icon"></i>';
}

function isEditableFile(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const editableExts = ['txt', 'md', 'log', 'cfg', 'conf', 'ini', 'json', 'xml', 'yaml', 'yml',
                          'py', 'js', 'html', 'css', 'php', 'java', 'c', 'cpp', 'go', 'rs', 'rb',
                          'sh', 'bash', 'zsh', 'fish', 'sql', 'r', 'pl', 'lua', 'toml', 'env'];
    return editableExts.includes(ext);
}

function renderFileList(items, parentDir) {
    const tbody = document.getElementById('fileList');
    tbody.innerHTML = '';

    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Папка пуста</td</tr>';
        return;
    }

    items.forEach(item => {
        const row = tbody.insertRow();
        row.className = 'file-row';

        const iconHtml = getFileIcon(item.name, item.is_directory);

        // Имя файла/папки
        const nameCell = row.insertCell(0);
        nameCell.innerHTML = iconHtml + ' ' + escapeHtml(item.name);
        if (item.is_directory) {
            nameCell.style.cursor = 'pointer';
            nameCell.onclick = () => loadDirectory(item.path);
        }

        // Размер
        const sizeCell = row.insertCell(1);
        sizeCell.textContent = item.is_directory ? '-' : formatFileSize(item.size);

        // Дата
        const dateCell = row.insertCell(2);
        dateCell.textContent = item.modified || '-';

        // Действия
        const actionsCell = row.insertCell(3);
        let actionsHtml = '';

        // Кнопка скачивания (только для файлов)
        if (!item.is_directory) {
            actionsHtml += `<button class="btn btn-sm btn-primary me-1" onclick="event.stopPropagation(); downloadFile('${escapePath(item.path)}')" title="Скачать">
                <i class="fas fa-download"></i>
            </button>`;

            // Кнопка редактирования (для текстовых файлов)
            if (isEditableFile(item.name)) {
                actionsHtml += `<button class="btn btn-sm btn-warning me-1" onclick="event.stopPropagation(); editFile('${escapePath(item.path)}', '${escapeHtml(item.name)}')" title="Редактировать">
                    <i class="fas fa-edit"></i>
                </button>`;
            }
        }

        // Кнопка удаления
        actionsHtml += `<button class="btn btn-sm btn-danger me-1" onclick="event.stopPropagation(); deleteItem('${escapePath(item.path)}')" title="Удалить">
            <i class="fas fa-trash"></i>
        </button>`;

        // Кнопка переименования
        actionsHtml += `<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); renameItem('${escapePath(item.path)}')" title="Переименовать">
            <i class="fas fa-tag"></i>
        </button>`;

        actionsCell.innerHTML = actionsHtml;
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapePath(path) {
    return path.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

async function downloadFile(path) {
    window.open(`/api/download/${encodeURIComponent(path)}`, '_blank');
    showMessage('Скачивание началось...', 'info');
}

async function editFile(path, filename) {
    showMessage('Загрузка файла для редактирования...', 'info');

    try {
        const response = await fetch(`/api/read/${encodeURIComponent(path)}`);
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || 'Ошибка загрузки');

        if (data.success) {
            currentEditPath = path;
            document.getElementById('editFileName').textContent = filename;
            document.getElementById('editorContainer').style.display = 'flex';

            // Инициализируем редактор
            const textarea = document.getElementById('editorTextarea');
            textarea.value = data.content;

            if (currentEditor) {
                currentEditor.setValue(data.content);
            } else {
                // Определяем режим подсветки по расширению
                let mode = 'text/plain';
                const ext = filename.split('.').pop().toLowerCase();
                const modeMap = {
                    'py': 'python', 'js': 'javascript', 'html': 'htmlmixed',
                    'css': 'css', 'json': 'application/json', 'xml': 'xml',
                    'sh': 'shell', 'bash': 'shell', 'yaml': 'yaml', 'yml': 'yaml'
                };
                mode = modeMap[ext] || 'text/plain';

                currentEditor = CodeMirror.fromTextArea(textarea, {
                    lineNumbers: true,
                    mode: mode,
                    theme: 'monokai',
                    indentUnit: 4,
                    lineWrapping: true,
                    autoCloseBrackets: true,
                    matchBrackets: true
                });
            }

            currentEditor.refresh();
        }
    } catch (error) {
        showMessage('Ошибка загрузки файла: ' + error.message, 'danger');
    }
}

async function saveFile() {
    if (!currentEditPath || !currentEditor) return;

    const content = currentEditor.getValue();

    try {
        const response = await fetch(`/api/save/${encodeURIComponent(currentEditPath)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showMessage('Файл сохранен!', 'success');
            closeEditor();
            await loadDirectory(); // Обновляем список файлов
        } else {
            throw new Error(data.error || 'Ошибка сохранения');
        }
    } catch (error) {
        showMessage('Ошибка сохранения: ' + error.message, 'danger');
    }
}

function closeEditor() {
    document.getElementById('editorContainer').style.display = 'none';
    if (currentEditor) {
        currentEditor.toTextArea();
        currentEditor = null;
    }
    currentEditPath = null;
}

async function deleteItem(path) {
    if (confirm(`Удалить "${path}"?`)) {
        try {
            const response = await fetch('/api/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });

            if (response.ok) {
                showMessage('Удалено', 'success');
                await loadDirectory();
            } else {
                const data = await response.json();
                showMessage(data.error || 'Ошибка удаления', 'danger');
            }
        } catch (error) {
            showMessage('Ошибка: ' + error.message, 'danger');
        }
    }
}

async function createDirectory() {
    const folderName = document.getElementById('folderName').value.trim();
    if (!folderName) {
        showMessage('Введите имя папки', 'warning');
        return;
    }

    let path = currentPath === '/' ? `/${folderName}` : `${currentPath}/${folderName}`;

    try {
        const response = await fetch('/api/mkdir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });

        if (response.ok) {
            showMessage(`Папка "${folderName}" создана`, 'success');
            document.getElementById('folderName').value = '';
            bootstrap.Modal.getInstance(document.getElementById('mkdirModal')).hide();
            await loadDirectory();
        } else {
            const data = await response.json();
            showMessage(data.error || 'Ошибка создания', 'danger');
        }
    } catch (error) {
        showMessage('Ошибка: ' + error.message, 'danger');
    }
}

async function renameItem(path) {
    const oldName = path.split('/').pop();
    const newName = prompt('Новое имя:', oldName);

    if (newName && newName !== oldName) {
        const pathParts = path.split('/');
        pathParts.pop();
        const newPath = pathParts.length ? pathParts.join('/') + '/' + newName : newName;

        try {
            const response = await fetch('/api/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_path: path, new_path: newPath })
            });

            if (response.ok) {
                showMessage('Переименовано', 'success');
                await loadDirectory();
            } else {
                const data = await response.json();
                showMessage(data.error || 'Ошибка переименования', 'danger');
            }
        } catch (error) {
            showMessage('Ошибка: ' + error.message, 'danger');
        }
    }
}

async function uploadFiles() {
    const fileInput = document.getElementById('fileInput');
    const files = fileInput.files;

    if (files.length === 0) return;

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('remote_path', currentPath);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                showMessage(`Загружено: ${file.name}`, 'success');
            } else {
                const data = await response.json();
                showMessage(`Ошибка загрузки ${file.name}: ${data.error}`, 'danger');
            }
        } catch (error) {
            showMessage(`Ошибка: ${file.name} - ${error.message}`, 'danger');
        }
    }

    fileInput.value = '';
    await loadDirectory();
}

// Обработчики событий
document.getElementById('connectBtn').addEventListener('click', connect);
document.getElementById('disconnectBtn').addEventListener('click', disconnect);
document.getElementById('refreshBtn').addEventListener('click', () => loadDirectory());
document.getElementById('backBtn').addEventListener('click', () => {
    if (currentPath && currentPath !== '/') {
        const parent = currentPath.split('/').slice(0, -1).join('/') || '/';
        loadDirectory(parent);
    }
});
document.getElementById('uploadBtn').addEventListener('click', () => {
    document.getElementById('fileInput').click();
});
document.getElementById('mkdirBtn').addEventListener('click', () => {
    new bootstrap.Modal(document.getElementById('mkdirModal')).show();
});
document.getElementById('confirmMkdirBtn').addEventListener('click', createDirectory);
document.getElementById('fileInput').addEventListener('change', uploadFiles);
document.getElementById('saveFileBtn').addEventListener('click', saveFile);
document.getElementById('closeEditorBtn').addEventListener('click', closeEditor);

// Закрытие редактора по Esc
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('editorContainer').style.display === 'flex') {
        closeEditor();
    }
});