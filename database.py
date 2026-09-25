import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()

def init_db(app):
    """Initialize database with MySQL"""
    db.init_app(app)
    
    with app.app_context():
        try:
            # Check pymysql
            try:
                import pymysql
                logger.info("✅ pymysql is installed")
            except ImportError:
                logger.error("❌ pymysql is not installed! Run: pip install pymysql")
                return
            
            # Test connection
            engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✅ Connected to MySQL successfully!")
                
                # Check database
                result = conn.execute(text("SELECT DATABASE()"))
                db_name = result.scalar()
                logger.info(f"✅ Using database: {db_name}")
                
                # Create tables
                db.create_all()
                logger.info("✅ Tables created successfully!")
                
                # Create default admin account if not exists
                from models import Account
                admin = Account.query.filter_by(username='admin').first()
                if not admin:
                    admin = Account(
                        username='admin',
                        email='admin@nexus.com',
                        role='admin'
                    )
                    admin.set_password('admin123')
                    db.session.add(admin)
                    db.session.commit()
                    logger.info("✅ Default admin account created (username: admin, password: admin123)")
                else:
                    logger.info("✅ Admin account already exists")
                    
        except Exception as e:
            logger.error(f"❌ Database error: {str(e)}")
            logger.info("\n💡 Troubleshooting:")
            logger.info("1. Check MySQL is running")
            logger.info("2. Check username/password in config.py")
            logger.info("3. Check database 'predictive_maintenance' exists")
            logger.info("4. Run: pip install pymysql")

def get_db_connection():
    """Get a raw database connection"""
    from sqlalchemy import create_engine
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    return engine.connect()

def execute_raw_query(query, params=None):
    """Execute a raw SQL query"""
    from sqlalchemy import text
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    
    with engine.connect() as conn:
        try:
            if params:
                result = conn.execute(text(query), params)
            else:
                result = conn.execute(text(query))
            
            if query.strip().upper().startswith('SELECT'):
                return result.fetchall()
            else:
                conn.commit()
                return True
        except Exception as e:
            raise e