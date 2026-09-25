import os

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # MySQL Configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'predictive_maintenance')
      
    
    # MySQL Connection String
    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DATABASE}'
    )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask Secret Key for sessions
    SECRET_KEY = 'your-secret-key-here-change-in-production-nexus2024'
    
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = True
    AGENT_INTERVAL = 5
    OFFLINE_THRESHOLD = 20
    CPU_WARNING = 70
    CPU_CRITICAL = 90
    RAM_WARNING = 80
    RAM_CRITICAL = 90
    DISK_WARNING = 85
    DISK_CRITICAL = 95
    DASHBOARD_REFRESH = 5000

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'prod-secret-key-change-this')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}