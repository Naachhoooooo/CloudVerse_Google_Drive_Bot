import os
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent
LOGGER_DIR = PROJECT_ROOT / 'Logger'
UTILITIES_DIR = PROJECT_ROOT / 'Utilities'

class WebConfig:
    """Configuration class for web interface"""
    
    # Server Configuration
    WEBSOCKET = {
        'HOST': 'localhost',
        'PORT': 8765,
        'URL': 'ws://localhost:8765',
        'RECONNECT_ATTEMPTS': 5,
        'RECONNECT_DELAY': 2000,
        'UPDATE_INTERVAL': 2000
    }
    
    HTTP = {
        'HOST': 'localhost',
        'PORT': 8766,
        'BASE_URL': 'http://localhost:8766',
            'MAIN_PAGE': 'App.html',
    'FULL_URL': 'http://localhost:8766/App.html'
    }
    
    # File Paths
    PATHS = {
        'LOGO': str(UTILITIES_DIR / 'CloudVerse_Logo.jpg'),
        'FONT': str(UTILITIES_DIR / 'Helvetica.ttf'),
        'LOG_FILE': str(PROJECT_ROOT / 'bot.log'),
        'DATABASE': str(PROJECT_ROOT / 'Cloudverse.db'),
        'WEB_DIR': str(LOGGER_DIR)
    }
    
    # Branding
    BRANDING = {
        'NAME': 'CloudVerse',
        'VERSION': '1.0.0',
        'DESCRIPTION': 'Professional Cloud Storage Management Bot'
    }
    
    # UI Configuration
    UI = {
        'THEME': {
            'PRIMARY': '#000000',
            'SECONDARY': '#ffffff',
            'BACKGROUND': '#111111',
            'SURFACE': '#181818',
            'TEXT': '#ffffff',
            'ACCENT': '#ffffff'
        },
        'ANIMATION': {
            'DURATION': 600,
            'EASING': 'ease-out'
        },
        'LAYOUT': {
            'MAX_WIDTH': 1600,
            'SECTION_GAP': 32,
            'BORDER_RADIUS': 32
        }
    }
    
    # Features
    FEATURES = {
        'AUTO_RECONNECT': True,
        'REAL_TIME_UPDATES': True,
        'THEME_TOGGLE': True,
        'USER_MANAGEMENT': True,
        'LOG_STREAMING': True
    }
    
    @classmethod
    def get_websocket_url(cls):
        """Get WebSocket URL"""
        return f"ws://{cls.WEBSOCKET['HOST']}:{cls.WEBSOCKET['PORT']}"
    
    @classmethod
    def get_http_url(cls):
        """Get HTTP URL"""
        return f"http://{cls.HTTP['HOST']}:{cls.HTTP['PORT']}"
    
    @classmethod
    def get_main_page_url(cls):
        """Get main page URL"""
        return f"{cls.get_http_url()}/{cls.HTTP['MAIN_PAGE']}"
    
    @classmethod
    def validate_paths(cls):
        """Validate that all required files exist"""
        required_files = [
            cls.PATHS['LOGO'],
            cls.PATHS['FONT'],
            cls.PATHS['WEB_DIR']
        ]
        
        missing_files = []
        for file_path in required_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        return missing_files
    
    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("CloudVerse Web Interface Configuration:")
        print("=" * 50)
        print(f"WebSocket: {cls.get_websocket_url()}")
        print(f"HTTP Server: {cls.get_http_url()}")
        print(f"Main Page: {cls.get_main_page_url()}")
        print(f"Brand: {cls.BRANDING['NAME']} v{cls.BRANDING['VERSION']}")
        print(f"Project Root: {PROJECT_ROOT}")
        print(f"Logger Dir: {LOGGER_DIR}")
        print(f"Utilities Dir: {UTILITIES_DIR}")
        
        # Check file existence
        missing_files = cls.validate_paths()
        if missing_files:
            print("\n⚠️  Missing files:")
            for file_path in missing_files:
                print(f"   - {file_path}")
        else:
            print("\n✅ All required files found")

# Create global instance
config = WebConfig()

if __name__ == "__main__":
    config.print_config() 