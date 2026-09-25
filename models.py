from database import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Account(db.Model):
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    security_question = db.Column(db.String(255), nullable=True)
    security_answer_hash = db.Column(db.String(255), nullable=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None
        }

class Computer(db.Model):
    __tablename__ = 'computers'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), unique=True, nullable=False)
    computer_name = db.Column(db.String(100), nullable=False, unique=True)
    ip_address = db.Column(db.String(45), nullable=False)
    cpu_usage = db.Column(db.Float, default=0.0)
    # CPU Hardware
    cpu_model = db.Column(db.String(200), default='Unknown')
    cpu_cores = db.Column(db.Integer, default=0)
    cpu_threads = db.Column(db.Integer, default=0)
    
    # RAM Hardware
    ram_total = db.Column(db.Float, default=0.0)
    ram_used = db.Column(db.Float, default=0.0)
    ram_available = db.Column(db.Float, default=0.0)
    
    # GPU Hardware
    gpu_model = db.Column(db.String(200), default='Unknown')
    gpu_vram = db.Column(db.Float, default=0.0)
    gpu_usage = db.Column(db.Float, default=0.0)
    
    # Storage Hardware
    storage_model = db.Column(db.String(200), default='Unknown')
    storage_type = db.Column(db.String(50), default='Unknown')
    storage_total = db.Column(db.Float, default=0.0)
    storage_used = db.Column(db.Float, default=0.0)
    
    # System Hardware
    manufacturer = db.Column(db.String(200), default='Unknown')
    system_model = db.Column(db.String(200), default='Unknown')
    motherboard = db.Column(db.String(200), default='Unknown')
    bios_version = db.Column(db.String(200), default='Unknown')
    architecture = db.Column(db.String(50), default='Unknown')
    
    # Battery
    battery_percent = db.Column(db.Float, nullable=True)
    battery_charging = db.Column(db.Boolean, nullable=True)
    ram_usage = db.Column(db.Float, default=0.0)
    disk_usage = db.Column(db.Float, default=0.0)
    disk_free = db.Column(db.String(20), default='0 GB')
    uptime = db.Column(db.String(50), default='0 minutes')
    operating_system = db.Column(db.String(100), default='Unknown')
    status = db.Column(db.String(20), default='online')
    last_update = db.Column(db.DateTime, default=datetime.utcnow)
    qr_code = db.Column(db.Text, nullable=True)
    
    history = db.relationship('History', lazy=True, cascade='all, delete-orphan')
    
    @staticmethod
    def generate_device_id():
        prefix = "PC"
        last_computer = Computer.query.order_by(Computer.id.desc()).first()
        if last_computer:
            try:
                last_num = int(last_computer.device_id[2:])
                new_num = last_num + 1
            except:
                new_num = 1
        else:
            new_num = 1
        return f"{prefix}{str(new_num).zfill(3)}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'computer_name': self.computer_name,
            'ip_address': self.ip_address,
            'cpu_usage': self.cpu_usage,
             'cpu_model': self.cpu_model,
            'cpu_cores': self.cpu_cores,
            'cpu_threads': self.cpu_threads,
            
            'ram_total': self.ram_total,
            'ram_used': self.ram_used,
            'ram_available': self.ram_available,
            
            'gpu_model': self.gpu_model,
            'gpu_vram': self.gpu_vram,
            'gpu_usage': self.gpu_usage,
            
            'storage_model': self.storage_model,
            'storage_type': self.storage_type,
            'storage_total': self.storage_total,
            'storage_used': self.storage_used,
            
            'manufacturer': self.manufacturer,
            'system_model': self.system_model,
            'motherboard': self.motherboard,
            'bios_version': self.bios_version,
            'architecture': self.architecture,
            
            'battery_percent': self.battery_percent,
            'battery_charging': self.battery_charging,
            'ram_usage': self.ram_usage,
            'disk_usage': self.disk_usage,
            'disk_free': self.disk_free,
            'uptime': self.uptime,
            'operating_system': self.operating_system,
            'status': self.status,
            'last_update': self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else None,
            'qr_code': self.qr_code
        }

class History(db.Model):
    __tablename__ = 'history'
    
    id = db.Column(db.Integer, primary_key=True)
    computer_id = db.Column(db.Integer, db.ForeignKey('computers.id'), nullable=False)
    cpu = db.Column(db.Float, default=0.0)
    ram = db.Column(db.Float, default=0.0)
    disk = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    computer = db.relationship('Computer', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'computer_id': self.computer_id,
            'cpu': self.cpu,
            'ram': self.ram,
            'disk': self.disk,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        }

# ==========================================
# COMPLETE TICKET MODEL WITH PROGRESS
# ==========================================

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')
    priority = db.Column(db.String(20), default='medium')
    category = db.Column(db.String(50), default='General')
    
    computer_id = db.Column(db.Integer, db.ForeignKey('computers.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    
    due_date = db.Column(db.DateTime, nullable=True)
    attachment = db.Column(db.String(255), nullable=True)
    response_time = db.Column(db.Integer, nullable=True)
    resolution_time = db.Column(db.Integer, nullable=True)
    pinned = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    
    # ==========================================
    # PROGRESS TRACKING - ADD THESE LINES
    # ==========================================
    progress = db.Column(db.Integer, default=0)  # 0-100 percentage
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    computer = db.relationship('Computer', lazy=True)
    creator = db.relationship('Account', foreign_keys=[created_by], lazy=True)
    assignee = db.relationship('Account', foreign_keys=[assigned_to], lazy=True)
    
    comments = db.relationship('TicketComment', lazy=True, cascade='all, delete-orphan')
    activities = db.relationship('TicketActivity', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'category': self.category,
            'computer_id': self.computer_id,
            'computer_name': self.computer.computer_name if self.computer else None,
            'device_id': self.computer.device_id if self.computer else None,
            'created_by': self.created_by,
            'created_by_name': self.creator.username if self.creator else None,
            'assigned_to': self.assigned_to,
            'assigned_to_name': self.assignee.username if self.assignee else None,
            'due_date': self.due_date.strftime('%Y-%m-%d %H:%M:%S') if self.due_date else None,
            # ==========================================
            # PROGRESS FIELDS - ADD THESE
            # ==========================================
            'progress': self.progress,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M:%S') if self.started_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
            'resolved_at': self.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if self.resolved_at else None,
            'comments': [c.to_dict() for c in self.comments],
            'activities': [a.to_dict() for a in self.activities]
        }

class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('Account', lazy=True)
    ticket = db.relationship('Ticket', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'comment': self.comment,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class TicketActivity(db.Model):
    __tablename__ = 'ticket_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('Account', lazy=True)
    ticket = db.relationship('Ticket', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'username': self.user.username if self.user else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class TicketAssignee(db.Model):
    __tablename__ = 'ticket_assignees'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('Account', lazy=True)
    ticket = db.relationship('Ticket', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'assigned_at': self.assigned_at.strftime('%Y-%m-%d %H:%M:%S') if self.assigned_at else None
        }

class TicketTime(db.Model):
    __tablename__ = 'ticket_time'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    hours = db.Column(db.Numeric(5,2), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('Account', lazy=True)
    ticket = db.relationship('Ticket', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'hours': float(self.hours),
            'description': self.description,
            'username': self.user.username if self.user else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class MaintenancePlanner(db.Model):
    __tablename__ = 'maintenance_planner'

    id = db.Column(db.Integer, primary_key=True)

    computer_id = db.Column(
        db.Integer,
        db.ForeignKey('computers.id'),
        nullable=True
    )

    system_name = db.Column(db.String(100), nullable=False)
    component = db.Column(db.String(100), nullable=False)
    task = db.Column(db.String(255), nullable=False)

    scheduled_date = db.Column(db.Date, nullable=True)

    priority = db.Column(
        db.String(20),
        default='Medium'
    )

    estimated_cost = db.Column(
        db.Numeric(10, 2),
        default=0.00
    )

    replacement_date = db.Column(
        db.Date,
        nullable=True
    )

    status = db.Column(
        db.String(30),
        default='Scheduled'
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    computer = db.relationship(
        'Computer',
        lazy=True
    )

    def to_dict(self):
        return {
            'id': self.id,
            'computer_id': self.computer_id,
            'system_name': self.system_name,
            'component': self.component,
            'task': self.task,

            'scheduled_date': (
                self.scheduled_date.strftime('%Y-%m-%d')
                if self.scheduled_date else None
            ),

            'priority': self.priority,

            'estimated_cost': float(
                self.estimated_cost or 0
            ),

            'replacement_date': (
                self.replacement_date.strftime('%Y-%m-%d')
                if self.replacement_date else None
            ),

            'status': self.status,
            'notes': self.notes,

            'created_at': (
                self.created_at.strftime('%Y-%m-%d %H:%M:%S')
                if self.created_at else None
            )
        }

class Inventory(db.Model):
    __tablename__ = 'inventory'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    component_type = db.Column(
        db.String(50),
        nullable=False
    )

    component_name = db.Column(
        db.String(100),
        nullable=False
    )

    manufacturer = db.Column(
        db.String(100),
        nullable=True
    )

    model = db.Column(
        db.String(100),
        nullable=True
    )

    serial_number = db.Column(
        db.String(100),
        nullable=True
    )

    system_name = db.Column(
        db.String(100),
        nullable=True
    )

    quantity = db.Column(
        db.Integer,
        default=1
    )

    status = db.Column(
        db.String(30),
        default='Good'
    )

    purchase_date = db.Column(
        db.Date,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.component_type,
            'name': self.component_name,
            'manufacturer': self.manufacturer or '-',
            'model': self.model or '-',
            'serial': self.serial_number or '-',
            'system': self.system_name or '-',
            'quantity': self.quantity or 1,
            'status': self.status or 'Good',
            'purchaseDate': (
                self.purchase_date.strftime('%Y-%m-%d')
                if self.purchase_date else '-'
            ),
            'created_at': (
                self.created_at.strftime('%Y-%m-%d %H:%M:%S')
                if self.created_at else None
            )
        }