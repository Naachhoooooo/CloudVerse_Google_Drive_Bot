// CloudVerse Dashboard Application Logic
// Professional dynamic logger frontend for CloudVerse Bot

// Configuration
const CONFIG = {
    WEBSOCKET: {
        HOST: 'localhost',
        PORT: 8765,
        URL: 'ws://localhost:8765',
        RECONNECT_ATTEMPTS: 5,
        RECONNECT_DELAY: 2000,
        UPDATE_INTERVAL: 2000
    },
    
    HTTP: {
        HOST: 'localhost',
        PORT: 8766,
        BASE_URL: 'http://localhost:8766',
        MAIN_PAGE: 'App.html',
        FULL_URL: 'http://localhost:8766/App.html'
    },
    
    BRANDING: {
        NAME: 'CloudVerse',
        VERSION: '1.0.0',
        DESCRIPTION: 'Professional Cloud Storage Management Bot'
    },
    
    FEATURES: {
        AUTO_RECONNECT: true,
        REAL_TIME_UPDATES: true,
        THEME_TOGGLE: true,
        USER_MANAGEMENT: true,
        LOG_STREAMING: true,
        VISUALIZATIONS: true,
        UPLOAD_MANAGER: true
    }
};

// Utility Functions
class Utils {
    static formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    static formatSpeed(bytesPerSecond) {
        return this.formatBytes(bytesPerSecond) + '/s';
    }

    static formatTime(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    static generateId() {
        return Math.random().toString(36).substr(2, 9);
    }
}

// WebSocket Management
class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = CONFIG.WEBSOCKET.RECONNECT_ATTEMPTS;
        this.reconnectDelay = CONFIG.WEBSOCKET.RECONNECT_DELAY;
        this.connect();
    }

    connect() {
        try {
            this.ws = new WebSocket(CONFIG.WEBSOCKET.URL);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected to', CONFIG.WEBSOCKET.URL);
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('Connected', 'success');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                this.updateConnectionStatus('Disconnected', 'error');
                this.attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('Connection error', 'error');
            };
            
        } catch (error) {
            console.error('Error creating WebSocket connection:', error);
            this.updateConnectionStatus('Connection failed', 'error');
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            this.updateConnectionStatus(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
            setTimeout(() => this.connect(), this.reconnectDelay);
        } else {
            this.updateConnectionStatus('Connection failed', 'error');
            console.error('Max reconnection attempts reached');
        }
    }

    manualReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            this.updateConnectionStatus(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
            setTimeout(() => this.connect(), this.reconnectDelay);
        } else {
            this.updateConnectionStatus('Connection failed', 'error');
            console.error('Max reconnection attempts reached');
        }
    }

    handleMessage(data) {
        if (data.type === 'dashboard') App.updateDashboard(data.metrics);
        if (data.type === 'logs') App.appendLog(data.log);
        if (data.type === 'users') App.updateUsers(data.users);
        if (data.type === 'uploads') App.updateUploads(data.uploads);
        if (data.type === 'upload_progress') App.updateUploadProgress(data.upload);
        if (data.type === 'status') this.showStatusMessage(data.message);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    updateConnectionStatus(status, type) {
        // Remove floating connection status button if it exists
        const statusEl = document.getElementById('connection-status');
        if (statusEl) {
            statusEl.remove();
        }
        // Update dashboard status indicator
        this.updateDashboardStatus(type);
    }

    updateDashboardStatus(type) {
        const statusIndicator = document.getElementById('status-indicator');
        const reconnectBtn = document.getElementById('reconnect-btn');
        if (!statusIndicator) return;
        
        const statusDot = statusIndicator.querySelector('.status-dot');
        const statusText = statusIndicator.querySelector('.status-text');
        
        // Remove all status classes
        statusIndicator.classList.remove('online', 'offline', 'connecting');
        
        // Hide reconnect button by default
        if (reconnectBtn) reconnectBtn.style.display = 'none';
        
        switch (type) {
            case 'success':
                statusIndicator.classList.add('online');
                statusText.textContent = 'Online';
                break;
            case 'warning':
                statusIndicator.classList.add('connecting');
                statusText.textContent = 'Connecting';
                break;
            case 'error':
                statusIndicator.classList.add('offline');
                statusText.textContent = 'Offline';
                if (reconnectBtn) reconnectBtn.style.display = 'flex';
                break;
            default:
                statusIndicator.classList.add('offline');
                statusText.textContent = 'Offline';
                if (reconnectBtn) reconnectBtn.style.display = 'flex';
        }
    }

    showStatusMessage(message) {
        const msgEl = document.createElement('div');
        msgEl.style.cssText = `
            position: fixed;
            top: 40px;
            right: 8px;
            padding: 6px 10px;
            background: #4ecdc4;
            color: #fff;
            border-radius: 4px;
            font-size: 11px;
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        `;
        msgEl.textContent = message;
        document.body.appendChild(msgEl);
        
        setTimeout(() => {
            msgEl.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => msgEl.remove(), 300);
        }, 3000);
    }
}

// Dashboard Visualizations
class DashboardVisualizations {
    static drawSpeedometer(canvasId, value, maxValue = 100) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        
        ctx.clearRect(0, 0, width, height);
        
        const percentage = Math.min(value / maxValue, 1);
        const startAngle = Math.PI;
        const endAngle = startAngle + (Math.PI * percentage);
        
        // Background arc
        ctx.beginPath();
        ctx.arc(width/2, height, width/2 - 2, startAngle, startAngle + Math.PI, false);
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 4;
        ctx.stroke();
        
        // Value arc
        ctx.beginPath();
        ctx.arc(width/2, height, width/2 - 2, startAngle, endAngle, false);
        ctx.strokeStyle = value > 80 ? '#ff6b6b' : value > 60 ? '#ffa726' : '#4ecdc4';
        ctx.lineWidth = 4;
        ctx.stroke();
        
        // Center circle
        ctx.beginPath();
        ctx.arc(width/2, height, 3, 0, 2 * Math.PI);
        ctx.fillStyle = '#fff';
        ctx.fill();
    }

    static updateDashboard(metrics) {
        // Update speedometer
        this.drawSpeedometer('cpu-canvas', metrics.cpu_usage, 100);
        document.getElementById('cpu').textContent = `${metrics.cpu_usage}%`;
        
        // Animate Memory usage
        DashboardVisualizations.drawSpeedometer('memory-canvas', metrics.memory_usage, 100);
        document.getElementById('memory').textContent = `${metrics.memory_usage}%`;
        
        // Update bandwidth circular progress
        const bandwidthFill = document.getElementById('bandwidth-fill');
        const bandwidthText = document.getElementById('bandwidth');
        const circumference = 2 * Math.PI * 25;
        const percentage = Math.min(metrics.bandwidth / 10, 1); // Assuming 10GB is max
        const offset = circumference - (percentage * circumference);
        bandwidthFill.style.strokeDasharray = `${circumference} ${circumference}`;
        bandwidthFill.style.strokeDashoffset = offset;
        bandwidthText.textContent = `${metrics.bandwidth.toFixed(1)} GB`;
        
        // Update storage progress bar
        const storageFill = document.getElementById('storage-fill');
        const storageText = document.getElementById('total_storage_used');
        const storagePercentage = Math.min((metrics.total_storage_used / 1000) * 100, 100); // Assuming 1TB is max
        storageFill.style.width = `${storagePercentage}%`;
        storageText.textContent = `${metrics.total_storage_used.toFixed(1)} GB`;
        
        // Update simple counters
        document.getElementById('uptime').textContent = Utils.formatTime(metrics.uptime);
        document.getElementById('users').textContent = metrics.users;
        document.getElementById('uploads_today').textContent = metrics.uploads_today;
    }
}

// Upload Manager
class UploadManager {
    constructor() {
        this.uploads = new Map();
        this.setupEventListeners();
    }

    setupEventListeners() {
        const refreshBtn = document.getElementById('refresh-uploads-btn');
        if (refreshBtn) {
            refreshBtn.onclick = () => this.refreshUploads();
        }
    }

    updateUploads(uploadsData) {
        this.uploads.clear();
        
        if (uploadsData && uploadsData.length > 0) {
            uploadsData.forEach(upload => {
                this.uploads.set(upload.id, upload);
            });
        }
        
        this.renderUploads();
        this.updateUploadCount();
    }

    updateUploadProgress(uploadData) {
        const existingUpload = this.uploads.get(uploadData.id);
        const wasPausedByAdmin = existingUpload && existingUpload.paused_by_admin;
        const isNowPausedByAdmin = uploadData.paused_by_admin;
        const wasPaused = existingUpload && existingUpload.status === 'paused';
        const isNowPaused = uploadData.status === 'paused';
        const wasUploading = existingUpload && existingUpload.status === 'uploading';
        const isNowUploading = uploadData.status === 'uploading';
        if (existingUpload) {
            Object.assign(existingUpload, uploadData);
        } else {
            this.uploads.set(uploadData.id, uploadData);
        }
        // Show notification if paused/resumed by admin
        if (!wasPausedByAdmin && isNowPausedByAdmin) {
            App.wsManager.showStatusMessage('Upload temporarily paused by admin');
        }
        if (wasPausedByAdmin && !isNowPausedByAdmin && isNowUploading) {
            App.wsManager.showStatusMessage('Upload resumed by admin');
        }
        // Show notification if paused/resumed (not just by admin)
        if (!wasPaused && isNowPaused) {
            App.wsManager.showStatusMessage('Upload paused');
        }
        if (wasPaused && isNowUploading) {
            App.wsManager.showStatusMessage('Upload resumed');
        }
        this.renderUploads();
        this.updateUploadCount();
    }

    renderUploads() {
        const uploadsList = document.getElementById('uploads-list');
        const noUploadsMessage = document.getElementById('no-uploads-message');
        
        if (!uploadsList || !noUploadsMessage) return;
        
        if (this.uploads.size === 0) {
            uploadsList.innerHTML = '';
            noUploadsMessage.style.display = 'flex';
            return;
        }
        
        noUploadsMessage.style.display = 'none';
        
        uploadsList.innerHTML = '';
        
        this.uploads.forEach(upload => {
            const uploadElement = this.createUploadElement(upload);
            uploadsList.appendChild(uploadElement);
        });
    }

    createUploadElement(upload) {
        const uploadDiv = document.createElement('div');
        uploadDiv.className = `upload-item ${upload.status}`;
        uploadDiv.id = `upload-${upload.id}`;
        
        const statusText = this.getStatusText(upload.status);
        const progressPercent = Math.round((upload.bytesUploaded / upload.totalBytes) * 100);
        const speed = upload.speed || 0;
        const eta = this.calculateETA(upload.bytesUploaded, upload.totalBytes, speed);
        const isAdmin = upload.is_admin;
        const isBanned = upload.is_banned;
        const pausedByAdmin = upload.paused_by_admin;
        
        // Add Mark for Ban button for non-admin, non-banned users
        let markBanBtn = '';
        if (!isAdmin && !isBanned) {
            markBanBtn = `<button class="mark-ban-btn" title="Mark for Ban">🚩 Mark for Ban</button>`;
        }
        uploadDiv.innerHTML = `
            <div class="upload-header">
                <div class="upload-info">
                    <div class="upload-filename" title="${upload.filename}">${upload.filename}
                        ${isAdmin ? '<span class="admin-upload-badge" title="Admin Upload">⭐ Admin</span>' : ''}
                    </div>
                    <div class="upload-details">
                        <div class="upload-detail">
                            <span>📁</span>
                            <span class="upload-size">${Utils.formatBytes(upload.totalBytes)}</span>
                        </div>
                        <div class="upload-detail">
                            <span>⚡</span>
                            <span class="upload-speed">${Utils.formatSpeed(speed)}</span>
                        </div>
                        <div class="upload-detail">
                            <span>👤</span>
                            <span class="upload-user">${upload.username || 'Unknown'}</span>
                        </div>
                        ${eta ? `<div class="upload-detail">
                            <span>⏱️</span>
                            <span>${eta}</span>
                        </div>` : ''}
                    </div>
                    ${pausedByAdmin ? `<div class="upload-paused-admin"><span class='paused-admin-icon' title='Paused by admin'>⏸️</span> <span>Temporarily paused by admin</span></div>` : ''}
                </div>
                <div class="upload-status ${upload.status}">${statusText}</div>
            </div>
            <div class="upload-progress-container">
                <div class="upload-progress-bar ${pausedByAdmin ? 'paused-admin-bar' : ''}">
                    <div class="upload-progress-fill" style="width: ${progressPercent}%"></div>
                </div>
                <div class="upload-progress-text">${progressPercent}% (${Utils.formatBytes(upload.bytesUploaded)} / ${Utils.formatBytes(upload.totalBytes)})</div>
            </div>
            <div class="upload-actions">
                ${markBanBtn}
                <button class="upload-action-btn" onclick="App.limitBandwidthUpload('${upload.id}')" title="Limit Bandwidth">🚦</button>
                ${upload.status !== 'paused' ? `<button class="upload-action-btn" onclick="App.pauseUpload('${upload.id}')" title="Pause">⏸️</button>` : ''}
                ${upload.status === 'paused' ? `<button class="upload-action-btn" onclick="App.resumeUpload('${upload.id}')" title="Resume">▶️</button>` : ''}
                ${!isAdmin ? this.renderBanDropdown(upload) : ''}
            </div>
        `;
        
        // Add event listener for Mark for Ban
        if (!isAdmin && !isBanned) {
            uploadDiv.querySelector('.mark-ban-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                this.send({ action: 'mark_for_ban', user_id: upload.user_id });
            });
        }
        return uploadDiv;
    }

    renderBanDropdown(upload) {
        const banOptions = [
            { label: '1 Hour', value: 1 },
            { label: '6 Hours', value: 6 },
            { label: '12 Hours', value: 12 },
            { label: '1 Day', value: 24 },
            { label: '10 Days', value: 240 },
            { label: '20 Days', value: 480 },
            { label: '1 Month', value: 720 },
            { label: 'Permanent', value: 'permanent' }
        ];
        const selectId = `ban-select-${upload.id}`;
        return `
            <select class="ban-dropdown" id="${selectId}" onchange="App.banUser('${upload.user_id || upload.telegram_id}', this.value)">
                <option value="">Ban...</option>
                ${banOptions.map(opt => `<option value="${opt.value}">${opt.label}</option>`).join('')}
            </select>
        `;
    }

    getStatusText(status) {
        const statusMap = {
            'uploading': 'UPLOADING',
            'completed': 'COMPLETED',
            'failed': 'FAILED',
            'paused': 'PAUSED',
            'cancelled': 'CANCELLED'
        };
        return statusMap[status] || status.toUpperCase();
    }

    calculateETA(bytesUploaded, totalBytes, speed) {
        if (speed <= 0 || bytesUploaded >= totalBytes) return null;
        
        const remainingBytes = totalBytes - bytesUploaded;
        const remainingSeconds = remainingBytes / speed;
        
        return Utils.formatTime(remainingSeconds);
    }

    updateUploadCount() {
        const countElement = document.getElementById('active-uploads-count');
        if (countElement) {
            const activeCount = Array.from(this.uploads.values()).filter(u => u.status === 'uploading').length;
            countElement.textContent = `${activeCount} Active Uploads`;
        }
    }

    refreshUploads() {
        if (App.wsManager.send({ action: 'get_uploads' })) {
            App.wsManager.showStatusMessage('Refreshing uploads...');
        }
    }

    // Upload actions
    pauseUpload(uploadId) {
        if (App.wsManager.send({ action: 'pause_upload', upload_id: uploadId })) {
            App.wsManager.showStatusMessage('Pausing upload...');
        }
    }

    resumeUpload(uploadId) {
        if (App.wsManager.send({ action: 'resume_upload', upload_id: uploadId })) {
            App.wsManager.showStatusMessage('Resuming upload...');
        }
    }

    cancelUpload(uploadId) {
        if (confirm('Are you sure you want to cancel this upload?')) {
            if (App.wsManager.send({ action: 'cancel_upload', upload_id: uploadId })) {
                App.wsManager.showStatusMessage('Cancelling upload...');
            }
        }
    }

    removeUpload(uploadId) {
        this.uploads.delete(uploadId);
        this.renderUploads();
        this.updateUploadCount();
    }
}

// User Management
class UserManager {
    static updateUsers(users) {
        const tbody = document.getElementById('users-tbody');
        tbody.innerHTML = '';
        
        users.forEach(user => {
            const tr = document.createElement('tr');
            
            let statusClass = 'status-offline';
            if (user.status === 'Online') {
                statusClass = 'status-online';
            } else if (user.status === 'Inactive') {
                statusClass = 'status-inactive';
            }
            
            tr.innerHTML = `
                <td>
                    <div class="user-name-container">
                        <div class="user-name">${user.name}</div>
                        ${user.is_admin ? '<span class="admin-tag">Admin</span>' : ''}
                    </div>
                </td>
                <td>${user.username} <button class="copy-btn" data-copy="${user.username}" title="Copy username">📋</button></td>
                <td>${user.telegram_id} <button class="copy-btn" data-copy="${user.telegram_id}" title="Copy ID">📋</button></td>
                <td><span class="${statusClass}">${user.status}</span></td>
                <td>${user.parallel_uploads}</td>
            `;
            
            tr.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.showToolkit(e.pageX, e.pageY, user);
            });
            
            tbody.appendChild(tr);
        });
    }

    static showToolkit(x, y, user) {
        const toolkit = document.getElementById('user-toolkit');
        let banDropdown = '';
        if (!user.is_admin) {
            const banOptions = [
                { label: '1 Hour', value: 1 },
                { label: '6 Hours', value: 6 },
                { label: '12 Hours', value: 12 },
                { label: '1 Day', value: 24 },
                { label: '10 Days', value: 240 },
                { label: '20 Days', value: 480 },
                { label: '1 Month', value: 720 },
                { label: 'Permanent', value: 'permanent' }
            ];
            banDropdown = `<select class='ban-dropdown' onchange="App.banUser('${user.telegram_id}', this.value)">
                <option value=''>Ban...</option>
                ${banOptions.map(opt => `<option value='${opt.value}'>${opt.label}</option>`).join('')}
            </select>`;
        }
        toolkit.innerHTML = `
            <div><b>${user.name}</b> (@${user.username})</div>
            <div>ID: ${user.telegram_id}</div>
            <button onclick="App.limitBandwidth('${user.telegram_id}')">Limit Bandwidth</button>
            <button onclick="App.tagUser('${user.telegram_id}')">Tag User</button>
            ${banDropdown}
        `;
        toolkit.style.left = x + 'px';
        toolkit.style.top = y + 'px';
        toolkit.classList.remove('hidden');
        toolkit.onmouseleave = () => toolkit.classList.add('hidden');
    }
}

// Log Management
class LogManager {
    static appendLog(log) {
        const logsDiv = document.getElementById('logs');
        logsDiv.textContent += log + '\n';
        logsDiv.scrollTop = logsDiv.scrollHeight;
    }
}

// Theme Management
class ThemeManager {
    static currentTheme = 'light';

    static init() {
        this.setTheme(this.currentTheme);
        this.setupThemeToggle();
    }

    static setTheme(theme) {
        this.currentTheme = theme;
        document.body.className = theme === 'light' ? 'light-theme' : '';
        
        const themeBtn = document.getElementById('theme-toggle-btn');
        themeBtn.textContent = theme === 'light' ? '🌙' : '☀️';
    }

    static setupThemeToggle() {
        const themeBtn = document.getElementById('theme-toggle-btn');
        themeBtn.onclick = () => {
            this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
            this.setTheme(this.currentTheme);
        };
    }
}

// Main Application Class
class App {
    constructor() {
        this.wsManager = new WebSocketManager();
        this.uploadManager = new UploadManager();
        this.init();
    }

    init() {
        this.setupEventListeners();
        ThemeManager.init();
        this.setupPlaceholderData();
    }

    setupEventListeners() {
        // Copy button functionality
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('copy-btn')) {
                const val = e.target.getAttribute('data-copy');
                navigator.clipboard.writeText(val);
                
                // Show copied feedback
                const originalText = e.target.textContent;
                e.target.textContent = '✓';
                e.target.style.background = 'var(--accent-success)';
                e.target.style.color = 'var(--text-primary)';
                e.target.style.borderColor = 'var(--accent-success)';
                
                setTimeout(() => { 
                    e.target.textContent = originalText;
                    e.target.style.background = '';
                    e.target.style.color = '';
                    e.target.style.borderColor = '';
                }, 1000);
            }
        });

        // User toolkit
        document.addEventListener('click', (e) => {
            const toolkit = document.getElementById('user-toolkit');
            if (!toolkit.contains(e.target)) toolkit.classList.add('hidden');
        });

        // Dashboard tabs
        this.setupDashboardTabs();

        // Control buttons
        document.getElementById('restart-btn').onclick = () => {
            if (this.wsManager.send({ action: 'restart_bot' })) {
                this.wsManager.showStatusMessage('Restart requested');
            } else {
                this.wsManager.showStatusMessage('Not connected to server');
            }
        };

        document.getElementById('shutdown-btn').onclick = () => {
            if (this.wsManager.send({ action: 'shutdown_bot' })) {
                this.wsManager.showStatusMessage('Shutdown requested');
            } else {
                this.wsManager.showStatusMessage('Not connected to server');
            }
        };

        // Reconnect button
        const reconnectBtn = document.getElementById('reconnect-btn');
        if (reconnectBtn) {
            reconnectBtn.addEventListener('click', () => {
                this.manualReconnect();
            });
        }

        // Theme toggle
        const themeToggleBtn = document.getElementById('theme-toggle-btn');
        if (themeToggleBtn) {
            themeToggleBtn.addEventListener('click', () => {
                ThemeManager.toggleTheme();
            });
        }

        // Refresh users button
        const refreshUsersBtn = document.getElementById('refresh-users-btn');
        if (refreshUsersBtn) {
            refreshUsersBtn.addEventListener('click', () => {
                this.refreshUsers();
            });
        }
    }

    setupDashboardTabs() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                
                // Remove active class from all buttons and contents
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked button and corresponding content
                button.classList.add('active');
                const targetContent = document.getElementById(targetTab + '-tab');
                if (targetContent) {
                    targetContent.classList.add('active');
                }
            });
        });
    }

    setupPlaceholderData() {
        if (location.hostname === 'localhost') {
            setTimeout(() => {
                DashboardVisualizations.updateDashboard({ 
                    cpu_usage: 12.5, 
                    memory_usage: 48.3, 
                    bandwidth: 1.2, 
                    uptime: 1234, 
                    users: 2, 
                    uploads_today: 10, 
                    total_storage_used: 50 
                });
                
                // Update performance metrics
                this.updatePerformanceMetrics();
                
                LogManager.appendLog('[INFO] Bot started.');
                UserManager.updateUsers([
                    { name: 'Alice', username: 'alice', telegram_id: '123456', status: 'Online', parallel_uploads: 2, is_admin: true },
                    { name: 'Charlie', username: 'charlie', telegram_id: '789012', status: 'Online', parallel_uploads: 1, is_admin: false },
                ]);
                
                // Add sample uploads
                this.uploadManager.updateUploads([
                    {
                        id: '1',
                        filename: 'sample_video.mp4',
                        totalBytes: 1024 * 1024 * 100, // 100MB
                        bytesUploaded: 1024 * 1024 * 45, // 45MB
                        speed: 1024 * 1024 * 2, // 2MB/s
                        status: 'uploading',
                        username: 'alice',
                        startTime: Date.now() - 30000,
                        is_admin: true
                    },
                    {
                        id: '2',
                        filename: 'document.pdf',
                        totalBytes: 1024 * 1024 * 5, // 5MB
                        bytesUploaded: 1024 * 1024 * 5, // 5MB
                        speed: 0,
                        status: 'completed',
                        username: 'bob',
                        startTime: Date.now() - 60000,
                        is_admin: false
                    }
                ]);
            }, 500);
        }
    }

    updatePerformanceMetrics() {
        // Update performance metrics with placeholder data
        const performanceData = {
            responseTime: '~45ms',
            activeConnections: 12,
            queueSize: 3,
            errorRate: '0.2%',
            uploadSpeed: '2.5 MB/s',
            downloadSpeed: '1.8 MB/s',
            avgUploadTime: '2.3s',
            successRate: '99.8%',
            peakLoad: '78%',
            cacheHitRate: '94%'
        };

        // Update performance displays
        document.getElementById('response-time').textContent = performanceData.responseTime;
        document.getElementById('active-connections').textContent = performanceData.activeConnections;
        document.getElementById('queue-size').textContent = performanceData.queueSize;
        document.getElementById('error-rate').textContent = performanceData.errorRate;
        document.getElementById('upload-speed').textContent = performanceData.uploadSpeed;
        document.getElementById('download-speed').textContent = performanceData.downloadSpeed;

        // Update performance analytics
        document.getElementById('avg-upload-time').textContent = performanceData.avgUploadTime;
        document.getElementById('success-rate').textContent = performanceData.successRate;
        document.getElementById('peak-load').textContent = performanceData.peakLoad;
        document.getElementById('cache-hit-rate').textContent = performanceData.cacheHitRate;
    }

    // WebSocket message handlers
    updateDashboard(metrics) {
        DashboardVisualizations.updateDashboard(metrics);
    }

    appendLog(log) {
        LogManager.appendLog(log);
    }

    updateUsers(users) {
        UserManager.updateUsers(users);
        // Update total users info
        const totalUsersInfo = document.getElementById('total-users-info');
        if (totalUsersInfo) {
            const userCount = users.length;
            totalUsersInfo.textContent = `Currently ${userCount} User${userCount === 1 ? '' : 's'} Online`;
        }
    }

    updateUploads(uploads) {
        this.uploadManager.updateUploads(uploads);
    }

    updateUploadProgress(upload) {
        this.uploadManager.updateUploadProgress(upload);
    }

    // Upload actions
    pauseUpload(uploadId) {
        this.uploadManager.pauseUpload(uploadId);
    }

    resumeUpload(uploadId) {
        this.uploadManager.resumeUpload(uploadId);
    }

    cancelUpload(uploadId) {
        this.uploadManager.cancelUpload(uploadId);
    }

    removeUpload(uploadId) {
        this.uploadManager.removeUpload(uploadId);
    }

    limitBandwidthUpload(uploadId) {
        // Find the upload and get the user id
        const upload = this.uploadManager.uploads.get(uploadId);
        if (upload && upload.user_id) {
            if (this.wsManager.send({ action: 'limit_bandwidth', user_id: upload.user_id })) {
                this.wsManager.showStatusMessage(`Bandwidth limit requested for user ${upload.user_id}`);
            } else {
                this.wsManager.showStatusMessage('Not connected to server');
            }
        } else {
            this.wsManager.showStatusMessage('User ID not found for this upload');
        }
    }

    // User actions
    limitBandwidth(id) {
        if (this.wsManager.send({ action: 'limit_bandwidth', user_id: id })) {
            this.wsManager.showStatusMessage(`Bandwidth limit requested for user ${id}`);
        } else {
            this.wsManager.showStatusMessage('Not connected to server');
        }
        document.getElementById('user-toolkit').classList.add('hidden');
    }

    tagUser(id) {
        if (this.wsManager.send({ action: 'tag_user', user_id: id })) {
            this.wsManager.showStatusMessage(`User ${id} tagged`);
        } else {
            this.wsManager.showStatusMessage('Not connected to server');
        }
        document.getElementById('user-toolkit').classList.add('hidden');
    }

    banUser(userId, duration) {
        if (!duration) return;
        if (window.App && App.wsManager) {
            App.wsManager.send({ action: 'ban_user', user_id: userId, duration });
            App.wsManager.showStatusMessage('Ban request sent');
        }
    }

    manualReconnect() {
        const reconnectBtn = document.getElementById('reconnect-btn');
        if (reconnectBtn) {
            reconnectBtn.classList.add('spinning');
        }
        
        this.wsManager.manualReconnect();
        
        // Reset button after 3 seconds
        setTimeout(() => {
            if (reconnectBtn) {
                reconnectBtn.classList.remove('spinning');
            }
        }, 3000);
    }
}

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.App = new App();
}); 