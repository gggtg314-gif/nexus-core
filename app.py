from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime, timedelta
from config import Config, config
from database import db, init_db
from models import (
    Computer,
    History,
    Account,
    Ticket,
    TicketComment,
    TicketActivity,
    MaintenancePlanner,
    Inventory
)
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import os
import traceback
from sqlalchemy import text
import functools
import random
import qrcode
import io
import base64
import json
import time

from google import genai
from google.genai import types


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============================================================
# NUXES AI - GEMINI CONFIGURATION
# ============================================================

NEXUS_AI_MODEL = 'gemini-3.5-flash-lite'

gemini_api_key = os.getenv('GEMINI_API_KEY')
gemini_client = None

if gemini_api_key:
    try:
        gemini_client = genai.Client(
            api_key=gemini_api_key
        )
        logger.info(
            f'Nuxes AI initialized with {NEXUS_AI_MODEL}'
        )
    except Exception as e:
        logger.error(
            f'Failed to initialize Gemini client: {e}'
        )
else:
    logger.warning(
        'GEMINI_API_KEY not configured. Nuxes AI is disabled.'
    )


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
app.config.from_object(config['default'])

# Initialize database
init_db(app)


# ============================================================
# SYSTEM SETTINGS
# ============================================================

def get_system_settings():
    """
    Load global system settings from MySQL.
    """

    defaults = {
        'refresh_interval': 5,
        'offline_threshold': 20,

        'cpu_warning': 70,
        'cpu_critical': 90,

        'ram_warning': 80,
        'ram_critical': 90,

        'disk_warning': 85,
        'disk_critical': 95
    }

    try:

        result = db.session.execute(
            text("""
                SELECT
                    refresh_interval,
                    offline_threshold,
                    cpu_warning,
                    cpu_critical,
                    ram_warning,
                    ram_critical,
                    disk_warning,
                    disk_critical
                FROM system_settings
                WHERE id = 1
                LIMIT 1
            """)
        ).mappings().first()

        if result:

            settings_data = dict(result)

            for key in settings_data:

                if key in (
                    'refresh_interval',
                    'offline_threshold'
                ):

                    settings_data[key] = int(
                        settings_data[key]
                    )

                else:

                    settings_data[key] = float(
                        settings_data[key]
                    )

            return settings_data

    except Exception as e:

        logger.error(
            f"Error loading system settings: {e}"
        )

        db.session.rollback()

    return defaults


# ============================================================
# LOGIN REQUIRED DECORATOR
# ============================================================

def login_required(f):

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):

        if 'account_id' not in session:

            flash(
                'Please log in to access this page.',
                'warning'
            )

            return redirect(
                url_for('login')
            )

        try:

            account = db.session.get(
                Account,
                session['account_id']
            )

            if not account:

                session.clear()

                flash(
                    'Session expired. Please login again.',
                    'warning'
                )

                return redirect(
                    url_for('login')
                )

        except Exception as e:

            logger.error(
                f"Database error in login check: {e}"
            )

            session.clear()

            flash(
                'Unable to verify your session.',
                'danger'
            )

            return redirect(
                url_for('login')
            )

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# ADMIN REQUIRED DECORATOR
# ============================================================

def admin_required(f):
    """
    Allow access only to logged-in admin users.
    Role is always verified from the database.
    """

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):

        if 'account_id' not in session:

            flash(
                'Please log in to access this page.',
                'warning'
            )

            return redirect(
                url_for('login')
            )

        try:

            account = db.session.get(
                Account,
                session['account_id']
            )

            if not account:

                session.clear()

                flash(
                    'Session expired. Please login again.',
                    'warning'
                )

                return redirect(
                    url_for('login')
                )

            # IMPORTANT:
            # Never trust role from browser/session.
            # Always check current role from database.
            current_role = (
                account.role or 'user'
            ).strip().lower()

            if current_role != 'admin':

                flash(
                    'Access denied. Admin privileges required.',
                    'danger'
                )

                if request.is_json:

                    return jsonify({
                        'success': False,
                        'error': (
                            'Access denied. '
                            'Admin privileges required.'
                        )
                    }), 403

                return redirect(
                    url_for('profile')
                )

            # Keep session role synchronized
            session['role'] = current_role

        except Exception as e:

            logger.error(
                f"Admin permission check error: {e}"
            )

            flash(
                'Unable to verify account permissions.',
                'danger'
            )

            if request.is_json:

                return jsonify({
                    'success': False,
                    'error': 'Unable to verify permissions'
                }), 500

            return redirect(
                url_for('profile')
            )

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# GET CURRENT ACCOUNT
# ============================================================

def get_current_account():

    try:

        if 'account_id' in session:

            return db.session.get(
                Account,
                session['account_id']
            )

    except Exception as e:

        logger.error(
            f"Error getting current account: {e}"
        )

    return None


# ============================================================
# BEFORE REQUEST
# ============================================================

@app.before_request
def before_request():

    public_routes = [
    'login',
    'register',
    'forgot_password',
    'forgot_change_password',
    'static',
    'update_computer',
    'update_iot_data'
    ]

    if request.endpoint in public_routes:
        return None

    if 'account_id' not in session:

        flash(
            'Please log in to access this page.',
            'warning'
        )

        return redirect(
            url_for('login')
        )

    return None


# ============================================================
# MAINTENANCE PLANNER
# ============================================================

@app.route(
    '/api/maintenance/planner',
    methods=['GET']
)
@login_required
def get_maintenance_planner():

    try:

        tasks = (
            MaintenancePlanner.query
            .order_by(
                MaintenancePlanner.id.desc()
            )
            .all()
        )

        return jsonify({
            'success': True,
            'data': [
                task.to_dict()
                for task in tasks
            ]
        }), 200

    except Exception as e:

        logger.error(
            f"Error loading maintenance planner: {e}"
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route(
    '/api/maintenance/planner',
    methods=['POST']
)
@admin_required
def add_maintenance_planner():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        system_name = str(
            data.get('system_name', '')
        ).strip()

        component = str(
            data.get('component', '')
        ).strip()

        task = str(
            data.get('task', '')
        ).strip()

        if (
            not system_name
            or not component
            or not task
        ):

            return jsonify({
                'success': False,
                'error': (
                    'System name, component '
                    'and task are required'
                )
            }), 400

        scheduled_date = None

        if data.get('scheduled_date'):

            scheduled_date = datetime.strptime(
                data['scheduled_date'],
                '%Y-%m-%d'
            ).date()

        replacement_date = None

        if data.get('replacement_date'):

            replacement_date = datetime.strptime(
                data['replacement_date'],
                '%Y-%m-%d'
            ).date()

        task_obj = MaintenancePlanner(
            computer_id=(
                data.get('computer_id')
                or None
            ),

            system_name=system_name,

            component=component,

            task=task,

            scheduled_date=scheduled_date,

            priority=data.get(
                'priority',
                'Medium'
            ),

            estimated_cost=float(
                data.get(
                    'estimated_cost',
                    0
                ) or 0
            ),

            replacement_date=replacement_date,

            status=data.get(
                'status',
                'Scheduled'
            ),

            notes=data.get(
                'notes',
                ''
            )
        )

        db.session.add(task_obj)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Maintenance task added successfully'
            ),
            'data': task_obj.to_dict()
        }), 201

    except ValueError:

        db.session.rollback()

        return jsonify({
            'success': False,
            'error': 'Invalid date or cost format'
        }), 400

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error adding maintenance task: {e}"
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route(
    '/api/maintenance/planner/<int:task_id>',
    methods=['DELETE']
)
@admin_required
def delete_maintenance_planner(task_id):

    try:

        task = db.session.get(
            MaintenancePlanner,
            task_id
        )

        if not task:

            return jsonify({
                'success': False,
                'error': 'Maintenance task not found'
            }), 404

        db.session.delete(task)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Maintenance task deleted successfully'
            )
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error deleting maintenance task: {e}"
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route(
    '/api/maintenance/planner/clear',
    methods=['DELETE']
)
@admin_required
def clear_maintenance_planner():

    try:

        deleted = MaintenancePlanner.query.delete(
            synchronize_session=False
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'All maintenance tasks cleared',
            'deleted': deleted
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error clearing maintenance planner: {e}"
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# AUTH - LOGIN
# ============================================================

@app.route(
    '/login',
    methods=['GET', 'POST']
)
def login():

    if 'account_id' in session:

        return redirect(
            url_for('index')
        )

    if request.method == 'POST':

        username = request.form.get(
            'username',
            ''
        ).strip()

        password = request.form.get(
            'password',
            ''
        )

        remember = (
            request.form.get(
                'remember_me'
            ) == 'on'
        )

        if not username or not password:

            flash(
                'Please enter both username and password',
                'danger'
            )

            return render_template(
                'login.html'
            )

        try:

            # IMPORTANT:
            # Role is NOT received from login form.
            account = Account.query.filter_by(
                username=username
            ).first()

            if (
                account
                and account.check_password(password)
            ):

                # Clear old session data
                session.clear()

                # Account ID comes from DB
                session['account_id'] = account.id

                # Role comes ONLY from DB
                session['role'] = (
                    account.role or 'user'
                ).strip().lower()

                if remember:

                    session.permanent = True

                account.last_login = datetime.utcnow()

                db.session.commit()

                flash(
                    f'Welcome back, {account.username}!',
                    'success'
                )

                return redirect(
                    url_for('index')
                )

            flash(
                'Invalid username or password',
                'danger'
            )

        except Exception as e:

            logger.error(
                f"Login error: {e}"
            )

            logger.error(
                traceback.format_exc()
            )

            db.session.rollback()

            flash(
                'Login error. Please try again.',
                'danger'
            )

    return render_template(
        'login.html'
    )


# ============================================================
# AUTH - REGISTER
# ============================================================

@app.route(
    '/register',
    methods=['GET', 'POST']
)
def register():

    if 'account_id' in session:

        return redirect(
            url_for('index')
        )

    if request.method == 'POST':

        username = request.form.get(
            'username',
            ''
        ).strip()

        email = request.form.get(
            'email',
            ''
        ).strip()

        password = request.form.get(
            'password',
            ''
        )

        password_confirm = request.form.get(
            'password_confirm',
            ''
        )

        security_question = request.form.get(
            'security_question',
            ''
        ).strip()

        security_answer = request.form.get(
            'security_answer',
            ''
        ).strip()

        if (
            not username
            or not email
            or not password
            or not password_confirm
            or not security_question
            or not security_answer
        ):

            flash(
                'All fields are required',
                'danger'
            )

            return render_template(
                'register.html'
            )

        if password != password_confirm:

            flash(
                'Passwords do not match',
                'danger'
            )

            return render_template(
                'register.html'
            )

        if len(password) < 6:

            flash(
                'Password must be at least 6 characters',
                'danger'
            )

            return render_template(
                'register.html'
            )

        if len(security_answer) < 2:

            flash(
                'Security answer must be at least 2 characters',
                'danger'
            )

            return render_template(
                'register.html'
            )

        try:

            if Account.query.filter_by(
                username=username
            ).first():

                flash(
                    'Username already taken',
                    'danger'
                )

                return render_template(
                    'register.html'
                )

            if Account.query.filter_by(
                email=email
            ).first():

                flash(
                    'Email already registered',
                    'danger'
                )

                return render_template(
                    'register.html'
                )

            # IMPORTANT:
            # New registration can NEVER select admin.
            account = Account(
                username=username,
                email=email,
                role='user',

                security_question=(
                    security_question
                ),

                security_answer_hash=security_answer.strip().lower()
                    
                
            )

            account.set_password(
                password
            )

            db.session.add(account)

            db.session.commit()

            logger.info(
                f"New account registered: {username}"
            )

            flash(
                'Account created successfully! Please login.',
                'success'
            )

            return redirect(
                url_for('login')
            )

        except Exception as e:

            logger.error(
                f"Registration error: {e}"
            )

            logger.error(
                traceback.format_exc()
            )

            db.session.rollback()

            flash(
                'Registration error. Please try again.',
                'danger'
            )

    return render_template(
        'register.html'
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

# ============================================================
# FORGOT PASSWORD
# ============================================================

@app.route(
    '/forgot-password',
    methods=['GET', 'POST']
)
def forgot_password():

    if 'account_id' in session:
        return redirect(
            url_for('index')
        )

    if request.method == 'GET':
        return render_template(
            'forgot_password.html'
        )

    username_or_email = request.form.get(
        'username_or_email',
        ''
    ).strip()

    security_answer = request.form.get(
        'security_answer',
        ''
    ).strip().lower()

    if not username_or_email:
        flash(
            'Please enter your username or email.',
            'danger'
        )

        return render_template(
            'forgot_password.html'
        )

    try:

        account = Account.query.filter(
            (Account.username == username_or_email) |
            (Account.email == username_or_email)
        ).first()

        if not account:

            flash(
                'Account not found.',
                'danger'
            )

            return render_template(
                'forgot_password.html',
                username_or_email=username_or_email
            )

        if not account.security_question:

            flash(
                'Security question is not configured for this account.',
                'danger'
            )

            return render_template(
                'forgot_password.html',
                username_or_email=username_or_email
            )

        if not account.security_answer_hash:

            flash(
                'Security answer is not configured for this account.',
                'danger'
            )

            return render_template(
                'forgot_password.html',
                username_or_email=username_or_email
            )

        # ====================================================
        # FIRST STEP
        # Show security question
        # ====================================================

        if not security_answer:

            return render_template(
                'forgot_password.html',
                username_or_email=username_or_email,
                security_question=account.security_question,
                show_question=True
            )

        # ====================================================
        # SECOND STEP
        # Verify security answer
        # ====================================================

        answer_correct = (
         account.security_answer_hash.strip().lower()
         == security_answer.strip().lower()
        )

        if not answer_correct:

            flash(
                'Incorrect security answer.',
                'danger'
            )

            return render_template(
                'forgot_password.html',
                username_or_email=username_or_email,
                security_question=account.security_question,
                show_question=True
            )

        # ====================================================
        # SECURITY ANSWER CORRECT
        # Allow password reset
        # ====================================================

        session.pop(
            'reset_account_id',
            None
        )

        session['reset_account_id'] = account.id

        return redirect(
            url_for('forgot_change_password')
        )

    except Exception as e:

        logger.error(
            f"Forgot password error: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        db.session.rollback()

        flash(
            'Something went wrong. Please try again.',
            'danger'
        )

        return render_template(
            'forgot_password.html',
            username_or_email=username_or_email
        )

# ============================================================
# RESET PASSWORD
# ============================================================

# ============================================================
# FORGOT PASSWORD - CHANGE PASSWORD
# ============================================================

@app.route(
    '/change-password',
    methods=['GET', 'POST']
)
def forgot_change_password():

    reset_account_id = session.get(
        'reset_account_id'
    )

    if not reset_account_id:

        flash(
            'Please start from Forgot Password.',
            'warning'
        )

        return redirect(
            url_for('forgot_password')
        )

    try:

        account = db.session.get(
            Account,
            reset_account_id
        )

        if not account:

            session.pop(
                'reset_account_id',
                None
            )

            flash(
                'Invalid password reset session.',
                'danger'
            )

            return redirect(
                url_for('forgot_password')
            )

        # ====================================================
        # SHOW CHANGE PASSWORD PAGE
        # ====================================================

        if request.method == 'GET':

            return render_template(
                'change_password.html'
            )

        # ====================================================
        # GET NEW PASSWORD
        # ====================================================

        new_password = request.form.get(
            'new_password',
            ''
        )

        confirm_password = request.form.get(
            'confirm_password',
            ''
        )

        if not new_password:

            flash(
                'Please enter a new password.',
                'warning'
            )

            return render_template(
                'change_password.html'
            )

        if len(new_password) < 6:

            flash(
                'Password must be at least 6 characters.',
                'warning'
            )

            return render_template(
                'change_password.html'
            )

        if new_password != confirm_password:

            flash(
                'Passwords do not match.',
                'danger'
            )

            return render_template(
                'change_password.html'
            )

        # ====================================================
        # UPDATE PASSWORD
        # ====================================================

        account.set_password(
            new_password
        )

        db.session.commit()

        # Remove reset permission
        session.pop(
            'reset_account_id',
            None
        )

        flash(
            'Password changed successfully. Please login.',
            'success'
        )

        return redirect(
            url_for('login')
        )

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Forgot password change error: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        flash(
            'Password change failed. Please try again.',
            'danger'
        )

        return redirect(
            url_for('forgot_password')
        )

# ============================================================
# LOGOUT
# ============================================================

@app.route('/logout')
def logout():

    if 'account_id' in session:

        account = db.session.get(
            Account,
            session['account_id']
        )

        if account:

            flash(
                f'Goodbye, {account.username}!',
                'info'
            )

    session.clear()

    return redirect(
        url_for('login')
    )


# ============================================================
# PROFILE
# ============================================================

@app.route('/profile')
@login_required
def profile():

    account = get_current_account()

    users = (
        Account.query
        .order_by(Account.id.asc())
        .all()
        if (
            account
            and (
                account.role or 'user'
            ).lower() == 'admin'
        )
        else []
    )

    return render_template(
        'profile.html',
        account=account,
        users=users
    )


# ============================================================
# INVENTORY PAGE
# ============================================================

@app.route('/inventory')
@login_required
def inventory():

    return render_template(
        'inventory.html'
    )


# ============================================================
# USER ROLE API
# ============================================================

@app.route(
    '/api/users/<int:user_id>/role',
    methods=['POST']
)
@admin_required
def update_user_role(user_id):

    try:

        current_account = get_current_account()

        target = db.session.get(
            Account,
            user_id
        )

        if not current_account:

            return jsonify({
                'success': False,
                'error': 'Admin account not found'
            }), 401

        if not target:

            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        data = request.get_json(
            silent=True
        ) or {}

        new_role = str(
            data.get('role', '')
        ).strip().lower()

        if new_role not in (
            'admin',
            'user'
        ):

            return jsonify({
                'success': False,
                'error': (
                    'Role must be either admin or user'
                )
            }), 400

        if (
            target.id == current_account.id
            and new_role != 'admin'
        ):

            return jsonify({
                'success': False,
                'error': (
                    'You cannot remove your own admin role'
                )
            }), 400

        if (
            target.role
            and target.role.lower() == 'admin'
            and new_role == 'user'
        ):

            admin_count = Account.query.filter(
                db.func.lower(
                    Account.role
                ) == 'admin'
            ).count()

            if admin_count <= 1:

                return jsonify({
                    'success': False,
                    'error': (
                        'At least one admin account '
                        'must remain'
                    )
                }), 400

        target.role = new_role

        db.session.commit()

        logger.info(
            f"Role changed: {target.username} -> "
            f"{new_role} by admin "
            f"{current_account.username}"
        )

        return jsonify({
            'success': True,
            'message': (
                f'{target.username} role changed to '
                f'{new_role}'
            ),
            'user': {
                'id': target.id,
                'username': target.username,
                'email': target.email,
                'role': new_role
            }
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error changing user role: {e}"
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# CHANGE OWN PASSWORD
# ============================================================

@app.route(
    '/api/change-password',
    methods=['POST']
)
@login_required
def change_password():

    try:

        account = get_current_account()

        if not account:

            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 401

        data = request.get_json(
            silent=True
        ) or {}

        current_password = data.get(
            'current_password',
            ''
        )

        new_password = data.get(
            'new_password',
            ''
        )

        confirm_password = data.get(
            'confirm_password',
            ''
        )

        if (
            not current_password
            or not new_password
            or not confirm_password
        ):

            return jsonify({
                'success': False,
                'error': (
                    'All password fields are required'
                )
            }), 400

        if not account.check_password(
            current_password
        ):

            return jsonify({
                'success': False,
                'error': (
                    'Current password is incorrect'
                )
            }), 400

        if len(new_password) < 6:

            return jsonify({
                'success': False,
                'error': (
                    'New password must be '
                    'at least 6 characters'
                )
            }), 400

        if new_password != confirm_password:

            return jsonify({
                'success': False,
                'error': (
                    'New passwords do not match'
                )
            }), 400

        if new_password == current_password:

            return jsonify({
                'success': False,
                'error': (
                    'New password must be different '
                    'from the current password'
                )
            }), 400

        account.set_password(
            new_password
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Password changed successfully'
            )
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error changing password: {e}"
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# MAIN PAGES
# ============================================================

@app.route('/')
@admin_required
def index():

    return render_template(
        'index.html'
    )


@app.route('/about')
@login_required
def about():

    return render_template(
        'about.html'
    )


@app.route('/settings')
@login_required
def settings():

    return render_template(
        'settings.html'
    )


@app.route('/systems')
@login_required
def systems():

    return render_template(
        'systems.html'
    )


# ============================================================
# SETTINGS API - GET
# ============================================================

@app.route(
    '/api/settings',
    methods=['GET']
)
@login_required
def get_settings_api():

    try:

        settings_data = get_system_settings()

        return jsonify({
            'success': True,
            'settings': settings_data
        }), 200

    except Exception as e:

        logger.error(
            f"Error getting settings: {e}"
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# SETTINGS API - UPDATE
# ============================================================

@app.route(
    '/api/settings',
    methods=['POST']
)
@admin_required
def update_settings_api():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        refresh_interval = int(
            data.get(
                'refresh_interval',
                5
            )
        )

        offline_threshold = int(
            data.get(
                'offline_threshold',
                20
            )
        )

        cpu_warning = float(
            data.get(
                'cpu_warning',
                70
            )
        )

        cpu_critical = float(
            data.get(
                'cpu_critical',
                90
            )
        )

        ram_warning = float(
            data.get(
                'ram_warning',
                80
            )
        )

        ram_critical = float(
            data.get(
                'ram_critical',
                90
            )
        )

        disk_warning = float(
            data.get(
                'disk_warning',
                85
            )
        )

        disk_critical = float(
            data.get(
                'disk_critical',
                95
            )
        )

        if not 1 <= refresh_interval <= 60:

            return jsonify({
                'success': False,
                'error': (
                    'Refresh interval must be '
                    'between 1 and 60 seconds'
                )
            }), 400

        if not 5 <= offline_threshold <= 300:

            return jsonify({
                'success': False,
                'error': (
                    'Offline threshold must be '
                    'between 5 and 300 seconds'
                )
            }), 400

        if not 0 <= cpu_warning <= 100:

            return jsonify({
                'success': False,
                'error': (
                    'CPU warning must be '
                    'between 0 and 100'
                )
            }), 400

        if not 0 <= cpu_critical <= 100:

            return jsonify({
                'success': False,
                'error': (
                    'CPU critical must be '
                    'between 0 and 100'
                )
            }), 400

        if cpu_warning >= cpu_critical:

            return jsonify({
                'success': False,
                'error': (
                    'CPU warning must be lower '
                    'than CPU critical'
                )
            }), 400

        if not 0 <= ram_warning <= 100:

            return jsonify({
                'success': False,
                'error': (
                    'RAM warning must be '
                    'between 0 and 100'
                )
            }), 400

        if not 0 <= ram_critical <= 100:

            return jsonify({
                'success': False,
                'error': (
                    'RAM critical must be '
                    'between 0 and 100'
                )
            }), 400

        if ram_warning >= ram_critical:

            return jsonify({
                'success': False,
                'error': (
                    'RAM warning must be lower '
                    'than RAM critical'
                )
            }), 400

        if not 0 <= disk_warning <= 100:

            return jsonify({
                'success': False,
                'error': (
                    'Disk warning must be '
                    'between 0 and 100'
                )
            }), 400

        if not 0 <= disk_critical <= 100:

            return jsonify({
                'success': False,
                'error': (
                    'Disk critical must be '
                    'between 0 and 100'
                )
            }), 400

        if disk_warning >= disk_critical:

            return jsonify({
                'success': False,
                'error': (
                    'Disk warning must be lower '
                    'than Disk critical'
                )
            }), 400

        db.session.execute(
            text("""
                UPDATE system_settings
                SET
                    refresh_interval = :refresh_interval,
                    offline_threshold = :offline_threshold,
                    cpu_warning = :cpu_warning,
                    cpu_critical = :cpu_critical,
                    ram_warning = :ram_warning,
                    ram_critical = :ram_critical,
                    disk_warning = :disk_warning,
                    disk_critical = :disk_critical
                WHERE id = 1
            """),
            {
                'refresh_interval': refresh_interval,
                'offline_threshold': offline_threshold,
                'cpu_warning': cpu_warning,
                'cpu_critical': cpu_critical,
                'ram_warning': ram_warning,
                'ram_critical': ram_critical,
                'disk_warning': disk_warning,
                'disk_critical': disk_critical
            }
        )

        db.session.commit()

        logger.info(
            'System settings updated successfully'
        )

        return jsonify({
            'success': True,
            'message': 'Settings saved successfully',
            'settings': get_system_settings()
        }), 200

    except ValueError:

        db.session.rollback()

        return jsonify({
            'success': False,
            'error': (
                'Please enter valid numeric values'
            )
        }), 400

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error updating settings: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# COMPUTERS PAGE
# ============================================================

@app.route('/computers')
@login_required
def computers_page():

    return redirect(
        url_for('systems')
    )


@app.route(
    '/computer/<int:computer_id>'
)
@login_required
def computer_details(computer_id):

    computer = db.session.get(
        Computer,
        computer_id
    )

    if not computer:

        flash(
            'Computer not found',
            'danger'
        )

        return redirect(
            url_for('systems')
        )

    return render_template(
        'pc_details.html',
        computer=computer
    )


# ============================================================
# PREDICTIONS
# ============================================================

@app.route('/predictions')
@login_required
def predictions():

    try:

        computers = Computer.query.all()

        predictions_data = []

        total_critical = 0
        total_warnings = 0
        total_info = 0

        # System settings
        settings_data = get_system_settings()

        cpu_warning = settings_data['cpu_warning']
        cpu_critical = settings_data['cpu_critical']

        ram_warning = settings_data['ram_warning']
        ram_critical = settings_data['ram_critical']

        disk_warning = settings_data['disk_warning']
        disk_critical = settings_data['disk_critical']

        # -----------------------------------------
        # CURRENT ONLINE / OFFLINE THRESHOLD
        # -----------------------------------------

        offline_seconds = int(
            settings_data.get('offline_threshold', 20)
        )

        offline_threshold = (
            datetime.utcnow()
            - timedelta(seconds=offline_seconds)
        )

        # -----------------------------------------
        # PROCESS EVERY COMPUTER
        # -----------------------------------------

        for comp in computers:

            preds = []

            # -----------------------------------------
            # CALCULATE REAL-TIME CONNECTION STATUS
            # USING LAST HEARTBEAT
            # -----------------------------------------

            last_update = comp.last_update

            if last_update:

                # Handle string datetime if required
                if isinstance(last_update, str):

                    try:

                        last_update = datetime.fromisoformat(
                            last_update.replace('Z', '+00:00')
                        )

                        # Convert timezone-aware datetime
                        # to naive UTC datetime
                        if last_update.tzinfo is not None:
                            last_update = last_update.replace(
                                tzinfo=None
                            )

                    except Exception:

                        last_update = None

                # Current heartbeat is recent
                if (
                    last_update is not None
                    and last_update >= offline_threshold
                ):

                    connection_status = 'online'

                else:

                    connection_status = 'offline'

            else:

                connection_status = 'offline'

            # -----------------------------------------
            # STORE CURRENT CONNECTION STATUS
            # -----------------------------------------
            #
            # This makes Predictions use the same
            # online/offline status as Dashboard/API.
            #
            # Do NOT use old DB status for connection.
            # -----------------------------------------

            comp.connection_status = connection_status

            # -----------------------------------------
            # CPU PREDICTION
            # -----------------------------------------

            cpu = comp.cpu_usage or 0

            if cpu >= cpu_critical:

                preds.append({
                    'type': 'critical',
                    'icon': 'fa-exclamation-circle',
                    'title': 'CPU Overload',
                    'message': (
                        f'CPU usage at {cpu}% - '
                        'Immediate action required'
                    ),
                    'action': (
                        'Scale up or optimize processes'
                    ),
                    'severity': 5
                })

                total_critical += 1

            elif cpu >= cpu_warning:

                preds.append({
                    'type': 'warning',
                    'icon': 'fa-exclamation-triangle',
                    'title': 'High CPU Usage',
                    'message': (
                        f'CPU usage at {cpu}% - '
                        'Monitor performance'
                    ),
                    'action': (
                        'Check running processes'
                    ),
                    'severity': 3
                })

                total_warnings += 1

            # -----------------------------------------
            # RAM PREDICTION
            # -----------------------------------------

            ram = comp.ram_usage or 0

            if ram >= ram_critical:

                preds.append({
                    'type': 'critical',
                    'icon': 'fa-exclamation-circle',
                    'title': 'Memory Exhaustion',
                    'message': (
                        f'RAM usage at {ram}% - '
                        'Memory almost full'
                    ),
                    'action': (
                        'Upgrade RAM or close applications'
                    ),
                    'severity': 5
                })

                total_critical += 1

            elif ram >= ram_warning:

                preds.append({
                    'type': 'warning',
                    'icon': 'fa-exclamation-triangle',
                    'title': 'High Memory Usage',
                    'message': (
                        f'RAM usage at {ram}% - '
                        'Upgrade recommended'
                    ),
                    'action': (
                        'Consider adding more memory'
                    ),
                    'severity': 3
                })

                total_warnings += 1

            # -----------------------------------------
            # DISK PREDICTION
            # -----------------------------------------

            disk = comp.disk_usage or 0

            if disk >= disk_critical:

                preds.append({
                    'type': 'critical',
                    'icon': 'fa-exclamation-circle',
                    'title': 'Disk Full',
                    'message': (
                        f'Disk usage at {disk}% - '
                        'Immediate cleanup required'
                    ),
                    'action': (
                        'Delete unnecessary files'
                    ),
                    'severity': 5
                })

                total_critical += 1

            elif disk >= disk_warning:

                preds.append({
                    'type': 'warning',
                    'icon': 'fa-exclamation-triangle',
                    'title': 'High Disk Usage',
                    'message': (
                        f'Disk usage at {disk}% - '
                        'Plan for cleanup'
                    ),
                    'action': (
                        'Archive old data'
                    ),
                    'severity': 3
                })

                total_warnings += 1

            # -----------------------------------------
            # GPU PREDICTION
            # -----------------------------------------

            gpu = comp.gpu_usage or 0

            if gpu > 90:

                preds.append({
                    'type': 'warning',
                    'icon': 'fa-exclamation-triangle',
                    'title': 'GPU Overload',
                    'message': (
                        f'GPU usage at {gpu}% - '
                        'Performance may degrade'
                    ),
                    'action': (
                        'Reduce graphics load'
                    ),
                    'severity': 3
                })

                total_warnings += 1

            # -----------------------------------------
            # ONLINE / OFFLINE PREDICTION
            # -----------------------------------------

            if connection_status == 'offline':

                preds.append({
                    'type': 'critical',
                    'icon': 'fa-exclamation-circle',
                    'title': 'System Offline',
                    'message': (
                        f'{comp.computer_name} is offline'
                    ),
                    'action': (
                        'Check network connectivity'
                    ),
                    'severity': 5
                })

                total_critical += 1

            # -----------------------------------------
            # CRITICAL HEALTH STATUS
            # -----------------------------------------

            elif comp.status == 'critical':

                preds.append({
                    'type': 'critical',
                    'icon': 'fa-exclamation-circle',
                    'title': 'System Critical',
                    'message': (
                        f'{comp.computer_name} '
                        'is in critical state'
                    ),
                    'action': (
                        'Immediate investigation required'
                    ),
                    'severity': 5
                })

                total_critical += 1

            # -----------------------------------------
            # BATTERY PREDICTION
            # -----------------------------------------

            if comp.battery_percent is not None:

                battery = (
                    comp.battery_percent or 0
                )

                if (
                    battery < 5
                    and not comp.battery_charging
                ):

                    preds.append({
                        'type': 'critical',
                        'icon': 'fa-exclamation-circle',
                        'title': 'Battery Critical',
                        'message': (
                            f'Battery at {battery}% - '
                            'Charge immediately'
                        ),
                        'action': (
                            'Connect to power source'
                        ),
                        'severity': 5
                    })

                    total_critical += 1

                elif (
                    battery < 15
                    and not comp.battery_charging
                ):

                    preds.append({
                        'type': 'warning',
                        'icon': 'fa-exclamation-triangle',
                        'title': 'Low Battery',
                        'message': (
                            f'Battery at {battery}% - '
                            'Plug in charger'
                        ),
                        'action': (
                            'Connect to power source'
                        ),
                        'severity': 3
                    })

                    total_warnings += 1

            # -----------------------------------------
            # UPTIME PREDICTION
            # -----------------------------------------

            if comp.uptime:

                uptime = str(
                    comp.uptime
                ).lower()

                if 'day' in uptime:

                    try:

                        days = int(
                            ''.join(
                                filter(
                                    str.isdigit,
                                    uptime.split()[0]
                                )
                            )
                        )

                        if days > 30:

                            preds.append({
                                'type': 'info',
                                'icon': 'fa-info-circle',
                                'title': 'Long Uptime',
                                'message': (
                                    f'System running for '
                                    f'{days} days - '
                                    'Reboot recommended'
                                ),
                                'action': (
                                    'Schedule maintenance reboot'
                                ),
                                'severity': 2
                            })

                            total_info += 1

                    except Exception:
                        pass

            # -----------------------------------------
            # HEALTH SCORE
            # -----------------------------------------

            if preds:

                health_score = 100

                for p in preds:

                    if p['type'] == 'critical':

                        health_score -= 25

                    elif p['type'] == 'warning':

                        health_score -= 15

                    elif p['type'] == 'info':

                        health_score -= 5

                health_score = max(
                    0,
                    min(
                        100,
                        health_score
                    )
                )

                # -------------------------------------
                # HEALTH STATUS
                # -------------------------------------

                if health_score >= 80:

                    health_status = 'healthy'
                    health_color = '#34d399'
                    health_icon = 'fa-check-circle'

                elif health_score >= 50:

                    health_status = 'warning'
                    health_color = '#fbbf24'
                    health_icon = 'fa-exclamation-triangle'

                else:

                    health_status = 'critical'
                    health_color = '#ef4444'
                    health_icon = 'fa-exclamation-circle'

                # -------------------------------------
                # ADD COMPUTER DATA
                # -------------------------------------

                predictions_data.append({

                    'computer': comp,

                    'predictions': preds,

                    'health_score': health_score,

                    'health_status': health_status,

                    'health_color': health_color,

                    'health_icon': health_icon,

                    'total_predictions': len(preds),

                    'critical_count': sum(
                        1
                        for p in preds
                        if p['type'] == 'critical'
                    ),

                    'warning_count': sum(
                        1
                        for p in preds
                        if p['type'] == 'warning'
                    ),

                    'info_count': sum(
                        1
                        for p in preds
                        if p['type'] == 'info'
                    )
                })

        # -----------------------------------------
        # RENDER PREDICTIONS PAGE
        # -----------------------------------------

        return render_template(
            'predictions.html',

            predictions_data=predictions_data,

            total_systems=len(computers),

            total_issues=sum(
                len(p['predictions'])
                for p in predictions_data
            ),

            total_critical=total_critical,

            total_warnings=total_warnings,

            total_info=total_info
        )

    # ---------------------------------------------
    # ERROR HANDLING
    # ---------------------------------------------

    except Exception as e:

        logger.error(
            f"Predictions error: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        flash(
            'Unable to load predictions.',
            'danger'
        )

        return render_template(
            'predictions.html',

            predictions_data=[],

            total_systems=0,

            total_issues=0,

            total_critical=0,

            total_warnings=0,

            total_info=0
        )


# ============================================================
# MAINTENANCE PAGE
# ============================================================

@app.route('/maintenance')
@login_required
def maintenance():

    computers = Computer.query.all()

    maintenance_list = []

    settings_data = get_system_settings()

    cpu_warning = settings_data['cpu_warning']
    cpu_critical = settings_data['cpu_critical']

    ram_warning = settings_data['ram_warning']
    ram_critical = settings_data['ram_critical']

    disk_warning = settings_data['disk_warning']
    disk_critical = settings_data['disk_critical']

    for comp in computers:

        tasks = []

        cpu = comp.cpu_usage or 0
        ram = comp.ram_usage or 0
        disk = comp.disk_usage or 0

        if cpu >= cpu_critical:

            tasks.append({
                'type': 'urgent',
                'title': 'CPU Overload',
                'description': (
                    f'CPU usage is at '
                    f'{cpu}%. '
                    'Consider upgrading or '
                    'optimizing processes.'
                ),
                'icon': 'fa-microchip'
            })

        elif cpu >= cpu_warning:

            tasks.append({
                'type': 'warning',
                'title': 'High CPU Usage',
                'description': (
                    f'CPU usage is at '
                    f'{cpu}%. '
                    'Monitor performance.'
                ),
                'icon': 'fa-microchip'
            })

        if ram >= ram_critical:

            tasks.append({
                'type': 'urgent',
                'title': 'Memory Exhaustion',
                'description': (
                    f'RAM usage is at '
                    f'{ram}%. '
                    'Memory upgrade recommended.'
                ),
                'icon': 'fa-memory'
            })

        elif ram >= ram_warning:

            tasks.append({
                'type': 'warning',
                'title': 'High Memory Usage',
                'description': (
                    f'RAM usage is at '
                    f'{ram}%. '
                    'Consider adding more memory.'
                ),
                'icon': 'fa-memory'
            })

        if disk >= disk_critical:

            tasks.append({
                'type': 'urgent',
                'title': 'Disk Almost Full',
                'description': (
                    f'Disk usage is at '
                    f'{disk}%. '
                    'Cleanup required immediately.'
                ),
                'icon': 'fa-hdd'
            })

        elif disk >= disk_warning:

            tasks.append({
                'type': 'warning',
                'title': 'High Disk Usage',
                'description': (
                    f'Disk usage is at '
                    f'{disk}%. '
                    'Plan for cleanup.'
                ),
                'icon': 'fa-hdd'
            })

        if comp.status == 'offline':

            tasks.append({
                'type': 'urgent',
                'title': 'System Offline',
                'description': (
                    f'{comp.computer_name} is offline. '
                    'Check network connectivity.'
                ),
                'icon': 'fa-power-off'
            })

        if tasks:

            maintenance_list.append({
                'computer': comp,
                'tasks': tasks,
                'priority': (
                    'urgent'
                    if any(
                        t['type'] == 'urgent'
                        for t in tasks
                    )
                    else 'warning'
                )
            })

    return render_template(
        'maintenance.html',
        maintenance_list=maintenance_list
    )


# ============================================================
# TICKETS
# ============================================================

@app.route('/tickets')
@login_required
def tickets():

    try:

        tickets = (
            Ticket.query
            .order_by(
                Ticket.created_at.desc()
            )
            .all()
        )

        computers = Computer.query.all()

        return render_template(
            'tickets.html',
            tickets=tickets,
            computers=computers
        )

    except Exception as e:

        logger.error(
            f"Error loading tickets: {e}"
        )

        return render_template(
            'tickets.html',
            tickets=[],
            computers=[]
        )


@app.route(
    '/api/tickets',
    methods=['POST']
)
@login_required
def create_ticket():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        current_user = get_current_account()

        if not current_user:

            return jsonify({
                'error': 'User not found'
            }), 401

        if (
            not data.get('title')
            or not data.get('description')
        ):

            return jsonify({
                'error': (
                    'Title and description are required'
                )
            }), 400

        due_date = None

        if data.get('due_date'):

            due_date = datetime.strptime(
                data['due_date'],
                '%Y-%m-%d'
            )

        ticket = Ticket(
            title=data['title'],
            description=data['description'],
            status='open',
            priority=data.get(
                'priority',
                'medium'
            ),
            category=data.get(
                'category',
                'General'
            ),
            computer_id=data.get(
                'computer_id'
            ) or None,
            due_date=due_date,
            created_by=current_user.id,
            assigned_to=current_user.id,
            progress=0
        )

        db.session.add(ticket)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Ticket created successfully',
            'ticket': ticket.to_dict()
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error creating ticket: {e}"
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/api/tickets/<int:ticket_id>',
    methods=['DELETE']
)
@admin_required
def delete_ticket(ticket_id):

    try:

        ticket = db.session.get(
            Ticket,
            ticket_id
        )

        if not ticket:

            return jsonify({
                'error': 'Ticket not found'
            }), 404

        db.session.delete(ticket)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Ticket deleted successfully'
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error deleting ticket: {e}"
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/api/tickets/<int:ticket_id>/progress',
    methods=['POST']
)
@admin_required
def update_ticket_progress(ticket_id):

    try:

        data = request.get_json(
            silent=True
        ) or {}

        progress = int(
            data.get(
                'progress',
                0
            )
        )

        if not 0 <= progress <= 100:

            return jsonify({
                'error': (
                    'Progress must be between 0 and 100'
                )
            }), 400

        ticket = db.session.get(
            Ticket,
            ticket_id
        )

        if not ticket:

            return jsonify({
                'error': 'Ticket not found'
            }), 404

        ticket.progress = progress

        if progress == 0:

            ticket.status = 'open'

        elif 0 < progress < 100:

            ticket.status = 'in-progress'

            if not ticket.started_at:

                ticket.started_at = (
                    datetime.utcnow()
                )

        elif progress == 100:

            ticket.status = 'resolved'

            ticket.completed_at = (
                datetime.utcnow()
            )

            ticket.resolved_at = (
                datetime.utcnow()
            )

        ticket.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Progress updated successfully'
            ),
            'ticket': ticket.to_dict()
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error updating progress: {e}"
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/api/tickets/<int:ticket_id>/comment',
    methods=['POST']
)
@admin_required
def add_ticket_comment(ticket_id):

    try:

        data = request.get_json(
            silent=True
        ) or {}

        comment_text = data.get(
            'comment',
            ''
        ).strip()

        if not comment_text:

            return jsonify({
                'error': 'Comment cannot be empty'
            }), 400

        ticket = db.session.get(
            Ticket,
            ticket_id
        )

        if not ticket:

            return jsonify({
                'error': 'Ticket not found'
            }), 404

        current_user = get_current_account()

        if not current_user:

            return jsonify({
                'error': 'User not found'
            }), 401

        comment = TicketComment(
            ticket_id=ticket_id,
            user_id=current_user.id,
            comment=comment_text
        )

        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Comment added',
            'comment': comment.to_dict()
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"Error adding comment: {e}"
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/tickets/count')
@login_required
def get_ticket_count():

    try:

        open_count = Ticket.query.filter_by(
            status='open'
        ).count()

        in_progress_count = Ticket.query.filter_by(
            status='in-progress'
        ).count()

        resolved_count = Ticket.query.filter_by(
            status='resolved'
        ).count()

        total = Ticket.query.count()

        return jsonify({
            'success': True,
            'open_count': open_count,
            'in_progress_count': in_progress_count,
            'resolved_count': resolved_count,
            'total': total
        })

    except Exception as e:

        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/tickets')
@login_required
def get_tickets_api():

    try:

        tickets = (
            Ticket.query
            .order_by(
                Ticket.created_at.desc()
            )
            .all()
        )

        return jsonify({
            'success': True,
            'tickets': [
                t.to_dict()
                for t in tickets
            ]
        })

    except Exception as e:

        return jsonify({
            'error': str(e)
        }), 500


# ============================================================
# ALERTS
# ============================================================

@app.route('/alerts')
@login_required
def alerts():

    computers = Computer.query.all()

    alerts_data = []

    alert_id = 1

    settings_data = get_system_settings()

    cpu_warning = settings_data['cpu_warning']
    cpu_critical = settings_data['cpu_critical']

    ram_warning = settings_data['ram_warning']
    ram_critical = settings_data['ram_critical']

    disk_warning = settings_data['disk_warning']
    disk_critical = settings_data['disk_critical']

    for comp in computers:

        cpu = comp.cpu_usage or 0
        ram = comp.ram_usage or 0
        disk = comp.disk_usage or 0

        if cpu >= cpu_critical:

            alerts_data.append({
                'id': alert_id,
                'type': 'critical',
                'message': (
                    f'{comp.computer_name} CPU usage '
                    f'exceeded {cpu_critical}%'
                ),
                'timestamp': (
                    comp.last_update
                    or datetime.utcnow()
                ),
                'status': 'unread',
                'computer': comp.computer_name
            })

            alert_id += 1

        elif cpu >= cpu_warning:

            alerts_data.append({
                'id': alert_id,
                'type': 'warning',
                'message': (
                    f'{comp.computer_name} CPU usage '
                    f'at {cpu}%'
                ),
                'timestamp': (
                    comp.last_update
                    or datetime.utcnow()
                ),
                'status': 'unread',
                'computer': comp.computer_name
            })

            alert_id += 1

        if ram >= ram_critical:

            alerts_data.append({
                'id': alert_id,
                'type': 'critical',
                'message': (
                    f'{comp.computer_name} RAM usage '
                    f'at {ram}%'
                ),
                'timestamp': (
                    comp.last_update
                    or datetime.utcnow()
                ),
                'status': 'unread',
                'computer': comp.computer_name
            })

            alert_id += 1

        elif ram >= ram_warning:

            alerts_data.append({
                'id': alert_id,
                'type': 'warning',
                'message': (
                    f'{comp.computer_name} RAM usage '
                    f'at {ram}%'
                ),
                'timestamp': (
                    comp.last_update
                    or datetime.utcnow()
                ),
                'status': 'unread',
                'computer': comp.computer_name
            })

            alert_id += 1

        if disk >= disk_critical:

            alerts_data.append({
                'id': alert_id,
                'type': 'critical',
                'message': (
                    f'{comp.computer_name} disk usage '
                    f'at {disk}%'
                ),
                'timestamp': (
                    comp.last_update
                    or datetime.utcnow()
                ),
                'status': 'unread',
                'computer': comp.computer_name
            })

            alert_id += 1

        elif disk >= disk_warning:

            alerts_data.append({
                'id': alert_id,
                'type': 'warning',
                'message': (
                    f'{comp.computer_name} disk usage '
                    f'at {disk}%'
                ),
                'timestamp': (
                    comp.last_update
                    or datetime.utcnow()
                ),
                'status': 'unread',
                'computer': comp.computer_name
            })

            alert_id += 1

        if comp.status == 'offline':

            alerts_data.append({
                'id': alert_id,
                'type': 'critical',
                'message': (
                    f'{comp.computer_name} is offline - '
                    'Immediate attention'
                ),
                'timestamp': (
                    comp.last_update
                    or datetime.utcnow()
                ),
                'status': 'unread',
                'computer': comp.computer_name
            })

            alert_id += 1

    if not alerts_data:

        alerts_data.append({
            'id': 1,
            'type': 'info',
            'message': (
                'All systems are operating normally'
            ),
            'timestamp': datetime.utcnow(),
            'status': 'read',
            'computer': 'System'
        })

    return render_template(
        'alerts.html',
        alerts=alerts_data
    )


# ============================================================
# QR CODE
# ============================================================

@app.route('/qr')
@login_required
def qr_selection():

    try:

        computers = Computer.query.all()

        settings_data = get_system_settings()

        offline_seconds = int(
            settings_data.get(
                'offline_threshold',
                20
            )
        )

        offline_threshold = (
            datetime.utcnow()
            - timedelta(
                seconds=offline_seconds
            )
        )

        for comp in computers:

            last_update = comp.last_update

            if last_update:

                if last_update.tzinfo is not None:
                    last_update = last_update.replace(
                        tzinfo=None
                    )

            if (
                not last_update
                or last_update < offline_threshold
            ):

                comp.connection_status = 'offline'

            else:

                comp.connection_status = 'online'

        return render_template(
            'qr_selection.html',
            computers=computers
        )

    except Exception as e:

        logger.error(
            f'Error loading QR selection: {str(e)}'
        )

        logger.error(
            traceback.format_exc()
        )

        return render_template(
            'qr_selection.html',
            computers=[]
        )


@app.route('/qr/<int:computer_id>')
@login_required
def qr_display(computer_id):

    computer = db.session.get(
        Computer,
        computer_id
    )

    if not computer:

        flash(
            'Computer not found',
            'danger'
        )

        return redirect(
            url_for('qr_selection')
        )

    try:

        settings_data = get_system_settings()

        offline_seconds = int(
            settings_data.get(
                'offline_threshold',
                20
            )
        )

        offline_threshold = (
            datetime.utcnow()
            - timedelta(
                seconds=offline_seconds
            )
        )

        last_update = computer.last_update

        if last_update:

            if last_update.tzinfo is not None:
                last_update = last_update.replace(
                    tzinfo=None
                )

        if (
            not last_update
            or last_update < offline_threshold
        ):

            computer.connection_status = 'offline'

        else:

            computer.connection_status = 'online'

    except Exception as e:

        logger.error(
            f'Error checking QR computer status: {str(e)}'
        )

        logger.error(
            traceback.format_exc()
        )

        computer.connection_status = 'offline'

    return render_template(
        'qr_code.html',
        computer=computer
    )


@app.route('/qr-scanner')
@login_required
def qr_scanner():

    return render_template(
        'qr_scanner.html'
    )


@app.route(
    '/api/qrcode/<int:computer_id>'
)
@login_required
def generate_qr_code(computer_id):

    try:

        computer = db.session.get(
            Computer,
            computer_id
        )

        if not computer:

            return jsonify({
                'error': 'Computer not found'
            }), 404

        if computer.qr_code:

            return jsonify({
                'success': True,
                'qr_code': computer.qr_code,
                'device_id': computer.device_id,
                'computer': computer.to_dict()
            }), 200

        qr_data = computer.device_id

        qr = qrcode.QRCode(
            version=1,
            error_correction=(
                qrcode.constants.ERROR_CORRECT_L
            ),
            box_size=10,
            border=4
        )

        qr.add_data(qr_data)

        qr.make(
            fit=True
        )

        img = qr.make_image(
            fill_color='black',
            back_color='white'
        )

        img = img.resize(
            (300, 300)
        )

        buffered = io.BytesIO()

        img.save(
            buffered,
            format='PNG'
        )

        img_str = base64.b64encode(
            buffered.getvalue()
        ).decode()

        qr_base64 = (
            f'data:image/png;base64,{img_str}'
        )

        computer.qr_code = qr_base64

        db.session.commit()

        return jsonify({
            'success': True,
            'qr_code': qr_base64,
            'device_id': computer.device_id,
            'computer': computer.to_dict()
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error generating QR code: {e}'
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/api/device/<string:device_id>'
)
@login_required
def get_device_by_id(device_id):

    try:

        computer = Computer.query.filter_by(
            device_id=device_id.upper()
        ).first()

        if not computer:

            return jsonify({
                'error': 'Device not found'
            }), 404

        return jsonify({
            'success': True,
            'computer': computer.to_dict()
        }), 200

    except Exception as e:

        logger.error(
            f'Error looking up device: {e}'
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'error': str(e)
        }), 500

# ============================================================
# AGENT TELEMETRY UPDATE
# ============================================================

@app.route(
    '/api/update',
    methods=['POST']
)
def update_computer():

    try:

        data = request.get_json(
            silent=True
        )

        logger.info(
            f'Received data: {data}'
        )

        if not data:

            return jsonify({
                'error': 'Invalid JSON data'
            }), 400

        required_fields = [
            'computer_name',
            'ip_address',
            'cpu_usage',
            'ram_usage',
            'disk_usage'
        ]

        for field in required_fields:

            if field not in data:

                return jsonify({
                    'error': f'Missing: {field}'
                }), 400

        cpu = float(
            data['cpu_usage']
        )

        ram = float(
            data['ram_usage']
        )

        disk = float(
            data['disk_usage']
        )

        settings_data = get_system_settings()

        cpu_warning = settings_data['cpu_warning']
        cpu_critical = settings_data['cpu_critical']

        ram_warning = settings_data['ram_warning']
        ram_critical = settings_data['ram_critical']

        disk_warning = settings_data['disk_warning']
        disk_critical = settings_data['disk_critical']

        # =====================================================
        # CONNECTION STATUS
        # =====================================================
        # If agent successfully sends data, computer is ONLINE.
        #
        # IMPORTANT:
        # Do NOT put warning/critical here.
        # Health is calculated separately below.

        status = 'online'

        # =====================================================
        # HEALTH STATUS
        # =====================================================

        if (
            cpu >= cpu_critical
            or ram >= ram_critical
            or disk >= disk_critical
        ):

            health_status = 'critical'

        elif (
            cpu >= cpu_warning
            or ram >= ram_warning
            or disk >= disk_warning
        ):

            health_status = 'warning'

        else:

            health_status = 'healthy'

        logger.info(
            f"Computer: {data['computer_name']} | "
            f"Connection: {status} | "
            f"Health: {health_status}"
        )

        # =====================================================
        # FIND COMPUTER
        # =====================================================

        computer = Computer.query.filter_by(
            computer_name=data['computer_name']
        ).first()

        # =====================================================
        # EXISTING COMPUTER
        # =====================================================

        if computer:

            computer.ip_address = data[
                'ip_address'
            ]

            computer.cpu_usage = cpu

            computer.ram_usage = ram

            computer.disk_usage = disk

            computer.cpu_model = data.get(
                'cpu_model',
                'Unknown'
            )

            computer.cpu_cores = data.get(
                'cpu_cores',
                0
            )

            computer.cpu_threads = data.get(
                'cpu_threads',
                0
            )

            computer.ram_total = data.get(
                'ram_total',
                0
            )

            computer.ram_used = data.get(
                'ram_used',
                0
            )

            computer.ram_available = data.get(
                'ram_available',
                0
            )

            computer.gpu_model = data.get(
                'gpu_model',
                'Unknown'
            )

            computer.gpu_vram = data.get(
                'gpu_vram',
                0
            )

            computer.gpu_usage = data.get(
                'gpu_usage',
                0
            )

            computer.storage_model = data.get(
                'storage_model',
                'Unknown'
            )

            computer.storage_type = data.get(
                'storage_type',
                'Unknown'
            )

            computer.storage_total = data.get(
                'storage_total',
                0
            )

            computer.storage_used = data.get(
                'storage_used',
                0
            )

            computer.manufacturer = data.get(
                'manufacturer',
                'Unknown'
            )

            computer.system_model = data.get(
                'system_model',
                'Unknown'
            )

            computer.motherboard = data.get(
                'motherboard',
                'Unknown'
            )

            computer.bios_version = data.get(
                'bios_version',
                'Unknown'
            )

            computer.architecture = data.get(
                'architecture',
                'Unknown'
            )

            computer.battery_percent = data.get(
                'battery_percent'
            )

            computer.battery_charging = data.get(
                'battery_charging'
            )

            computer.disk_free = data.get(
                'disk_free',
                '0 GB'
            )

            computer.uptime = data.get(
                'uptime',
                '0 minutes'
            )

            computer.operating_system = data.get(
                'operating_system',
                'Unknown'
            )

            # =================================================
            # IMPORTANT
            # status = CONNECTION STATUS ONLY
            # =================================================

            computer.status = 'online'

            # =================================================
            # HEARTBEAT
            # =================================================

            computer.last_update = datetime.utcnow()

            logger.info(
                f'Updated: {computer.computer_name} | '
                f'Online | Health: {health_status}'
            )

        # =====================================================
        # NEW COMPUTER
        # =====================================================

        else:

            device_id = (
                Computer.generate_device_id()
            )

            computer = Computer(

                device_id=device_id,

                computer_name=data[
                    'computer_name'
                ],

                ip_address=data[
                    'ip_address'
                ],

                cpu_usage=cpu,

                ram_usage=ram,

                disk_usage=disk,

                cpu_model=data.get(
                    'cpu_model',
                    'Unknown'
                ),

                cpu_cores=data.get(
                    'cpu_cores',
                    0
                ),

                cpu_threads=data.get(
                    'cpu_threads',
                    0
                ),

                ram_total=data.get(
                    'ram_total',
                    0
                ),

                ram_used=data.get(
                    'ram_used',
                    0
                ),

                ram_available=data.get(
                    'ram_available',
                    0
                ),

                gpu_model=data.get(
                    'gpu_model',
                    'Unknown'
                ),

                gpu_vram=data.get(
                    'gpu_vram',
                    0
                ),

                gpu_usage=data.get(
                    'gpu_usage',
                    0
                ),

                storage_model=data.get(
                    'storage_model',
                    'Unknown'
                ),

                storage_type=data.get(
                    'storage_type',
                    'Unknown'
                ),

                storage_total=data.get(
                    'storage_total',
                    0
                ),

                storage_used=data.get(
                    'storage_used',
                    0
                ),

                manufacturer=data.get(
                    'manufacturer',
                    'Unknown'
                ),

                system_model=data.get(
                    'system_model',
                    'Unknown'
                ),

                motherboard=data.get(
                    'motherboard',
                    'Unknown'
                ),

                bios_version=data.get(
                    'bios_version',
                    'Unknown'
                ),

                architecture=data.get(
                    'architecture',
                    'Unknown'
                ),

                battery_percent=data.get(
                    'battery_percent'
                ),

                battery_charging=data.get(
                    'battery_charging'
                ),

                disk_free=data.get(
                    'disk_free',
                    '0 GB'
                ),

                uptime=data.get(
                    'uptime',
                    '0 minutes'
                ),

                operating_system=data.get(
                    'operating_system',
                    'Unknown'
                ),

                # Connection status only
                status='online',

                # Heartbeat
                last_update=datetime.utcnow()
            )

            db.session.add(
                computer
            )

            logger.info(
                f'New computer: '
                f'{computer.computer_name} '
                f'with Device ID: {device_id} | '
                f'Online | Health: {health_status}'
            )

        # =====================================================
        # SAVE COMPUTER
        # =====================================================

        db.session.commit()

        # =====================================================
        # HISTORY
        # =====================================================

        history = History(

            computer_id=computer.id,

            cpu=cpu,

            ram=ram,

            disk=disk,

            timestamp=datetime.utcnow()
        )

        db.session.add(
            history
        )

        db.session.commit()

        # =====================================================
        # RESPONSE
        # =====================================================

        return jsonify({

            'success': True,

            'message': 'Data updated',

            'connection_status': 'online',

            'health_status': health_status

        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error: {str(e)}'
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'error': str(e)
        }), 500

# ============================================================
# COMPUTERS API
# ============================================================

# ============================================================
# COMPUTERS API
# ============================================================

@app.route(
    '/api/computers',
    methods=['GET']
)
@login_required
def get_computers():

    try:

        computers = Computer.query.all()

        settings_data = get_system_settings()

        # =====================================================
        # OFFLINE THRESHOLD
        # =====================================================

        offline_seconds = int(
            settings_data.get(
                'offline_threshold',
                20
            )
        )

        offline_threshold = (
            datetime.utcnow()
            - timedelta(
                seconds=offline_seconds
            )
        )

        result = []

        # =====================================================
        # PROCESS EACH COMPUTER
        # =====================================================

        for comp in computers:

            # =================================================
            # DATETIME NORMALIZATION
            # =================================================

            last_update = comp.last_update

            if last_update:

                if last_update.tzinfo is not None:

                    last_update = (
                        last_update.replace(
                            tzinfo=None
                        )
                    )

            # =================================================
            # CONNECTION STATUS
            # =================================================

            if (
                not last_update
                or last_update < offline_threshold
            ):

                connection_status = 'offline'

            else:

                connection_status = 'online'

            # =================================================
            # CURRENT RESOURCE VALUES
            # =================================================

            cpu = float(
                comp.cpu_usage or 0
            )

            ram = float(
                comp.ram_usage or 0
            )

            disk = float(
                comp.disk_usage or 0
            )

            # =================================================
            # HEALTH STATUS
            # =================================================

            if (
                cpu >= settings_data[
                    'cpu_critical'
                ]

                or

                ram >= settings_data[
                    'ram_critical'
                ]

                or

                disk >= settings_data[
                    'disk_critical'
                ]
            ):

                health_status = 'critical'

            elif (
                cpu >= settings_data[
                    'cpu_warning'
                ]

                or

                ram >= settings_data[
                    'ram_warning'
                ]

                or

                disk >= settings_data[
                    'disk_warning'
                ]
            ):

                health_status = 'warning'

            else:

                health_status = 'healthy'

            # =================================================
            # OFFLINE = NO CURRENT HEALTH STATE
            # =================================================

            if connection_status == 'offline':

                display_health_status = 'offline'

            else:

                display_health_status = health_status

            # =================================================
            # IMPORTANT
            #
            # Keep database status as CONNECTION status only.
            #
            # Old frontend/code using comp.status will therefore
            # still see:
            #
            # online / offline
            #
            # It will NEVER become warning/critical.
            # =================================================

            comp.status = connection_status

            # =================================================
            # CREATE DICTIONARY
            # =================================================

            computer_data = comp.to_dict()

            # =================================================
            # ADD NEW SEPARATE STATUS FIELDS
            # =================================================

            computer_data[
                'connection_status'
            ] = connection_status

            computer_data[
                'health_status'
            ] = display_health_status

            # =================================================
            # LAST UPDATE
            # =================================================

            if last_update:

                computer_data[
                    'last_update'
                ] = last_update.isoformat()

            else:

                computer_data[
                    'last_update'
                ] = None

            # =================================================
            # ADD TO RESULT
            # =================================================

            result.append(
                computer_data
            )

        # =====================================================
        # RESPONSE
        # =====================================================

        return jsonify({

            'success': True,

            'computers': result

        }), 200

    except Exception as e:

        logger.error(
            f'Error getting computers: {str(e)}'
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({

            'success': False,

            'error': str(e)

        }), 500

# ============================================================
# SINGLE COMPUTER API
# ============================================================

@app.route(
    '/api/computer/<int:computer_id>',
    methods=['GET']
)
@login_required
def get_computer(computer_id):

    try:

        computer = db.session.get(
            Computer,
            computer_id
        )

        if not computer:

            return jsonify({
                'error': 'Not found'
            }), 404

        settings_data = get_system_settings()

        # =====================================================
        # OFFLINE THRESHOLD
        # =====================================================

        offline_seconds = int(
            settings_data.get(
                'offline_threshold',
                20
            )
        )

        offline_threshold = (
            datetime.utcnow()
            - timedelta(
                seconds=offline_seconds
            )
        )

        # =====================================================
        # DATETIME
        # =====================================================

        last_update = computer.last_update

        if last_update:

            if last_update.tzinfo is not None:

                last_update = (
                    last_update.replace(
                        tzinfo=None
                    )
                )

        # =====================================================
        # CONNECTION STATUS
        # =====================================================

        if (
            not last_update
            or last_update < offline_threshold
        ):

            connection_status = 'offline'

        else:

            connection_status = 'online'

        # =====================================================
        # RESOURCE VALUES
        # =====================================================

        cpu = float(
            computer.cpu_usage or 0
        )

        ram = float(
            computer.ram_usage or 0
        )

        disk = float(
            computer.disk_usage or 0
        )

        # =====================================================
        # HEALTH STATUS
        # =====================================================

        if (
            cpu >= settings_data['cpu_critical']
            or
            ram >= settings_data['ram_critical']
            or
            disk >= settings_data['disk_critical']
        ):

            health_status = 'critical'

        elif (
            cpu >= settings_data['cpu_warning']
            or
            ram >= settings_data['ram_warning']
            or
            disk >= settings_data['disk_warning']
        ):

            health_status = 'warning'

        else:

            health_status = 'healthy'

        # =====================================================
        # OFFLINE = NO CURRENT HEALTH STATE
        # =====================================================

        if connection_status == 'offline':

            display_health_status = 'offline'

        else:

            display_health_status = health_status

        # =====================================================
        # KEEP LEGACY STATUS AS CONNECTION STATUS
        # =====================================================

        computer.status = connection_status

        # =====================================================
        # PREDICTIONS
        # =====================================================

        predictions = []

        if cpu >= settings_data['cpu_critical']:

            predictions.append(
                '⚠️ Critical CPU Usage'
            )

        elif cpu >= settings_data['cpu_warning']:

            predictions.append(
                '⚠️ High CPU Usage'
            )

        if ram >= settings_data['ram_critical']:

            predictions.append(
                '⚠️ Memory Almost Full'
            )

        elif ram >= settings_data['ram_warning']:

            predictions.append(
                '⚠️ High Memory Usage'
            )

        if disk >= settings_data['disk_critical']:

            predictions.append(
                '⚠️ Disk Nearly Full'
            )

        elif disk >= settings_data['disk_warning']:

            predictions.append(
                '⚠️ High Disk Usage'
            )

        # =====================================================
        # OFFLINE PREDICTION
        # =====================================================

        if connection_status == 'offline':

            predictions.append(
                '📴 Offline - No updates received'
            )

        # =====================================================
        # HISTORY
        # =====================================================

        history = (
            History.query
            .filter_by(
                computer_id=computer_id
            )
            .order_by(
                History.timestamp.desc()
            )
            .limit(50)
            .all()
        )

        history = history[::-1]

        # =====================================================
        # COMPUTER DATA
        # =====================================================

        computer_data = computer.to_dict()

        # Separate connection + health
        computer_data[
            'connection_status'
        ] = connection_status

        computer_data[
            'health_status'
        ] = display_health_status

        if last_update:

            computer_data[
                'last_update'
            ] = last_update.isoformat()

        else:

            computer_data[
                'last_update'
            ] = None

        # =====================================================
        # RESPONSE
        # =====================================================

        return jsonify({

            'success': True,

            'computer': computer_data,

            'predictions': predictions,

            'history': [
                h.to_dict()
                for h in history
            ]

        }), 200

    except Exception as e:

        logger.error(
            f'Error: {str(e)}'
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'error': str(e)
        }), 500

# ============================================================
# HISTORY
# ============================================================

@app.route(
    '/api/history/<int:computer_id>',
    methods=['GET']
)
@login_required
def get_history(computer_id):

    try:

        limit = request.args.get(
            'limit',
            50,
            type=int
        )

        limit = max(
            1,
            min(
                limit,
                500
            )
        )

        history = (
            History.query
            .filter_by(
                computer_id=computer_id
            )
            .order_by(
                History.timestamp.desc()
            )
            .limit(limit)
            .all()
        )

        history = history[::-1]

        return jsonify({
            'success': True,
            'history': [
                h.to_dict()
                for h in history
            ],
            'total': len(history)
        }), 200

    except Exception as e:

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/api/history/clear/<int:computer_id>',
    methods=['DELETE']
)
@admin_required
def clear_history(computer_id):

    try:

        db.session.execute(
            text(
                'DELETE FROM history '
                'WHERE computer_id = :computer_id'
            ),
            {
                'computer_id': computer_id
            }
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'History cleared successfully'
            )
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error clearing history: {e}'
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/api/clear-all',
    methods=['DELETE']
)
@admin_required
def clear_all():

    try:

        db.session.execute(
            text('DELETE FROM history')
        )

        db.session.execute(
            text('DELETE FROM computers')
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'All data cleared'
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error clearing all data: {e}'
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/api/history/add-sample/<int:computer_id>',
    methods=['POST']
)
@admin_required
def add_sample_history(computer_id):

    try:

        computer = db.session.get(
            Computer,
            computer_id
        )

        if not computer:

            return jsonify({
                'error': 'Computer not found'
            }), 404

        for i in range(10):

            history = History(
                computer_id=computer_id,

                cpu=round(
                    random.uniform(
                        20,
                        95
                    ),
                    1
                ),

                ram=round(
                    random.uniform(
                        30,
                        90
                    ),
                    1
                ),

                disk=round(
                    random.uniform(
                        40,
                        98
                    ),
                    1
                ),

                timestamp=(
                    datetime.utcnow()
                    - timedelta(
                        minutes=i * 5
                    )
                )
            )

            db.session.add(history)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Sample history added'
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error adding sample history: {e}'
        )

        return jsonify({
            'error': str(e)
        }), 500


# ============================================================
# DELETE COMPUTER
# ============================================================

@app.route(
    '/api/computer/<int:computer_id>',
    methods=['DELETE']
)
@admin_required
def delete_computer(computer_id):

    try:

        computer = db.session.get(
            Computer,
            computer_id
        )

        if not computer:

            return jsonify({
                'error': 'Computer not found'
            }), 404

        computer_name = (
            computer.computer_name
        )

        db.session.delete(
            computer
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                f'Computer {computer_name} '
                'deleted successfully'
            )
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error deleting computer: {e}'
        )

        return jsonify({
            'error': str(e)
        }), 500


# ============================================================
# INVENTORY API
# ============================================================

@app.route(
    '/api/inventory',
    methods=['GET']
)
@login_required
def get_inventory():

    try:

        components = (
            Inventory.query
            .order_by(
                Inventory.id.desc()
            )
            .all()
        )

        return jsonify({
            'success': True,
            'data': [
                component.to_dict()
                for component in components
            ]
        }), 200

    except Exception as e:

        logger.error(
            f'Error loading inventory: {e}'
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route(
    '/api/inventory',
    methods=['POST']
)
@admin_required
def add_inventory():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        component_type = str(
            data.get('type', '')
        ).strip()

        component_name = str(
            data.get('name', '')
        ).strip()

        if (
            not component_type
            or not component_name
        ):

            return jsonify({
                'success': False,
                'error': (
                    'Component type and name '
                    'are required'
                )
            }), 400

        purchase_date = None

        if data.get('purchaseDate'):

            purchase_date = datetime.strptime(
                data['purchaseDate'],
                '%Y-%m-%d'
            ).date()

        component = Inventory(
            component_type=component_type,

            component_name=component_name,

            manufacturer=str(
                data.get(
                    'manufacturer',
                    ''
                )
            ).strip() or None,

            model=str(
                data.get(
                    'model',
                    ''
                )
            ).strip() or None,

            serial_number=str(
                data.get(
                    'serial',
                    ''
                )
            ).strip() or None,

            system_name=str(
                data.get(
                    'system',
                    ''
                )
            ).strip() or None,

            quantity=int(
                data.get(
                    'quantity',
                    1
                ) or 1
            ),

            status=str(
                data.get(
                    'status',
                    'Good'
                )
            ).strip(),

            purchase_date=purchase_date
        )

        db.session.add(component)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Component added successfully'
            ),
            'data': component.to_dict()
        }), 201

    except ValueError:

        db.session.rollback()

        return jsonify({
            'success': False,
            'error': (
                'Invalid quantity or purchase date'
            )
        }), 400

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error adding inventory component: {e}'
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route(
    '/api/inventory/<int:component_id>',
    methods=['DELETE']
)
@admin_required
def delete_inventory(component_id):

    try:

        component = db.session.get(
            Inventory,
            component_id
        )

        if not component:

            return jsonify({
                'success': False,
                'error': 'Component not found'
            }), 404

        db.session.delete(component)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Component deleted successfully'
            )
        }), 200

    except Exception as e:

        db.session.rollback()

        logger.error(
            f'Error deleting inventory component: {e}'
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# CURRENT USER API
# ============================================================

@app.route('/api/me')
@login_required
def get_current_user_api():

    try:

        account = get_current_account()

        if not account:

            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 401

        role = (
            account.role or 'user'
        ).strip().lower()

        return jsonify({
            'success': True,
            'user': {
                'id': account.id,
                'username': account.username,
                'email': account.email,
                'role': role,
                'is_admin': role == 'admin'
            }
        }), 200

    except Exception as e:

        logger.error(
            f'Error loading current user: {e}'
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# TEMPLATE CONTEXT
# ============================================================

@app.context_processor
def inject_account():

    account = get_current_account()

    role = (
        (
            account.role or 'user'
        ).strip().lower()
        if account
        else None
    )

    return dict(
        current_account=account,
        current_role=role,
        is_admin=(
            role == 'admin'
            if account
            else False
        )
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(e):

    if 'account_id' in session:

        flash(
            'Page not found. Please check the URL.',
            'warning'
        )

        return redirect(
            url_for('index')
        )

    flash(
        'Please log in to access this page.',
        'warning'
    )

    return redirect(
        url_for('login')
    )


@app.errorhandler(500)
def internal_server_error(e):

    logger.error(
        f'Server error: {e}'
    )

    db.session.rollback()

    flash(
        'Something went wrong. '
        'Please try again later.',
        'danger'
    )

    if 'account_id' in session:

        return redirect(
            url_for('index')
        )

    return redirect(
        url_for('login')
    )

# ============================================================
# IOT - DHT11 API
# ============================================================

@app.route(
    '/api/iot/update',
    methods=['POST']
)
def update_iot_data():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        device_id = str(
            data.get('device_id', '')
        ).strip()

        device_name = str(
            data.get(
                'device_name',
                device_id
            )
        ).strip()

        temperature = data.get(
            'temperature'
        )

        humidity = data.get(
            'humidity'
        )

        # ----------------------------------------------------
        # Required fields
        # ----------------------------------------------------

        if not device_id:
            return jsonify({
                'success': False,
                'error': 'device_id is required'
            }), 400

        if temperature is None:
            return jsonify({
                'success': False,
                'error': 'temperature is required'
            }), 400

        if humidity is None:
            return jsonify({
                'success': False,
                'error': 'humidity is required'
            }), 400

        # ----------------------------------------------------
        # Convert sensor values
        # ----------------------------------------------------

        temperature = float(temperature)
        humidity = float(humidity)

        # ----------------------------------------------------
        # Validate DHT11 values
        # ----------------------------------------------------

        if not -40 <= temperature <= 80:
            return jsonify({
                'success': False,
                'error': 'Invalid temperature value'
            }), 400

        if not 0 <= humidity <= 100:
            return jsonify({
                'success': False,
                'error': 'Invalid humidity value'
            }), 400

        now = datetime.utcnow()

        # ----------------------------------------------------
        # Check whether device already exists
        # ----------------------------------------------------

        device = db.session.execute(
            text("""
                SELECT id
                FROM iot_devices
                WHERE device_id = :device_id
                LIMIT 1
            """),
            {
                'device_id': device_id
            }
        ).first()

        # ----------------------------------------------------
        # Create / update device
        # ----------------------------------------------------

        if device:

            db.session.execute(
                text("""
                    UPDATE iot_devices
                    SET
                        device_name = :device_name,
                        sensor_type = 'DHT11',
                        status = 'online',
                        last_seen = :last_seen
                    WHERE device_id = :device_id
                """),
                {
                    'device_name': device_name,
                    'last_seen': now,
                    'device_id': device_id
                }
            )

        else:

            db.session.execute(
                text("""
                    INSERT INTO iot_devices
                    (
                        device_id,
                        device_name,
                        sensor_type,
                        status,
                        last_seen
                    )
                    VALUES
                    (
                        :device_id,
                        :device_name,
                        'DHT11',
                        'online',
                        :last_seen
                    )
                """),
                {
                    'device_id': device_id,
                    'device_name': device_name,
                    'last_seen': now
                }
            )

        # ----------------------------------------------------
        # Save sensor reading
        # ----------------------------------------------------

        db.session.execute(
            text("""
                INSERT INTO iot_readings
                (
                    device_id,
                    temperature,
                    humidity,
                    recorded_at
                )
                VALUES
                (
                    :device_id,
                    :temperature,
                    :humidity,
                    :recorded_at
                )
            """),
            {
                'device_id': device_id,
                'temperature': temperature,
                'humidity': humidity,
                'recorded_at': now
            }
        )

        db.session.commit()

        logger.info(
            f"IoT data received | "
            f"Device={device_id} | "
            f"Temperature={temperature} C | "
            f"Humidity={humidity}%"
        )

        return jsonify({
            'success': True,
            'message': 'IoT data received successfully',
            'device_id': device_id,
            'temperature': temperature,
            'humidity': humidity,
            'timestamp': now.strftime(
                '%Y-%m-%d %H:%M:%S'
            )
        }), 200

    except (ValueError, TypeError):

        db.session.rollback()

        return jsonify({
            'success': False,
            'error': 'Invalid sensor data'
        }), 400

    except Exception as e:

        db.session.rollback()

        logger.error(
            f"IoT API error: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================
# IOT DASHBOARD
# ============================================================

@app.route('/iot')
@login_required
def iot_dashboard():
    return render_template('iot.html')


# ============================================================
# IOT DEVICES API
# ============================================================

@app.route('/api/iot/devices', methods=['GET'])
@login_required
def get_iot_devices():

    try:

        rows = db.session.execute(
            text("""
                SELECT
                    id,
                    device_id,
                    device_name,
                    sensor_type,
                    last_seen,
                    created_at,

                    CASE
                        WHEN last_seen IS NOT NULL
                        AND TIMESTAMPDIFF(
                            SECOND,
                            last_seen,
                            UTC_TIMESTAMP()
                        ) BETWEEN 0 AND 20
                        THEN 'online'
                        ELSE 'offline'
                    END AS connection_status

                FROM iot_devices

                ORDER BY id DESC
            """)
        ).mappings().all()

        devices = []

        for row in rows:

            devices.append({
                'id': row['id'],

                'device_id':
                    row['device_id'],

                'device_name':
                    row['device_name'],

                'sensor_type':
                    row['sensor_type'],

                # IMPORTANT:
                # Old database status is NOT used.
                # Status is calculated from last_seen.
                'status':
                    row['connection_status'],

                'last_seen': (
                    row['last_seen'].isoformat()
                    if row['last_seen']
                    else None
                ),

                'created_at': (
                    row['created_at'].isoformat()
                    if row['created_at']
                    else None
                )
            })

        return jsonify({
            'success': True,
            'devices': devices
        }), 200

    except Exception as e:

        logger.error(
            f"IoT devices error: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================
# IOT READINGS API
# ============================================================

@app.route(
    '/api/iot/readings/<string:device_id>',
    methods=['GET']
)
@login_required
def get_iot_readings(device_id):

    try:

        rows = db.session.execute(
            text("""
                SELECT
                    id,
                    device_id,
                    temperature,
                    humidity,
                    recorded_at
                FROM iot_readings
                WHERE device_id = :device_id
                ORDER BY recorded_at DESC
                LIMIT 100
            """),
            {
                'device_id': device_id
            }
        ).mappings().all()

        readings = []

        for row in rows:

            readings.append({

                'id':
                    row['id'],

                'device_id':
                    row['device_id'],

                'temperature':
                    (
                        float(row['temperature'])
                        if row['temperature'] is not None
                        else None
                    ),

                'humidity':
                    (
                        float(row['humidity'])
                        if row['humidity'] is not None
                        else None
                    ),

                'recorded_at':
                    (
                        row['recorded_at'].isoformat()
                        if row['recorded_at']
                        else None
                    )
            })

        return jsonify({
            'success': True,
            'readings': readings
        }), 200

    except Exception as e:

        logger.error(
            f"IoT readings error: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================
# IOT HISTORY - CLEAR SELECTED DEVICE
# ============================================================

@app.route(
    '/api/iot/history/clear/<string:device_id>',
    methods=['DELETE']
)
@admin_required
def clear_iot_history(device_id):

    try:

        device_id = str(
            device_id
        ).strip()

        if not device_id:

            return jsonify({
                'success': False,
                'error': 'Device ID is required'
            }), 400


        # ----------------------------------------------------
        # Check device exists
        # ----------------------------------------------------

        device = db.session.execute(
            text("""
                SELECT id
                FROM iot_devices
                WHERE device_id = :device_id
                LIMIT 1
            """),
            {
                'device_id': device_id
            }
        ).first()


        if not device:

            return jsonify({
                'success': False,
                'error': 'IoT device not found'
            }), 404


        # ----------------------------------------------------
        # Delete readings only
        # Device itself will remain
        # ----------------------------------------------------

        result = db.session.execute(
            text("""
                DELETE FROM iot_readings
                WHERE device_id = :device_id
            """),
            {
                'device_id': device_id
            }
        )


        deleted_count = result.rowcount


        db.session.commit()


        logger.info(
            f"IoT history cleared | "
            f"Device={device_id} | "
            f"Rows={deleted_count}"
        )


        return jsonify({

            'success': True,

            'message':
                'IoT history cleared successfully',

            'device_id':
                device_id,

            'deleted_count':
                deleted_count

        }), 200


    except Exception as e:

        db.session.rollback()


        logger.error(
            f"Error clearing IoT history: {e}"
        )


        logger.error(
            traceback.format_exc()
        )


        return jsonify({

            'success': False,

            'error':
                str(e)

        }), 500


# ============================================================
# NUXES AI - HELPER FUNCTIONS
# ============================================================

def _safe_value(value, default='N/A'):
    """
    Safely convert a value to a short string.
    """

    if value is None or value == '':
        return default

    try:
        return str(value).strip()
    except Exception:
        return default


def _safe_number(
    value,
    decimals=1,
    default='N/A'
):
    """
    Safely format numeric values.
    """

    if value is None or value == '':
        return default

    try:
        return f'{float(value):.{decimals}f}'
    except (TypeError, ValueError):
        return _safe_value(
            value,
            default
        )


def _format_pc_context(computer):
    """
    Complete LIVE information for one PC.
    """

    if not computer:
        return (
            'No specific PC is selected.\n'
            'Do not invent or assume PC telemetry.'
        )

    try:
        settings_data = (
            get_system_settings()
            or {}
        )
    except Exception:
        settings_data = {}

    # --------------------------------------------------------
    # LAST UPDATE
    # --------------------------------------------------------

    if computer.last_update:

        try:
            last_update = (
                computer.last_update.strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            )

        except Exception:
            last_update = _safe_value(
                computer.last_update
            )

    else:
        last_update = 'N/A'

    # --------------------------------------------------------
    # LIVE CONNECTION
    # --------------------------------------------------------

    connection_status = 'offline'

    if computer.last_update:

        try:

            threshold = int(
                settings_data.get(
                    'offline_threshold',
                    20
                )
            )

            cutoff_time = (
                datetime.utcnow()
                - timedelta(
                    seconds=threshold
                )
            )

            if computer.last_update >= cutoff_time:
                connection_status = 'online'
            else:
                connection_status = 'offline'

        except Exception:
            connection_status = 'unknown'

    # --------------------------------------------------------
    # BATTERY
    # --------------------------------------------------------

    battery = 'N/A'

    if computer.battery_percent is not None:

        try:

            battery_percent = float(
                computer.battery_percent
            )

            charging = (
                'charging'
                if computer.battery_charging
                else 'not charging'
            )

            battery = (
                f'{battery_percent:.1f}% '
                f'({charging})'
            )

        except (
            TypeError,
            ValueError
        ):

            battery = _safe_value(
                computer.battery_percent
            )

    # --------------------------------------------------------
    # COMPLETE LIVE PC CONTEXT
    # --------------------------------------------------------

    return f"""
PC LIVE INFORMATION

Identity:
- Database ID: {_safe_value(computer.id)}
- Device ID: {_safe_value(computer.device_id)}
- Computer Name: {_safe_value(computer.computer_name)}
- Status: {_safe_value(computer.status)}
- Calculated Connection: {connection_status}
- Last Update: {last_update}
- IP Address: {_safe_value(computer.ip_address)}
- Operating System: {_safe_value(computer.operating_system)}

CPU:
- Usage: {_safe_number(computer.cpu_usage)}%
- Model: {_safe_value(computer.cpu_model)}
- Cores: {_safe_value(computer.cpu_cores)}
- Threads: {_safe_value(computer.cpu_threads)}

RAM:
- Usage: {_safe_number(computer.ram_usage)}%
- Total: {_safe_number(computer.ram_total)} GB
- Used: {_safe_number(computer.ram_used)} GB
- Available: {_safe_number(computer.ram_available)} GB

GPU:
- Model: {_safe_value(computer.gpu_model)}
- Usage: {_safe_number(computer.gpu_usage)}%
- VRAM: {_safe_number(computer.gpu_vram)} GB

STORAGE:
- Usage: {_safe_number(computer.disk_usage)}%
- Free: {_safe_value(computer.disk_free)}
- Model: {_safe_value(computer.storage_model)}
- Type: {_safe_value(computer.storage_type)}
- Total: {_safe_number(computer.storage_total)} GB
- Used: {_safe_number(computer.storage_used)} GB

HARDWARE:
- Manufacturer: {_safe_value(computer.manufacturer)}
- System Model: {_safe_value(computer.system_model)}
- Motherboard: {_safe_value(computer.motherboard)}
- BIOS: {_safe_value(computer.bios_version)}
- Architecture: {_safe_value(computer.architecture)}

BATTERY:
- {battery}

UPTIME:
- {_safe_value(computer.uptime)}
""".strip()


# ============================================================
# PC HISTORICAL DATA
# ============================================================

def _format_pc_history_context(computer):
    """
    Historical CPU/RAM/Disk information from History table.

    IMPORTANT:
    Historical values are NEVER treated as current values.
    """

    if not computer:

        return (
            'No PC historical data available because '
            'no specific PC is selected.'
        )

    try:

        history_rows = (
            History.query
            .filter_by(
                computer_id=computer.id
            )
            .order_by(
                History.timestamp.desc()
            )
            .limit(100)
            .all()
        )

        if not history_rows:

            return f"""
PC HISTORICAL DATA

Device ID:
{_safe_value(computer.device_id)}

No historical telemetry records were found.
""".strip()

        cpu_values = [
            float(row.cpu)
            for row in history_rows
            if row.cpu is not None
        ]

        ram_values = [
            float(row.ram)
            for row in history_rows
            if row.ram is not None
        ]

        disk_values = [
            float(row.disk)
            for row in history_rows
            if row.disk is not None
        ]

        def avg(values):

            if not values:
                return None

            return (
                sum(values)
                / len(values)
            )

        def minimum(values):

            if not values:
                return None

            return min(values)

        def maximum(values):

            if not values:
                return None

            return max(values)

        records = []

        for row in history_rows:

            timestamp = (
                row.timestamp.strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
                if row.timestamp
                else 'N/A'
            )

            records.append(
                f'- {timestamp} | '
                f'CPU: {_safe_number(row.cpu)}% | '
                f'RAM: {_safe_number(row.ram)}% | '
                f'Disk: {_safe_number(row.disk)}%'
            )

        return f"""
PC HISTORICAL DATA

Device ID:
{_safe_value(computer.device_id)}

Computer Name:
{_safe_value(computer.computer_name)}

History Records Loaded:
{len(history_rows)}

Historical CPU:
- Average: {_safe_number(avg(cpu_values))}%
- Minimum: {_safe_number(minimum(cpu_values))}%
- Maximum: {_safe_number(maximum(cpu_values))}%

Historical RAM:
- Average: {_safe_number(avg(ram_values))}%
- Minimum: {_safe_number(minimum(ram_values))}%
- Maximum: {_safe_number(maximum(ram_values))}%

Historical Disk:
- Average: {_safe_number(avg(disk_values))}%
- Minimum: {_safe_number(minimum(disk_values))}%
- Maximum: {_safe_number(maximum(disk_values))}%

Historical Records:
{chr(10).join(records)}
""".strip()

    except Exception as exc:

        logger.warning(
            'Nuxes AI history lookup failed: '
            f'{exc}'
        )

        return (
            f'Historical telemetry for '
            f'{_safe_value(computer.device_id)} '
            f'is temporarily unavailable.'
        )


# ============================================================
# COMPLETE COMPUTER DATABASE CONTEXT
# ============================================================

def _build_computer_database_context(
    selected_computer=None
):
    """
    Give Nuxes AI knowledge of registered computers.

    If a specific computer is selected, complete information
    for that computer is included.

    Otherwise a compact list of all computers is included.
    """

    try:

        if selected_computer:

            return (
                'SELECTED COMPUTER DATABASE RECORD\n\n'
                + _format_pc_context(
                    selected_computer
                )
            )

        computers = (
            Computer.query
            .order_by(
                Computer.id.asc()
            )
            .all()
        )

        if not computers:

            return (
                'COMPUTER DATABASE\n'
                'No computer records found.'
            )

        records = []

        for computer in computers:

            records.append(
                f"""
- ID: {_safe_value(computer.id)}
- Device ID: {_safe_value(computer.device_id)}
- Name: {_safe_value(computer.computer_name)}
- Status: {_safe_value(computer.status)}
- Last Update: {_safe_value(computer.last_update)}
- IP: {_safe_value(computer.ip_address)}
""".strip()
            )

        return (
            'ALL REGISTERED COMPUTERS\n\n'
            + '\n\n'.join(records)
        )

    except Exception as exc:

        logger.warning(
            'Nuxes AI computer database '
            f'lookup failed: {exc}'
        )

        return (
            'Computer database information '
            'is temporarily unavailable.'
        )


# ============================================================
# TICKETS DATABASE CONTEXT
# ============================================================

def _build_ticket_database_context(
    selected_computer=None
):
    """
    Read actual tickets from database.

    Sensitive authentication information is not included.
    """

    try:

        query = (
            Ticket.query
            .order_by(
                Ticket.id.desc()
            )
        )

        tickets = query.limit(100).all()

        if not tickets:

            return (
                'TICKETS DATABASE\n'
                'No ticket records found.'
            )

        records = []

        selected_id = (
            selected_computer.id
            if selected_computer
            else None
        )

        for ticket in tickets:

            # Try common computer relation safely.
            ticket_computer_id = getattr(
                ticket,
                'computer_id',
                None
            )

            if (
                selected_id is not None
                and ticket_computer_id is not None
                and ticket_computer_id != selected_id
            ):
                continue

            records.append(
                f"""
Ticket ID:
{_safe_value(getattr(ticket, 'id', None))}

Title:
{_safe_value(getattr(ticket, 'title', None))}

Description:
{_safe_value(getattr(ticket, 'description', None))}

Status:
{_safe_value(getattr(ticket, 'status', None))}

Priority:
{_safe_value(getattr(ticket, 'priority', None))}

Category:
{_safe_value(getattr(ticket, 'category', None))}

Computer ID:
{_safe_value(getattr(ticket, 'computer_id', None))}

Created:
{_safe_value(getattr(ticket, 'created_at', None))}

Updated:
{_safe_value(getattr(ticket, 'updated_at', None))}
""".strip()
            )

        if not records:

            return (
                'TICKETS DATABASE\n'
                'No tickets matched the selected PC.'
            )

        return (
            'TICKETS DATABASE\n\n'
            + '\n\n--------------------\n\n'
            .join(records)
        )

    except Exception as exc:

        logger.warning(
            'Nuxes AI ticket lookup failed: '
            f'{exc}'
        )

        return (
            'Ticket database information '
            'is temporarily unavailable.'
        )


# ============================================================
# MAINTENANCE DATABASE CONTEXT
# ============================================================

def _build_maintenance_database_context(
    selected_computer=None
):
    """
    Read maintenance planner records.
    """

    try:

        tasks = (
            MaintenancePlanner.query
            .order_by(
                MaintenancePlanner.id.desc()
            )
            .limit(100)
            .all()
        )

        if not tasks:

            return (
                'MAINTENANCE DATABASE\n'
                'No maintenance records found.'
            )

        records = []

        selected_id = (
            selected_computer.id
            if selected_computer
            else None
        )

        for task in tasks:

            task_computer_id = getattr(
                task,
                'computer_id',
                None
            )

            if (
                selected_id is not None
                and task_computer_id is not None
                and task_computer_id != selected_id
            ):
                continue

            fields = []

            for field_name in (
                'id',
                'computer_id',
                'title',
                'description',
                'status',
                'priority',
                'category',
                'scheduled_date',
                'created_at',
                'updated_at'
            ):

                if hasattr(
                    task,
                    field_name
                ):

                    fields.append(
                        f'{field_name}: '
                        f'{_safe_value(getattr(task, field_name))}'
                    )

            records.append(
                '\n'.join(fields)
            )

        if not records:

            return (
                'MAINTENANCE DATABASE\n'
                'No maintenance records matched '
                'the selected PC.'
            )

        return (
            'MAINTENANCE DATABASE\n\n'
            + '\n\n--------------------\n\n'
            .join(records)
        )

    except Exception as exc:

        logger.warning(
            'Nuxes AI maintenance lookup failed: '
            f'{exc}'
        )

        return (
            'Maintenance database information '
            'is temporarily unavailable.'
        )


# ============================================================
# INVENTORY DATABASE CONTEXT
# ============================================================

def _build_inventory_database_context():
    """
    Read inventory records.
    """

    try:

        items = (
            Inventory.query
            .order_by(
                Inventory.id.desc()
            )
            .limit(100)
            .all()
        )

        if not items:

            return (
                'INVENTORY DATABASE\n'
                'No inventory records found.'
            )

        records = []

        for item in items:

            fields = []

            # Read known public inventory fields dynamically.
            for field_name in (
                'id',
                'name',
                'item_name',
                'category',
                'quantity',
                'stock',
                'status',
                'serial_number',
                'model',
                'manufacturer',
                'location',
                'description',
                'created_at',
                'updated_at'
            ):

                if hasattr(
                    item,
                    field_name
                ):

                    fields.append(
                        f'{field_name}: '
                        f'{_safe_value(getattr(item, field_name))}'
                    )

            records.append(
                '\n'.join(fields)
            )

        return (
            'INVENTORY DATABASE\n\n'
            + '\n\n--------------------\n\n'
            .join(records)
        )

    except Exception as exc:

        logger.warning(
            'Nuxes AI inventory lookup failed: '
            f'{exc}'
        )

        return (
            'Inventory database information '
            'is temporarily unavailable.'
        )


# ============================================================
# IOT DATABASE CONTEXT
# ============================================================

def _build_iot_database_context(
    selected_device_id=None
):
    """
    Give Nuxes AI current and historical IoT information.

    Historical IoT readings are read-only.
    """

    try:

        if selected_device_id:

            device_row = db.session.execute(
                text("""
                    SELECT
                        device_id,
                        device_name,
                        sensor_type,
                        status,
                        last_seen,
                        created_at
                    FROM iot_devices
                    WHERE device_id = :device_id
                    LIMIT 1
                """),
                {
                    'device_id': selected_device_id
                }
            ).mappings().first()

            if not device_row:

                return (
                    f'IOT DATABASE\n'
                    f'No device found for '
                    f'{selected_device_id}.'
                )

            readings = db.session.execute(
                text("""
                    SELECT
                        temperature,
                        humidity,
                        recorded_at
                    FROM iot_readings
                    WHERE device_id = :device_id
                    ORDER BY recorded_at DESC
                    LIMIT 100
                """),
                {
                    'device_id': selected_device_id
                }
            ).mappings().all()

            reading_lines = []

            for row in readings:

                reading_lines.append(
                    f"- {row['recorded_at']} | "
                    f"Temperature: "
                    f"{_safe_value(row['temperature'])} °C | "
                    f"Humidity: "
                    f"{_safe_value(row['humidity'])} %"
                )

            return f"""
IOT DATABASE

Device:
- ID: {_safe_value(device_row['device_id'])}
- Name: {_safe_value(device_row['device_name'])}
- Sensor: {_safe_value(device_row['sensor_type'])}
- Status: {_safe_value(device_row['status'])}
- Last Seen: {_safe_value(device_row['last_seen'])}
- Created: {_safe_value(device_row['created_at'])}

Historical Readings Loaded:
{len(readings)}

Readings:
{chr(10).join(reading_lines) if reading_lines else 'No readings found.'}
""".strip()

        # ----------------------------------------------------
        # ALL DEVICES
        # ----------------------------------------------------

        devices = db.session.execute(
            text("""
                SELECT
                    device_id,
                    device_name,
                    sensor_type,
                    status,
                    last_seen,
                    created_at
                FROM iot_devices
                ORDER BY id DESC
            """)
        ).mappings().all()

        if not devices:

            return (
                'IOT DATABASE\n'
                'No IoT devices found.'
            )

        records = []

        for device in devices:

            records.append(
                f"""
- Device ID: {_safe_value(device['device_id'])}
- Name: {_safe_value(device['device_name'])}
- Sensor: {_safe_value(device['sensor_type'])}
- Status: {_safe_value(device['status'])}
- Last Seen: {_safe_value(device['last_seen'])}
""".strip()
            )

        return (
            'IOT DEVICES DATABASE\n\n'
            + '\n\n'.join(records)
        )

    except Exception as exc:

        logger.warning(
            'Nuxes AI IoT database lookup failed: '
            f'{exc}'
        )

        return (
            'IoT database information '
            'is temporarily unavailable.'
        )


# ============================================================
# DATABASE SUMMARY
# ============================================================

def _build_nuxes_database_summary():
    """
    Actual database counts.
    """

    summary = []

    models = [
        ('PC systems', Computer),
        ('PC history records', History),
        ('maintenance tasks', MaintenancePlanner),
        ('tickets', Ticket),
        ('ticket comments', TicketComment),
        ('ticket activities', TicketActivity),
        ('inventory items', Inventory),
        ('accounts', Account),
    ]

    for label, model in models:

        try:

            total = model.query.count()

            summary.append(
                f'- {label}: {int(total)}'
            )

        except Exception as exc:

            logger.warning(
                f'Nuxes AI count failed for '
                f'{label}: {exc}'
            )

            summary.append(
                f'- {label}: unavailable'
            )

    # --------------------------------------------------------
    # IOT DEVICES
    # --------------------------------------------------------

    try:

        row = db.session.execute(
            text("""
                SELECT COUNT(*) AS total
                FROM iot_devices
            """)
        ).mappings().first()

        total = (
            row['total']
            if row
            and row.get('total') is not None
            else 0
        )

        summary.append(
            f'- IoT devices: {int(total)}'
        )

    except Exception:

        summary.append(
            '- IoT devices: unavailable'
        )

    # --------------------------------------------------------
    # IOT READINGS
    # --------------------------------------------------------

    try:

        row = db.session.execute(
            text("""
                SELECT COUNT(*) AS total
                FROM iot_readings
            """)
        ).mappings().first()

        total = (
            row['total']
            if row
            and row.get('total') is not None
            else 0
        )

        summary.append(
            f'- IoT readings: {int(total)}'
        )

    except Exception:

        summary.append(
            '- IoT readings: unavailable'
        )

    return '\n'.join(summary)


# ============================================================
# SETTINGS CONTEXT
# ============================================================

def _build_nuxes_settings_context(
    settings_data
):

    settings_data = (
        settings_data
        or {}
    )

    return f"""
MONITORING SETTINGS

- Refresh interval:
  {_safe_value(settings_data.get('refresh_interval'))} seconds

- Offline threshold:
  {_safe_value(settings_data.get('offline_threshold'))} seconds

- CPU warning / critical:
  {_safe_value(settings_data.get('cpu_warning'))}% /
  {_safe_value(settings_data.get('cpu_critical'))}%

- RAM warning / critical:
  {_safe_value(settings_data.get('ram_warning'))}% /
  {_safe_value(settings_data.get('ram_critical'))}%

- Disk warning / critical:
  {_safe_value(settings_data.get('disk_warning'))}% /
  {_safe_value(settings_data.get('disk_critical'))}%
""".strip()


# ============================================================
# LANGUAGE
# ============================================================

def _get_nuxes_language_context(
    language
):

    language_data = (
        NUXES_AI_LANGUAGES.get(
            language,
            NUXES_AI_LANGUAGES['en']
        )
    )

    return (
        language_data['name'],
        language_data['instruction']
    )


# ============================================================
# NUXES AI PROMPT
# ============================================================

def _build_nuxes_ai_prompt(
    question,
    language,
    sensor_context,
    pc_context,
    pc_history_context,
    computer_database_context,
    ticket_database_context,
    maintenance_database_context,
    inventory_database_context,
    iot_database_context,
    database_summary,
    settings_data
):
    """
    Complete Nuxes AI prompt.

    Nuxes has two modes:

    1. Nexus Core database-aware mode
    2. General AI mode for outside questions

    It is NOT restricted to Nexus Core questions.
    """

    language_name, language_instruction = (
        _get_nuxes_language_context(
            language
        )
    )

    settings_context = (
        _build_nuxes_settings_context(
            settings_data
        )
    )

    return f"""
You are Nuxes AI.

You are the intelligent assistant inside Nexus Core, but you are
NOT restricted to Nexus Core topics.

You can answer:
- Nexus Core questions
- PC monitoring questions
- Database questions
- IoT questions
- Programming questions
- Networking questions
- Cybersecurity concepts
- Linux / Windows questions
- Python / Flask questions
- Java questions
- MySQL / SQL questions
- MongoDB questions
- ESP32 / electronics questions
- College / viva questions
- General technical questions
- General knowledge questions
- Other normal user questions

============================================================
VERY IMPORTANT: DATABASE SOURCE OF TRUTH
============================================================

When the question is about Nexus Core or its stored data:

USE THE SUPPLIED DATABASE CONTEXT AS THE SOURCE OF TRUTH.

Never invent a database value.

If a database field is N/A, unavailable or missing, say so.

Do not convert historical data into live data.

Clearly distinguish:
- LIVE
- HISTORICAL
- DATABASE RECORD
- CONFIGURATION

============================================================
PROJECT KNOWLEDGE
============================================================

Nexus Core is a Flask-based PC Digital Twin, monitoring,
IoT monitoring and predictive-maintenance platform.

Technology:
- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- MySQL
- PyMySQL
- psutil
- HTML
- CSS
- JavaScript
- Bootstrap
- Font Awesome
- Google Gemini
- Docker
- Gunicorn
- GitHub
- Render

Core models:
- Computer
- History
- Account
- Ticket
- TicketComment
- TicketActivity
- MaintenancePlanner
- Inventory

PC telemetry:
- CPU
- RAM
- GPU
- Disk
- IP
- OS
- Uptime
- Hardware
- BIOS
- Motherboard
- Battery

IoT:
- iot_devices
- iot_readings
- Temperature
- Humidity
- Recorded timestamps

============================================================
DATABASE SUMMARY
============================================================

{database_summary}

============================================================
SELECTED PC LIVE DATA
============================================================

{pc_context}

============================================================
SELECTED PC HISTORICAL DATA
============================================================

{pc_history_context}

============================================================
COMPUTER DATABASE
============================================================

{computer_database_context}

============================================================
TICKET DATABASE
============================================================

{ticket_database_context}

============================================================
MAINTENANCE DATABASE
============================================================

{maintenance_database_context}

============================================================
INVENTORY DATABASE
============================================================

{inventory_database_context}

============================================================
IOT DATABASE
============================================================

{iot_database_context}

============================================================
SELECTED IOT LIVE DATA
============================================================

{sensor_context}

============================================================
SYSTEM SETTINGS
============================================================

{settings_context}

============================================================
USER QUESTION
============================================================

{question}

============================================================
PC RULES
============================================================

If the user mentions:
- PC001
- PC002
- PC003
- or another PC device ID

find and use that exact computer when available.

If the selected PC exists:

Explain:
- identity
- computer name
- connection
- last update
- IP
- OS
- CPU
- RAM
- GPU
- storage
- motherboard
- BIOS
- architecture
- battery
- uptime
- historical CPU
- historical RAM
- historical disk
- related tickets
- related maintenance records

when relevant to the question.

If the PC is offline:
DO NOT say its data does not exist.

Instead say:
- current connection is offline
- latest available telemetry
- last update time
- historical data that is available

Never claim old telemetry is live.

============================================================
IOT RULES
============================================================

Keep PC monitoring and IoT monitoring separate.

For IoT:
- distinguish current/latest reading from history
- use actual temperature/humidity values
- use actual timestamps
- never fabricate readings
- old readings must be described as historical

============================================================
GENERAL AI RULE
============================================================

The user may ask ANY normal question.

If the question is unrelated to Nexus Core:

DO NOT say:
"I can only answer Nexus Core questions."

Instead answer the question normally using your general
knowledge.

If the question requires current information that you do not
have, clearly state the limitation.

Do not force every question into the Nexus Core database.

============================================================
CODE RULE
============================================================

If the user asks for code:

- give working code
- explain briefly if needed
- preserve the user's existing architecture when the question
  is about Nexus Core
- do not invent unavailable project files
- do not expose secrets

============================================================
SECURITY RULE
============================================================

NEVER reveal:
- GEMINI_API_KEY
- API keys
- passwords
- password hashes
- database passwords
- SQL credentials
- Flask secret keys
- session secrets
- authentication tokens
- internal security credentials

Database awareness does NOT mean exposing sensitive secrets.

============================================================
LANGUAGE
============================================================

Selected language:
{language_name}

Instruction:
{language_instruction}

Answer in the selected language.

Technical names, commands, code, API paths and model names can
remain in English when required.

============================================================
ANSWER STYLE
============================================================

For simple questions:
Give a direct answer.

For technical questions:
Give explanation + practical steps.

For troubleshooting:
Give:
1. likely cause
2. fix
3. verification

For database questions:
Use actual database context.

For PC questions:
Separate LIVE and HISTORICAL information.

For college/viva questions:
Use simple understandable wording.

Do not unnecessarily limit the answer to 3-6 sentences.
Give as much detail as the user's question requires.

============================================================
FINAL INSTRUCTION
============================================================

Answer the user's actual question directly.

Do not refuse a normal outside question simply because it is
outside Nexus Core.

For Nexus Core data, trust the supplied database context.

For general questions, answer normally.

Never fabricate project/database values.
""".strip()


# ============================================================
# NUXES AI API
# ============================================================

@app.route(
    '/api/ai',
    methods=['POST']
)
@login_required
def nuxes_ai():
    """
    Complete database-aware + general-purpose Nuxes AI.
    """

    try:

        # ====================================================
        # GEMINI CHECK
        # ====================================================

        if gemini_client is None:

            return jsonify({
                'success': False,
                'error': (
                    'Nuxes AI is not configured. '
                    'Please configure GEMINI_API_KEY.'
                )
            }), 503

        # ====================================================
        # REQUEST
        # ====================================================

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        question = str(
            data.get(
                'question',
                ''
            )
        ).strip()

        device_id = str(
            data.get(
                'device_id',
                ''
            )
        ).strip()

        computer_id_raw = (
            data.get(
                'computer_id'
            )
        )

        language = str(
            data.get(
                'language',
                'en'
            )
        ).strip().lower()

        # ====================================================
        # VALIDATION
        # ====================================================

        if not question:

            return jsonify({
                'success': False,
                'error': 'Question is required.'
            }), 400

        if len(question) > 5000:

            return jsonify({
                'success': False,
                'error': (
                    'Question is too long. '
                    'Please keep it under 5000 characters.'
                )
            }), 400

        if language not in NUXES_AI_LANGUAGES:

            language = 'en'

        # ====================================================
        # SELECTED PC
        # ====================================================

        selected_computer = None

        # ----------------------------------------------------
        # 1. Explicit computer ID
        # ----------------------------------------------------

        if computer_id_raw not in (
            None,
            ''
        ):

            try:

                selected_computer = (
                    db.session.get(
                        Computer,
                        int(
                            computer_id_raw
                        )
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                selected_computer = None

        # ----------------------------------------------------
        # 2. device_id
        # ----------------------------------------------------

        if (
            selected_computer is None
            and device_id
        ):

            try:

                selected_computer = (
                    Computer.query
                    .filter_by(
                        device_id=device_id
                    )
                    .first()
                )

            except Exception as exc:

                logger.warning(
                    'Nuxes AI PC lookup failed: '
                    f'{exc}'
                )

        # ----------------------------------------------------
        # 3. PC mentioned in question
        # ----------------------------------------------------

        if selected_computer is None:

            try:

                import re

                pc_match = re.search(
                    r'\bPC\d{3,}\b',
                    question,
                    re.IGNORECASE
                )

                if pc_match:

                    requested_pc = (
                        pc_match
                        .group(0)
                        .upper()
                    )

                    selected_computer = (
                        Computer.query
                        .filter(
                            db.func.upper(
                                Computer.device_id
                            ) == requested_pc
                        )
                        .first()
                    )

                    if selected_computer:

                        logger.info(
                            'Nuxes AI selected PC from question: '
                            f'{selected_computer.device_id}'
                        )

            except Exception as exc:

                logger.warning(
                    'Nuxes AI question PC lookup failed: '
                    f'{exc}'
                )

        # ----------------------------------------------------
        # 4. If only one PC exists, automatically use it
        # ----------------------------------------------------

        if selected_computer is None:

            try:

                computers = (
                    Computer.query
                    .order_by(
                        Computer.id.asc()
                    )
                    .all()
                )

                if len(computers) == 1:

                    selected_computer = (
                        computers[0]
                    )

                    logger.info(
                        'Nuxes AI automatically selected '
                        f'{selected_computer.device_id}'
                    )

            except Exception as exc:

                logger.warning(
                    'Nuxes AI automatic PC selection '
                    f'failed: {exc}'
                )

        # ====================================================
        # PC LIVE DATA
        # ====================================================

        pc_context = (
            _format_pc_context(
                selected_computer
            )
        )

        # ====================================================
        # PC HISTORY
        # ====================================================

        pc_history_context = (
            _format_pc_history_context(
                selected_computer
            )
        )

        # ====================================================
        # COMPUTER DATABASE
        # ====================================================

        computer_database_context = (
            _build_computer_database_context(
                selected_computer
            )
        )

        # ====================================================
        # TICKETS
        # ====================================================

        ticket_database_context = (
            _build_ticket_database_context(
                selected_computer
            )
        )

        # ====================================================
        # MAINTENANCE
        # ====================================================

        maintenance_database_context = (
            _build_maintenance_database_context(
                selected_computer
            )
        )

        # ====================================================
        # INVENTORY
        # ====================================================

        inventory_database_context = (
            _build_inventory_database_context()
        )

        # ====================================================
        # IOT DATABASE
        # ====================================================

        iot_database_context = (
            _build_iot_database_context(
                device_id
                if device_id
                else None
            )
        )

        # ====================================================
        # IOT LIVE CONTEXT
        # ====================================================

        sensor_context = (
            'No specific IoT device is selected.'
        )

        if device_id:

            try:

                row = db.session.execute(
                    text("""
                        SELECT
                            d.device_id,
                            d.device_name,
                            d.sensor_type,
                            d.status,
                            d.last_seen,
                            r.temperature,
                            r.humidity,
                            r.recorded_at
                        FROM iot_devices d
                        LEFT JOIN iot_readings r
                            ON r.device_id =
                               d.device_id
                            AND r.recorded_at = (
                                SELECT MAX(
                                    r2.recorded_at
                                )
                                FROM iot_readings r2
                                WHERE r2.device_id =
                                      d.device_id
                            )
                        WHERE d.device_id =
                              :device_id
                        LIMIT 1
                    """),
                    {
                        'device_id':
                            device_id
                    }
                ).mappings().first()

                if row:

                    sensor_context = f"""
SELECTED IOT DEVICE

- Device ID:
  {_safe_value(row['device_id'])}

- Device Name:
  {_safe_value(row['device_name'])}

- Sensor Type:
  {_safe_value(row['sensor_type'])}

- Status:
  {_safe_value(row['status'])}

- Last Seen:
  {_safe_value(row['last_seen'])}

- Latest Temperature:
  {_safe_value(row['temperature'])} °C

- Latest Humidity:
  {_safe_value(row['humidity'])} %

- Latest Reading:
  {_safe_value(row['recorded_at'])}
""".strip()

                else:

                    sensor_context = f"""
SELECTED IOT DEVICE

Requested Device:
{device_id}

No matching IoT device was found.
Do not invent sensor values.
""".strip()

            except Exception as exc:

                logger.warning(
                    'Nuxes AI IoT live lookup failed: '
                    f'{exc}'
                )

                sensor_context = (
                    'IoT live information is '
                    'temporarily unavailable.'
                )

        # ====================================================
        # DATABASE SUMMARY
        # ====================================================

        database_summary = (
            _build_nuxes_database_summary()
        )

        # ====================================================
        # SETTINGS
        # ====================================================

        try:

            settings_data = (
                get_system_settings()
                or {}
            )

        except Exception as exc:

            logger.warning(
                'Nuxes AI settings lookup failed: '
                f'{exc}'
            )

            settings_data = {}

        # ====================================================
        # BUILD PROMPT
        # ====================================================

        prompt = _build_nuxes_ai_prompt(

            question=question,

            language=language,

            sensor_context=sensor_context,

            pc_context=pc_context,

            pc_history_context=(
                pc_history_context
            ),

            computer_database_context=(
                computer_database_context
            ),

            ticket_database_context=(
                ticket_database_context
            ),

            maintenance_database_context=(
                maintenance_database_context
            ),

            inventory_database_context=(
                inventory_database_context
            ),

            iot_database_context=(
                iot_database_context
            ),

            database_summary=(
                database_summary
            ),

            settings_data=settings_data
        )

        # ====================================================
        # GEMINI REQUEST
        # ====================================================

        last_error = None

        for attempt in range(2):

            try:

                response = (
                    gemini_client
                    .models
                    .generate_content(

                        model=NEXUS_AI_MODEL,

                        contents=prompt,

                        config=(
                            types
                            .GenerateContentConfig(
                                max_output_tokens=1200
                            )
                        )
                    )
                )

                answer = ''

                if response is not None:

                    try:

                        answer = (
                            response.text
                            or ''
                        ).strip()

                    except Exception:

                        answer = ''

                if answer:

                    return jsonify({

                        'success': True,

                        'answer': answer,

                        'model': (
                            NEXUS_AI_MODEL
                        ),

                        'language': language,

                        'language_name': (
                            NUXES_AI_LANGUAGES[
                                language
                            ]['name']
                        )

                    }), 200

                last_error = (
                    'Gemini returned '
                    'an empty response.'
                )

            except Exception as exc:

                last_error = exc

                logger.warning(
                    'Nuxes AI attempt '
                    f'{attempt + 1}/2 failed: '
                    f'{exc}'
                )

                if attempt == 0:

                    try:
                        time.sleep(0.7)
                    except Exception:
                        pass

        # ====================================================
        # GEMINI FAILED
        # ====================================================

        logger.error(
            'Nuxes AI failed after retries: '
            f'{last_error}'
        )

        return jsonify({
            'success': False,
            'error': (
                'AI is temporarily unavailable. '
                'Please try again in a few seconds.'
            )
        }), 503

    # ========================================================
    # UNEXPECTED ERROR
    # ========================================================

    except Exception as exc:

        try:
            db.session.rollback()
        except Exception:
            pass

        logger.error(
            f'Nuxes AI route error: {exc}'
        )

        logger.error(
            traceback.format_exc()
        )

        return jsonify({
            'success': False,
            'error': (
                'AI is temporarily unavailable. '
                'Please try again.'
            )
        }), 503

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':

    print(
        '\n' + '=' * 60
    )

    print(
        '🚀 Starting Nexus Core '
        'with Complete Features'
    )

    print(
        '=' * 60
    )

    print(
        f'📊 Database: '
        f'{Config.MYSQL_DATABASE}'
    )

    print(
        f'🌐 Server: '
        f'http://localhost:{Config.PORT}'
    )

    print(
        '🔑 Default Login: '
        'admin / admin123'
    )

    print(
        '=' * 60
    )

    print(
        '📌 Available Pages:'
    )

    print(
        '   - Dashboard: /'
    )

    print(
        '   - Login: /login'
    )

    print(
        '   - Register: /register'
    )

    print(
        '   - Forgot Password: /forgot-password'
    )

    print(
        '   - Systems: /systems'
    )

    print(
        '   - Computers: /computers '
        '(redirects to /systems)'
    )

    print(
        '   - Settings: /settings'
    )

    print(
        '   - QR Codes: /qr'
    )

    print(
        '   - QR Scanner: /qr-scanner'
    )

    print(
        '   - Predictions: /predictions'
    )

    print(
        '   - Maintenance: /maintenance'
    )

    print(
        '   - Tickets: /tickets'
    )

    print(
        '   - Alerts: /alerts'
    )

    print(
        '   - Inventory: /inventory'
    )

    print(
        '=' * 60 + '\n'
    )

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
