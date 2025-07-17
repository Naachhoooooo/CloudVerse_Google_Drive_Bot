// CloudVerse Web Interface Configuration
// Centralized configuration for all URLs, ports, and mappings

const CONFIG = {
    // Server Configuration
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
    
    // File Paths
    PATHS: {
        LOGO: '../Utilities/CloudVerse_Logo.jpg',
        FONT: '../Utilities/Helvetica.ttf',
        LOG_FILE: '../bot.log',
        DATABASE: '../users.db'
    },
    
    // Branding
    BRANDING: {
        NAME: 'CloudVerse',
        VERSION: '1.0.0',
        DESCRIPTION: 'Professional Cloud Storage Management Bot'
    },
    
    // UI Configuration
    UI: {
        THEME: {
            PRIMARY: '#000000',
            SECONDARY: '#ffffff',
            BACKGROUND: '#111111',
            SURFACE: '#181818',
            TEXT: '#ffffff',
            ACCENT: '#ffffff'
        },
        ANIMATION: {
            DURATION: 600,
            EASING: 'ease-out'
        },
        LAYOUT: {
            MAX_WIDTH: 1600,
            SECTION_GAP: 32,
            BORDER_RADIUS: 32
        }
    },
    
    // Features
    FEATURES: {
        AUTO_RECONNECT: true,
        REAL_TIME_UPDATES: true,
        THEME_TOGGLE: true,
        USER_MANAGEMENT: true,
        LOG_STREAMING: true
    }
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
} else {
    window.CONFIG = CONFIG;
} 