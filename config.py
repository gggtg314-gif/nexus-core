import os
from urllib.parse import quote_plus


class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # =========================================================
    # MySQL / TiDB Configuration
    # =========================================================

    MYSQL_HOST = os.environ.get(
        'MYSQL_HOST',
        'localhost'
    )

    MYSQL_PORT = int(os.environ.get(
        'MYSQL_PORT',
        '3306'
    ))

    MYSQL_USER = os.environ.get(
        'MYSQL_USER',
        'root'
    )

    MYSQL_PASSWORD = os.environ.get(
        'MYSQL_PASSWORD',
        ''
    )

    MYSQL_DATABASE = os.environ.get(
        'MYSQL_DATABASE',
        'predictive_maintenance'
    )

    # =========================================================
    # Database SSL Configuration
    # =========================================================

    DB_SSL = os.environ.get(
        'DB_SSL',
        'false'
    ).lower() in ('true', '1', 'yes')

    CA_PATH = os.environ.get(
        'CA_PATH',
        os.path.join(BASE_DIR, 'isrgrootx1.pem')
    )

    # =========================================================
    # SQLAlchemy Connection String
    # =========================================================

    encoded_user = quote_plus(MYSQL_USER)
    encoded_password = quote_plus(MYSQL_PASSWORD)

    if DB_SSL:
        encoded_ca_path = quote_plus(CA_PATH)

        SQLALCHEMY_DATABASE_URI = (
            f'mysql+pymysql://'
            f'{encoded_user}:{encoded_password}'
            f'@{MYSQL_HOST}:{MYSQL_PORT}'
            f'/{MYSQL_DATABASE}'
            f'?ssl_ca={encoded_ca_path}'
            f'&ssl_verify_cert=true'
            f'&ssl_verify_identity=true'
        )
    else:
        SQLALCHEMY_DATABASE_URI = (
            f'mysql+pymysql://'
            f'{encoded_user}:{encoded_password}'
            f'@{MYSQL_HOST}:{MYSQL_PORT}'
            f'/{MYSQL_DATABASE}'
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # =========================================================
    # Flask Security
    # =========================================================

    SECRET_KEY = os.environ.get(
        'SECRET_KEY',
        'dev-secret-key-change-this'
    )

    # =========================================================
    # Application Settings
    # =========================================================

    HOST = '0.0.0.0'

    PORT = int(os.environ.get(
        'PORT',
        '5000'
    ))

    DEBUG = os.environ.get(
        'DEBUG',
        'true'
    ).lower() in ('true', '1', 'yes')

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

    SECRET_KEY = os.environ.get(
        'SECRET_KEY',
        'prod-secret-key-change-this'
    )


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}