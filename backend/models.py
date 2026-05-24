# backend/models.py
from datetime import datetime
from flask import current_app
from sqlalchemy import text
import bcrypt
import json

from backend.database import db

# ================== SQLAlchemy Models ==================

class Tenant(db.Model):
    __tablename__ = 'tenants'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(50), nullable=False, default='basic')  # basic, standard, premium
    max_storage_bytes = db.Column(db.BigInteger, default=1073741824)  # 1GB default
    used_storage_bytes = db.Column(db.BigInteger, default=0)
    status = db.Column(db.String(50), default='active')  # active, suspended, cancelled
    stripe_customer_id = db.Column(db.String(255), nullable=True, index=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    managers = db.relationship('Manager', back_populates='tenant', cascade='all, delete-orphan')
    
    def to_dict(self, include_password=False):
        data = {
            'id': self.id,
            'company_name': self.company_name,
            'email': self.email,
            'plan': self.plan,
            'max_storage_bytes': self.max_storage_bytes,
            'used_storage_bytes': self.used_storage_bytes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_password:
            data['password_hash'] = self.password_hash
        return data
    
    def check_storage_limit(self, additional_bytes=0):
        """Check if tenant can use additional storage"""
        return (self.used_storage_bytes + additional_bytes) <= self.max_storage_bytes
    
    def get_storage_usage_percent(self):
        """Get storage usage as percentage"""
        if self.max_storage_bytes == 0:
            return 0
        return (self.used_storage_bytes / self.max_storage_bytes) * 100


class Manager(db.Model):
    __tablename__ = 'managers'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    # Note: username has index=True for performance, but uniqueness is enforced by
    # the composite UniqueConstraint('tenant_id', 'username') below, NOT by a unique index on username alone
    username = db.Column(db.String(50), nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(100), nullable=True)  # Manager location
    is_super_admin = db.Column(db.Boolean, default=False)  # True for tenant's super admin
    is_admin = db.Column(db.Boolean, default=False)  # True for admin users
    regions = db.Column(db.Text, nullable=True)  # JSON array of regions assigned to admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = db.relationship('Tenant', back_populates='managers')
    # Stores relationship - composite join on tenant_id + username
    # Note: No back_populates to avoid SQLAlchemy issues with composite keys
    # Use get_stores(manager_username=..., tenant_id=...) function instead
    
    # Composite unique constraint on tenant_id + username
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'username', name='uq_tenant_manager_username'),
    )
    
    def to_dict(self, include_password=False):
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'username': self.username,
            'location': self.location,
            'is_super_admin': self.is_super_admin,
            'is_admin': self.is_admin,
            'regions': self.get_regions(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_password:
            data['password'] = self.password
        return data
    
    def get_regions(self):
        """Parse JSON regions field"""
        try:
            return json.loads(self.regions) if self.regions else []
        except:
            return []
    
    def set_regions(self, regions_list):
        """Serialize regions to JSON"""
        self.regions = json.dumps(regions_list) if regions_list else None


class Store(db.Model):
    __tablename__ = 'stores'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    username = db.Column(db.String(50), nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    total_boxes = db.Column(db.Integer, default=0)
    manager_username = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    allowed_ip = db.Column(db.String(45), nullable=True)
    opening_time = db.Column(db.String(5), nullable=True)  # Format: "HH:MM" (24-hour)
    closing_time = db.Column(db.String(5), nullable=True)  # Format: "HH:MM" (24-hour)
    
    # Foreign key relationship to Manager (composite: tenant_id + username)
    # Note: We'll handle this in application logic since SQLAlchemy doesn't support composite FKs directly
    
    # Relationships
    tenant = db.relationship('Tenant')
    # Manager relationship - composite join handled in application code
    # Use get_manager_by_username(username, tenant_id=...) function instead
    # Inventory, InventoryHistory, and EOD relationships - composite join on tenant_id + store_id (name)
    # Note: Using string-based primaryjoin since store_id references Store.name, not Store.id
    # Note: Relationships to Inventory, InventoryHistory, and EOD are handled via queries
    # Using get_inventory(tenant_id=..., store_id=...) etc. functions
    # No SQLAlchemy relationships defined to avoid composite key issues
    
    # Composite unique constraint on tenant_id + name and tenant_id + username
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_tenant_store_name'),
        db.UniqueConstraint('tenant_id', 'username', name='uq_tenant_store_username'),
    )
    
    def to_dict(self, include_password=False):
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'username': self.username,
            'total_boxes': self.total_boxes,
            'manager_username': self.manager_username,
            'allowed_ip': self.allowed_ip,
            'opening_time': self.opening_time,
            'closing_time': self.closing_time,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_password:
            data['password'] = self.password
        return data


class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    store_id = db.Column(db.String(100), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    hourly_pay = db.Column(db.Float, nullable=True)
    active = db.Column(db.Boolean, default=True)
    face_registered = db.Column(db.Boolean, default=False)
    face_descriptor = db.Column(db.Text, nullable=True)  # JSON array
    face_descriptors = db.Column(db.Text, nullable=True)  # JSON array of arrays
    face_image = db.Column(db.Text, nullable=True)  # Base64 encoded image
    face_registered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = db.relationship('Tenant')
    
    # Relationships
    timeclock_entries = db.relationship('TimeClock', back_populates='employee', cascade='all, delete-orphan')
    
    def get_face_descriptor(self):
        """Parse JSON face_descriptor field"""
        try:
            return json.loads(self.face_descriptor) if self.face_descriptor else None
        except:
            return None
    
    def set_face_descriptor(self, descriptor):
        """Serialize face_descriptor to JSON"""
        self.face_descriptor = json.dumps(descriptor) if descriptor else None
    
    def get_face_descriptors(self):
        """Parse JSON face_descriptors field"""
        try:
            return json.loads(self.face_descriptors) if self.face_descriptors else []
        except:
            return []
    
    def set_face_descriptors(self, descriptors):
        """Serialize face_descriptors to JSON"""
        self.face_descriptors = json.dumps(descriptors) if descriptors else None
    
    def to_dict(self):
        return {
            'employee_id': str(self.id),
            'tenant_id': self.tenant_id,
            'store_id': self.store_id,
            'name': self.name,
            'role': self.role,
            'phone_number': self.phone_number,
            'hourly_pay': self.hourly_pay,
            'active': self.active,
            'face_registered': self.face_registered,
            'face_descriptor': self.get_face_descriptor(),
            'face_descriptors': self.get_face_descriptors(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    store_id = db.Column(db.String(100), nullable=False, index=True)
    sku = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    device_type = db.Column(db.String(50), default='metro', nullable=False, index=True)  # metro, discontinued, unlocked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = db.relationship('Tenant')
    # Store relationship - handled via queries (no SQLAlchemy relationship)
    # Use get_store_by_name(name, tenant_id=...) function instead
    
    # Composite unique constraint on tenant_id + store_id + sku + name
    # This allows multiple items with the same SKU but different names
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'store_id', 'sku', 'name', name='uq_tenant_store_sku_name'),
    )
    
    def to_dict(self):
        return {
            '_id': str(self.id),
            'tenant_id': self.tenant_id,
            'store_id': self.store_id,
            'sku': self.sku,
            'name': self.name,
            'quantity': self.quantity,
            'device_type': self.device_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class InventoryHistory(db.Model):
    __tablename__ = 'inventory_history'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    store_id = db.Column(db.String(100), nullable=False, index=True)
    snapshot_date = db.Column(db.DateTime, nullable=False, index=True)
    items = db.Column(db.Text, nullable=False)  # JSON array of inventory items
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = db.relationship('Tenant')
    # Store relationship - handled via queries (no SQLAlchemy relationship)
    # Use get_store_by_name(name, tenant_id=...) function instead
    
    # Composite unique constraint on tenant_id + store_id + snapshot_date
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'store_id', 'snapshot_date', name='uq_tenant_store_snapshot_date'),
    )
    
    def get_items(self):
        """Parse JSON items field"""
        try:
            return json.loads(self.items) if self.items else []
        except:
            return []
    
    def set_items(self, items_list):
        """Serialize items to JSON"""
        self.items = json.dumps(items_list)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': self.tenant_id,
            'store_id': self.store_id,
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None,
            'items': self.get_items(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class TimeClock(db.Model):
    __tablename__ = 'timeclock'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False, index=True)
    employee_name = db.Column(db.String(100), nullable=True)
    store_id = db.Column(db.String(100), nullable=True, index=True)
    clock_in = db.Column(db.DateTime, nullable=False, index=True)
    clock_out = db.Column(db.DateTime, nullable=True)
    hours_worked = db.Column(db.Float, nullable=True)
    clock_in_face_image = db.Column(db.Text, nullable=True)  # Base64 image
    clock_out_face_image = db.Column(db.Text, nullable=True)  # Base64 image
    clock_in_confidence = db.Column(db.Float, nullable=True)
    clock_out_confidence = db.Column(db.Float, nullable=True)
    
    # Relationships
    tenant = db.relationship('Tenant')
    employee = db.relationship('Employee', back_populates='timeclock_entries')
    
    def to_dict(self):
        clock_in_iso = self.clock_in.isoformat() if self.clock_in else None
        if clock_in_iso and not clock_in_iso.endswith('Z') and self.clock_in.tzinfo is None:
            clock_in_iso += 'Z'
        
        clock_out_iso = self.clock_out.isoformat() if self.clock_out else None
        if clock_out_iso and not clock_out_iso.endswith('Z') and self.clock_out.tzinfo is None:
            clock_out_iso += 'Z'
        
        return {
            'entry_id': str(self.id),
            'tenant_id': self.tenant_id,
            'employee_id': str(self.employee_id),
            'employee_name': self.employee_name,
            'store_id': self.store_id,
            'clock_in': clock_in_iso,
            'clock_out': clock_out_iso,
            'hours_worked': self.hours_worked,
            'clock_in_confidence': self.clock_in_confidence,
            'clock_out_confidence': self.clock_out_confidence,
            'status': 'clocked_out' if self.clock_out else 'clocked_in'
        }


class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    store_id = db.Column(db.String(100), nullable=True, index=True)
    manager_username = db.Column(db.String(50), nullable=True, index=True)
    alert_type = db.Column(db.String(50), nullable=False)  # 'late_clock_in', 'auto_clockout', etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    employee_name = db.Column(db.String(100), nullable=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    tenant = db.relationship('Tenant')
    employee = db.relationship('Employee')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'tenant_id': self.tenant_id,
            'store_id': self.store_id,
            'manager_username': self.manager_username,
            'alert_type': self.alert_type,
            'title': self.title,
            'message': self.message,
            'employee_id': str(self.employee_id) if self.employee_id else None,
            'employee_name': self.employee_name,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class EOD(db.Model):
    __tablename__ = 'eod'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    store_id = db.Column(db.String(100), nullable=False, index=True)
    report_date = db.Column(db.String(50), nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    cash_amount = db.Column(db.Float, default=0)
    credit_amount = db.Column(db.Float, default=0)
    card1_amount = db.Column(db.Float, default=0)
    qpay_amount = db.Column(db.Float, default=0)
    boxes_count = db.Column(db.Integer, default=0)
    accessories_amount = db.Column(db.Float, default=0)
    magenta_amount = db.Column(db.Float, default=0)
    inventory_sold = db.Column(db.Integer, default=0)
    over_short = db.Column(db.Float, default=0)
    total1 = db.Column(db.Float, default=0)
    # Denominations
    denom_100_count = db.Column(db.Integer, default=0)
    denom_100_total = db.Column(db.Float, default=0)
    denom_50_count = db.Column(db.Integer, default=0)
    denom_50_total = db.Column(db.Float, default=0)
    denom_20_count = db.Column(db.Integer, default=0)
    denom_20_total = db.Column(db.Float, default=0)
    denom_10_count = db.Column(db.Integer, default=0)
    denom_10_total = db.Column(db.Float, default=0)
    denom_5_count = db.Column(db.Integer, default=0)
    denom_5_total = db.Column(db.Float, default=0)
    denom_1_count = db.Column(db.Integer, default=0)
    denom_1_total = db.Column(db.Float, default=0)
    total_bills = db.Column(db.Float, default=0)
    submitted_by = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = db.relationship('Tenant')
    # Store relationship - handled via queries (no SQLAlchemy relationship)
    # Use get_store_by_name(name, tenant_id=...) function instead
    
    def to_dict(self):
        created_at_iso = self.created_at.isoformat() if self.created_at else None
        if created_at_iso and not created_at_iso.endswith('Z') and self.created_at.tzinfo is None:
            created_at_iso += 'Z'
        
        return {
            'id': str(self.id),
            'tenant_id': self.tenant_id,
            'store_id': self.store_id,
            'report_date': self.report_date,
            'notes': self.notes,
            'cash_amount': self.cash_amount,
            'credit_amount': self.credit_amount,
            'card1_amount': self.card1_amount,
            'qpay_amount': self.qpay_amount,
            'boxes_count': self.boxes_count,
            'accessories_amount': self.accessories_amount,
            'magenta_amount': self.magenta_amount,
            'inventory_sold': self.inventory_sold,
            'over_short': self.over_short,
            'total1': self.total1,
            'denom_100_count': self.denom_100_count,
            'denom_100_total': self.denom_100_total,
            'denom_50_count': self.denom_50_count,
            'denom_50_total': self.denom_50_total,
            'denom_20_count': self.denom_20_count,
            'denom_20_total': self.denom_20_total,
            'denom_10_count': self.denom_10_count,
            'denom_10_total': self.denom_10_total,
            'denom_5_count': self.denom_5_count,
            'denom_5_total': self.denom_5_total,
            'denom_1_count': self.denom_1_count,
            'denom_1_total': self.denom_1_total,
            'total_bills': self.total_bills,
            'submitted_by': self.submitted_by,
            'created_at': created_at_iso
        }


class StoreBilling(db.Model):
    __tablename__ = 'store_billings'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    store_id = db.Column(db.String(100), nullable=False, index=True)
    bill_type = db.Column(db.String(50), nullable=False)  # 'electricity', 'wifi', 'gas'
    billing_month = db.Column(db.String(7), nullable=False, index=True)  # Format: 'YYYY-MM' (e.g., '2024-01')
    amount = db.Column(db.Float, nullable=False, default=0)
    paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = db.relationship('Tenant')
    
    # Composite unique constraint on tenant_id + store_id + bill_type + billing_month
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'store_id', 'bill_type', 'billing_month', name='uq_tenant_store_bill_type_month'),
    )
    
    def to_dict(self):
        payment_date_iso = self.payment_date.isoformat() if self.payment_date else None
        if payment_date_iso and not payment_date_iso.endswith('Z') and self.payment_date and self.payment_date.tzinfo is None:
            payment_date_iso += 'Z'
        
        created_at_iso = self.created_at.isoformat() if self.created_at else None
        if created_at_iso and not created_at_iso.endswith('Z') and self.created_at.tzinfo is None:
            created_at_iso += 'Z'
        
        updated_at_iso = self.updated_at.isoformat() if self.updated_at else None
        if updated_at_iso and not updated_at_iso.endswith('Z') and self.updated_at.tzinfo is None:
            updated_at_iso += 'Z'
        
        return {
            'id': str(self.id),
            'tenant_id': self.tenant_id,
            'store_id': self.store_id,
            'bill_type': self.bill_type,
            'billing_month': self.billing_month,
            'amount': self.amount,
            'paid': self.paid,
            'payment_date': payment_date_iso,
            'created_at': created_at_iso,
            'updated_at': updated_at_iso
        }


# ================== Helper Functions ==================

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password, hashed):
    """
    Verify a password against a bcrypt hash.
    
    SECURITY: Plain text password fallback has been removed for security.
    All passwords must be bcrypt hashed.
    """
    if not password or not hashed:
        return False
    
    # Only accept bcrypt hashed passwords
    if not (hashed.startswith('$2b$') or hashed.startswith('$2a$')):
        # Password is not hashed - reject it for security
        return False
    
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def get_default_inventory_items():
    """Returns a list of default inventory items that should be created for each new store, categorized by device_type"""
    return [
        # Metro Devices
        {"sku": "Samsung", "name": "Samsung A15", "device_type": "metro"},
        {"sku": "Samsung", "name": "Samsung A16", "device_type": "metro"},
        {"sku": "Samsung", "name": "Samsung A36", "device_type": "metro"},
        {"sku": "Samsung", "name": "Samsung S25FE", "device_type": "metro"},
        {"sku": "Samsung", "name": "Samsung Tab A9+", "device_type": "metro"},
        {"sku": "Samsung", "name": "Samsung watch", "device_type": "metro"},
  
        {"sku": "Moto", "name": "Moto Gplay 2026", "device_type": "metro"},
        {"sku": "Moto", "name": "Moto G 2025", "device_type": "metro"},
        {"sku": "Moto", "name": "Moto power 2025", "device_type": "metro"},
        {"sku": "Moto", "name": "Moto stylus 2025", "device_type": "metro"},
        {"sku": "Moto", "name": "Moto Razr 2025", "device_type": "metro"},
        
        {"sku": "TCL", "name": "TCL K32", "device_type": "metro"},
        {"sku": "TCL", "name": "TCL Flip 4", "device_type": "metro"},
        
        {"sku": "Revvl", "name": "Revvl 8", "device_type": "metro"},
        {"sku": "Revvl", "name": "Revvl tab2", "device_type": "metro"},
        
        {"sku": "Apple", "name": "iPhone 13", "device_type": "metro"},
        {"sku": "Apple", "name": "iPhone 14", "device_type": "metro"},
        {"sku": "Apple", "name": "iPhone 15", "device_type": "metro"},
        {"sku": "Apple", "name": "iPhone 16 e", "device_type": "metro"},
        {"sku": "Apple", "name": "iPhone Air", "device_type": "metro"},
        {"sku": "Apple", "name": "Apple watch", "device_type": "metro"},
  
        {"sku": "Generic", "name": "HSI", "device_type": "metro"},
        {"sku": "Generic", "name": "EDGE 2025", "device_type": "metro"},
        {"sku": "Simcards", "name": "Simcards", "device_type": "metro"},
        
        # Discontinued Devices
        {"sku": "Generic", "name": "A13", "device_type": "discontinued"},
        {"sku": "Generic", "name": "A35", "device_type": "discontinued"},
        {"sku": "Generic", "name": "G400", "device_type": "discontinued"},
        {"sku": "Moto", "name": "STYLUS 2023", "device_type": "discontinued"},
        {"sku": "Moto", "name": "EDGE 2024", "device_type": "discontinued"},
        {"sku": "Samsung", "name": "S24FE", "device_type": "discontinued"},
        {"sku": "TCL", "name": "K11", "device_type": "discontinued"},
        {"sku": "Generic", "name": "N300", "device_type": "discontinued"},
        {"sku": "TCL", "name": "ION X", "device_type": "discontinued"},
        {"sku": "Chromebook", "name": "CHROMEBOOK", "device_type": "discontinued"},
        
        # Unlocked Devices
        {"sku": "Generic", "name": "A14", "device_type": "unlocked"},
        {"sku": "Generic", "name": "A15", "device_type": "unlocked"},
        {"sku": "Generic", "name": "A16", "device_type": "unlocked"},
        {"sku": "Generic", "name": "A36", "device_type": "unlocked"},
        {"sku": "Generic", "name": "A25", "device_type": "unlocked"},
        {"sku": "Samsung", "name": "S22 PLUS", "device_type": "unlocked"},
        {"sku": "Samsung", "name": "S25 ULTRA", "device_type": "unlocked"},
        {"sku": "Apple", "name": "IPHONE11", "device_type": "unlocked"},
        {"sku": "Apple", "name": "IPHONE 12", "device_type": "unlocked"},
        {"sku": "Apple", "name": "IPHONE 13", "device_type": "unlocked"},
        {"sku": "Apple", "name": "IPHONE 14", "device_type": "unlocked"},
        {"sku": "Apple", "name": "IPHONE16 PRO", "device_type": "unlocked"},
        {"sku": "Apple", "name": "IPHONE16 PRO MAX", "device_type": "unlocked"},
        {"sku": "Apple", "name": "IPhone 17 PRO MAX", "device_type": "unlocked"},
        {"sku": "Revvl", "name": "REVVL 6X", "device_type": "unlocked"},
        {"sku": "Generic", "name": "LOGIC(4G)", "device_type": "unlocked"},
        {"sku": "Moto", "name": "MOTO G 2022", "device_type": "unlocked"},
        {"sku": "Moto", "name": "MOTO G 2024", "device_type": "unlocked"},
        {"sku": "Generic", "name": "ORBIC", "device_type": "unlocked"},
        {"sku": "Generic", "name": "NOKIA", "device_type": "unlocked"},
        {"sku": "Generic", "name": "PANDA", "device_type": "unlocked"},
        {"sku": "Generic", "name": "FUSION", "device_type": "unlocked"},
        {"sku": "Generic", "name": "EDGE", "device_type": "unlocked"},
]


# ================== Tenant Functions ==================

def get_tenant_by_id(tenant_id):
    """Get a tenant by ID"""
    tenant = Tenant.query.get(tenant_id)
    return tenant.to_dict() if tenant else None


def get_tenant_by_email(email):
    """Get a tenant by email"""
    tenant = Tenant.query.filter_by(email=email).first()
    return tenant.to_dict(include_password=True) if tenant else None


def create_tenant(company_name, email, password_hash, plan='basic', stripe_customer_id=None, stripe_subscription_id=None):
    """Create a new tenant"""
    # Check if email already exists
    existing = Tenant.query.filter_by(email=email).first()
    if existing:
        raise ValueError(f"Tenant with email '{email}' already exists")
    
    # Set storage limits based on plan
    plan_limits = {
        'basic': 1073741824,      # 1GB
        'standard': 10737418240,   # 10GB
        'premium': 107374182400    # 100GB
    }
    max_storage = plan_limits.get(plan, 1073741824)
    
    tenant = Tenant(
        company_name=company_name,
        email=email,
        password_hash=password_hash,
        plan=plan,
        max_storage_bytes=max_storage,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id
    )
    db.session.add(tenant)
    db.session.commit()
    
    return tenant.to_dict()


def update_tenant_storage(tenant_id, additional_bytes):
    """Update tenant storage usage"""
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant with ID {tenant_id} not found")
    
    tenant.used_storage_bytes += additional_bytes
    if tenant.used_storage_bytes < 0:
        tenant.used_storage_bytes = 0
    
    db.session.commit()
    return tenant.to_dict()


def update_tenant_plan(tenant_id, plan, stripe_subscription_id=None):
    """Update tenant plan and storage limits"""
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant with ID {tenant_id} not found")
    
    plan_limits = {
        'basic': 1073741824,      # 1GB
        'standard': 10737418240,   # 10GB
        'premium': 107374182400    # 100GB
    }
    
    tenant.plan = plan
    tenant.max_storage_bytes = plan_limits.get(plan, 1073741824)
    if stripe_subscription_id:
        tenant.stripe_subscription_id = stripe_subscription_id
    
    db.session.commit()
    return tenant.to_dict()


# ================== Manager Functions ==================

def get_manager_by_username(username, tenant_id=None):
    """Get a manager by username, optionally filtered by tenant_id"""
    query = Manager.query.filter_by(username=username)
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    manager = query.first()
    return manager.to_dict(include_password=True) if manager else None


def get_all_managers(tenant_id=None):
    """Get all managers (excluding passwords), optionally filtered by tenant_id"""
    query = Manager.query
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    managers = query.all()
    return [m.to_dict() for m in managers]


def create_manager(tenant_id, name, username, password, location=None, is_super_admin=False, is_admin=False, regions=None):
    """Create a new manager account"""
    # Check if username already exists for this tenant
    existing = Manager.query.filter_by(tenant_id=tenant_id, username=username).first()
    if existing:
        raise ValueError(f"Manager username '{username}' already exists for this tenant")
    
    # Hash the password
    password_hash = hash_password(password)
    
    manager = Manager(
        tenant_id=tenant_id,
        name=name,
        username=username,
        password=password_hash,
        location=location,
        is_super_admin=is_super_admin,
        is_admin=is_admin
    )
    if regions:
        manager.set_regions(regions)
    
    db.session.add(manager)
    db.session.commit()
    
    return manager.to_dict()


def update_manager(tenant_id, username, name=None, new_username=None, password=None, location=None, is_admin=None, regions=None):
    """Update an existing manager account"""
    # Check if manager exists
    manager = Manager.query.filter_by(tenant_id=tenant_id, username=username).first()
    if not manager:
        raise ValueError(f"Manager with username '{username}' not found for this tenant")
    
    old_username = username
    
    # If username is changing, update all related data FIRST
    if new_username is not None and new_username != old_username:
        # Check if new username is already taken by another manager in the same tenant
        username_taken = Manager.query.filter_by(tenant_id=tenant_id, username=new_username).first()
        if username_taken:
            raise ValueError(f"Manager username '{new_username}' is already taken")
        
        # Update stores that reference this manager's username
        Store.query.filter_by(tenant_id=tenant_id, manager_username=old_username).update({Store.manager_username: new_username})
        
        # Commit the related table updates first
        db.session.commit()
    
    # Now update the manager itself
    if name is not None:
        manager.name = name
    
    if new_username is not None:
        manager.username = new_username
    
    if location is not None:
        manager.location = location
    
    if password is not None:
        manager.password = hash_password(password)
    
    if is_admin is not None:
        manager.is_admin = is_admin
    
    if regions is not None:
        manager.set_regions(regions)
    
    # Commit the manager update
    db.session.commit()
    
    return manager.to_dict()


# ================== Store Functions ==================

def create_store(tenant_id, name, username=None, password=None, total_boxes=0, manager_username=None, allowed_ip=None, opening_time=None, closing_time=None):
    """Create a new store"""
    # Skip duplicate checking - just try to create and let database handle it
    # This is much faster - database constraints will handle uniqueness
    original_name = name
    original_username = username
    
    # Generate default password if not provided
    if password is None:
        password = username + "123"
    
    # Hash the password
    password_hash = hash_password(password)
    
    store = Store(
        tenant_id=tenant_id,
        name=name,
        username=username,
        password=password_hash,
        total_boxes=total_boxes,
        manager_username=manager_username,
        allowed_ip=allowed_ip,
        opening_time=opening_time,
        closing_time=closing_time
    )
    db.session.add(store)
    
    # Commit the store creation
    # Since we've already checked for duplicates above, this should succeed
    db.session.commit()
    
    # Add default inventory items to the new store
    try:
        add_default_inventory_to_store(tenant_id=tenant_id, store_name=name)
    except Exception as inv_error:
        # Log error but don't fail store creation if inventory addition fails
        print(f"Warning: Failed to add default inventory to store '{name}': {inv_error}")
    
    return str(store.id)


def get_store_by_username(username, tenant_id=None):
    """Get a store by username, optionally filtered by tenant_id"""
    query = Store.query.filter_by(username=username)
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    store = query.first()
    return store.to_dict(include_password=True) if store else None


def get_store_by_name(name, tenant_id=None):
    """Get a store by name, optionally filtered by tenant_id"""
    query = Store.query.filter_by(name=name)
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    return query.first()

def get_stores(tenant_id=None, manager_username=None):
    """Get stores, optionally filtered by tenant_id and/or manager_username"""
    query = Store.query
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    if manager_username:
        query = query.filter_by(manager_username=manager_username)
    stores = query.all()
    return [s.to_dict() for s in stores]


def update_store(tenant_id, name, new_name=None, username=None, password=None, total_boxes=None, allowed_ip=None, opening_time=None, closing_time=None):
    """Update a store's information"""
    store = Store.query.filter_by(tenant_id=tenant_id, name=name).first()
    if not store:
        return False
    
    old_name = name
    
    # If the store name is changing, we need to handle FK constraints carefully
    # The FK constraint checks the NEW value immediately, so we need to work around it
    # Strategy: Make the FK constraint DEFERRABLE if it isn't already, then defer it
    if new_name is not None and new_name != old_name:
        # Check if FK constraint exists and make it DEFERRABLE if needed
        try:
            # Try to alter the constraint to be DEFERRABLE (if it exists)
            # This is safe to run multiple times - if already deferrable, it does nothing
            db.session.execute(text("""
                DO $$
                BEGIN
                    -- Check if constraint exists and alter it to be DEFERRABLE
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'inventory_store_id_fkey'
                    ) THEN
                        -- Drop and recreate as DEFERRABLE
                        ALTER TABLE inventory DROP CONSTRAINT IF EXISTS inventory_store_id_fkey;
                        ALTER TABLE inventory ADD CONSTRAINT inventory_store_id_fkey 
                            FOREIGN KEY (store_id) REFERENCES stores(name) 
                            ON UPDATE CASCADE ON DELETE CASCADE 
                            DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END $$;
            """))
            db.session.commit()  # Commit the constraint modification
            
            # Now defer the constraint for this transaction
            db.session.execute(text("SET CONSTRAINTS inventory_store_id_fkey DEFERRED"))
        except Exception as e:
            # If we can't modify the constraint, try the update anyway
            # The constraint might already be deferrable or we'll handle the error
            db.session.rollback()
            pass
        
        # First, update the store name
        store.name = new_name
        db.session.flush()  # Make store name change visible in transaction
        
        # Now update all related tables (FK constraint check is deferred until commit)
        # Update inventory items (has FK constraint: inventory_store_id_fkey)
        Inventory.query.filter_by(tenant_id=tenant_id, store_id=old_name).update(
            {Inventory.store_id: new_name}, 
            synchronize_session=False
        )
        
        # Update inventory history
        InventoryHistory.query.filter_by(tenant_id=tenant_id, store_id=old_name).update(
            {InventoryHistory.store_id: new_name}, 
            synchronize_session=False
        )
        
        # Update EOD reports
        EOD.query.filter_by(tenant_id=tenant_id, store_id=old_name).update(
            {EOD.store_id: new_name}, 
            synchronize_session=False
        )
        
        # Update timeclock entries
        TimeClock.query.filter_by(tenant_id=tenant_id, store_id=old_name).update(
            {TimeClock.store_id: new_name}, 
            synchronize_session=False
        )
        
        # Update employee store_id references
        Employee.query.filter_by(tenant_id=tenant_id, store_id=old_name).update(
            {Employee.store_id: new_name}, 
            synchronize_session=False
        )
    
    # Update other store fields
    if username is not None:
        store.username = username
    if password is not None:
        store.password = hash_password(password)
    if total_boxes is not None:
        store.total_boxes = total_boxes
    if allowed_ip is not None:
        store.allowed_ip = allowed_ip
    if opening_time is not None:
        store.opening_time = opening_time
    if closing_time is not None:
        store.closing_time = closing_time
    
    # Commit all changes together in a single transaction
    db.session.commit()
    
    return True


def delete_store(tenant_id, name):
    """Delete a store and all related data"""
    store = Store.query.filter_by(tenant_id=tenant_id, name=name).first()
    if not store:
        return False
    
    # Delete all related data BEFORE deleting the store to avoid FK constraint violations
    # Delete inventory items (has FK constraint: inventory_store_id_fkey)
    Inventory.query.filter_by(tenant_id=tenant_id, store_id=name).delete()
    
    # Delete inventory history (may have FK constraint)
    InventoryHistory.query.filter_by(tenant_id=tenant_id, store_id=name).delete()
    
    # Delete EOD reports (may have FK constraint)
    EOD.query.filter_by(tenant_id=tenant_id, store_id=name).delete()
    
    # Delete timeclock entries
    TimeClock.query.filter_by(tenant_id=tenant_id, store_id=name).delete()
    
    # Clear employee store_id references (set to NULL)
    Employee.query.filter_by(tenant_id=tenant_id, store_id=name).update({Employee.store_id: None})
    
    # Now delete the store itself
    db.session.delete(store)
    db.session.commit()
    
    return True




# ================== Employee Functions ==================

def create_employee(tenant_id, store_id, name, role=None, phone_number=None, hourly_pay=None):
    """Create a new employee"""
    # Check for duplicate phone number if phone_number is provided
    if phone_number and phone_number.strip():
        phone_number_clean = phone_number.strip()
        existing_employee = Employee.query.filter_by(
            tenant_id=tenant_id,
            phone_number=phone_number_clean
        ).first()
        if existing_employee:
            raise ValueError(f"An employee with phone number {phone_number_clean} already exists.")
    
    employee = Employee(
        tenant_id=tenant_id,
        store_id=store_id,
        name=name,
        role=role,
        phone_number=phone_number.strip() if phone_number else None,
        hourly_pay=hourly_pay,
        active=True
    )
    db.session.add(employee)
    db.session.commit()
    return str(employee.id)


def get_employees(tenant_id=None, store_id=None):
    """Get employees, optionally filtered by tenant_id and/or store_id"""
    query = Employee.query
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    if store_id:
        query = query.filter_by(store_id=store_id)
    employees = query.all()
    return [e.to_dict() for e in employees]


def update_employee(employee_id, tenant_id=None, phone_number=None, hourly_pay=None):
    """Update an employee's phone number and/or hourly pay"""
    try:
        employee = Employee.query.get(int(employee_id))
        if not employee:
            return False
        
        # Verify employee belongs to tenant if tenant_id is provided
        if tenant_id is not None and employee.tenant_id != tenant_id:
            return False
        
        if phone_number is not None:
            employee.phone_number = phone_number
        if hourly_pay is not None:
            employee.hourly_pay = float(hourly_pay) if hourly_pay else None
        
        db.session.commit()
        return True
    except (ValueError, TypeError):
        return False


def delete_employee(employee_id):
    """Delete an employee"""
    try:
        employee = Employee.query.get(int(employee_id))
        if not employee:
            return False
        db.session.delete(employee)
        db.session.commit()
        return True
    except (ValueError, TypeError):
        return False


# ================== Inventory Functions ==================

def add_inventory_item(tenant_id, store_id, sku, name, quantity=0, device_type='metro'):
    """Add an inventory item"""
    # Validate device_type
    valid_types = ['metro', 'discontinued', 'unlocked']
    if device_type not in valid_types:
        device_type = 'metro'  # Default to metro if invalid
    
    # Check if item already exists (check by SKU + Name combination, not just SKU)
    # Multiple items can have the same SKU but different names
    existing_item = Inventory.query.filter_by(
        tenant_id=tenant_id,
        store_id=store_id,
        sku=sku,
        name=name
    ).first()
    
    if existing_item:
        raise ValueError(f"An item with SKU '{sku}' and name '{name}' already exists for this store. Please use a different name or update the existing item.")
    
    item = Inventory(
        tenant_id=tenant_id,
        store_id=store_id,
        sku=sku,
        name=name,
        quantity=quantity,
        device_type=device_type
    )
    db.session.add(item)
    db.session.commit()
    return str(item.id)


def update_inventory_item(tenant_id, store_id, sku=None, item_id=None, quantity=None, name=None, new_sku=None, device_type=None):
    """Update an inventory item"""
    # Find the item
    if item_id:
        try:
            item = Inventory.query.filter_by(tenant_id=tenant_id, id=int(item_id)).first()
        except (ValueError, TypeError):
            return False
    elif store_id and sku:
        item = Inventory.query.filter_by(tenant_id=tenant_id, store_id=store_id, sku=sku).first()
    else:
        return False

    if not item:
        return False
    
    # If SKU is changing, check if new (SKU, name) combination already exists
    # Multiple items can have the same SKU but different names
    if new_sku is not None:
        new_name = name if name is not None else item.name
        existing = Inventory.query.filter_by(
            tenant_id=tenant_id, 
            store_id=store_id, 
            sku=new_sku,
            name=new_name
        ).filter(Inventory.id != item.id).first()
        if existing:
            return False
        item.sku = new_sku
    
    if quantity is not None:
        item.quantity = quantity
    if name is not None:
        item.name = name
    if device_type is not None:
        # Validate device_type
        valid_types = ['metro', 'discontinued', 'unlocked']
        if device_type in valid_types:
            item.device_type = device_type
    
    db.session.commit()
    return True


def delete_inventory_item(tenant_id, store_id, sku):
    """Delete an inventory item"""
    item = Inventory.query.filter_by(tenant_id=tenant_id, store_id=store_id, sku=sku).first()
    if not item:
        return False
    db.session.delete(item)
    db.session.commit()
    return True


def get_inventory(tenant_id=None, store_id=None, device_type=None):
    """Get inventory items, optionally filtered by tenant_id, store_id, and/or device_type"""
    query = Inventory.query
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    if store_id:
        query = query.filter_by(store_id=store_id)
    if device_type and device_type.strip():
        # Only filter if device_type is provided and not empty
        query = query.filter_by(device_type=device_type.strip())
    items = query.all()
    return [i.to_dict() for i in items]


def add_default_inventory_to_store(tenant_id, store_name):
    """
    Add default inventory items to a store.
    Checks for existing items to avoid duplicates.
    Returns the number of items created.
    """
    from backend.database import db
    # Import models here to avoid circular imports
    from backend.models import Inventory
    
    default_items = get_default_inventory_items()
    
    # Batch fetch existing items to reduce database queries
    existing_items = Inventory.query.filter_by(
        tenant_id=tenant_id,
        store_id=store_name
    ).all()
    
    # Create a set of existing (sku, name) combinations for fast lookup
    existing_combinations = set()
    existing_skus = set()
    for existing in existing_items:
        existing_combinations.add((existing.sku, existing.name))
        existing_skus.add(existing.sku)
    
    # Batch create items
    items_to_create = []
    for item in default_items:
        sku = item["sku"]
        name = item["name"]
        device_type = item.get("device_type", "metro")  # Default to metro if not specified
        
        # Skip if already exists (check both new and old constraint formats)
        if (sku, name) in existing_combinations or sku in existing_skus:
            continue
        
        try:
            inventory_item = Inventory(
                tenant_id=tenant_id,
                store_id=store_name,
                sku=sku,
                name=name,
                quantity=0,
                device_type=device_type
            )
            items_to_create.append(inventory_item)
        except Exception as item_error:
            print(f"Warning: Failed to prepare inventory item {sku}/{name}: {item_error}")
            continue
    
    # Batch insert all items at once
    if items_to_create:
        try:
            db.session.bulk_save_objects(items_to_create)
            db.session.commit()
            return len(items_to_create)
        except Exception as e:
            db.session.rollback()
            # If bulk insert fails (e.g., due to constraints), try individual inserts
            created_count = 0
            for item in items_to_create:
                try:
                    db.session.add(item)
                    db.session.commit()
                    created_count += 1
                except Exception as item_error:
                    db.session.rollback()
                    error_str = str(item_error)
                    if "UniqueViolation" not in error_str and "duplicate key" not in error_str.lower():
                        print(f"Warning: Failed to add inventory item {item.sku}/{item.name}: {item_error}")
            return created_count
    
    return 0


# ================== EOD Functions ==================

def create_alert(tenant_id, store_id, manager_username, alert_type, title, message, employee_id=None, employee_name=None):
    """Create a new alert for a manager"""
    alert = Alert(
        tenant_id=tenant_id,
        store_id=store_id,
        manager_username=manager_username,
        alert_type=alert_type,
        title=title,
        message=message,
        employee_id=employee_id,
        employee_name=employee_name,
        is_read=False
    )
    db.session.add(alert)
    db.session.commit()
    return alert.to_dict()


def get_alerts(tenant_id, manager_username=None, store_id=None, is_read=None, limit=100):
    """Get alerts for a manager, optionally filtered by store and read status"""
    query = Alert.query.filter_by(tenant_id=tenant_id)
    
    if manager_username:
        query = query.filter_by(manager_username=manager_username)
    if store_id:
        query = query.filter_by(store_id=store_id)
    if is_read is not None:
        query = query.filter_by(is_read=is_read)
    
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return [alert.to_dict() for alert in alerts]


def mark_alert_read(alert_id, tenant_id):
    """Mark an alert as read"""
    alert = Alert.query.filter_by(id=alert_id, tenant_id=tenant_id).first()
    if alert:
        alert.is_read = True
        db.session.commit()
        return True
    return False


def create_eod(tenant_id, store_id, report_date, notes=None, cash_amount=0, credit_amount=0, card1_amount=0, qpay_amount=0, boxes_count=0, accessories_amount=0, magenta_amount=0, inventory_sold=0, over_short=0, total1=0, 
               denom_100_count=0, denom_100_total=0, denom_50_count=0, denom_50_total=0, denom_20_count=0, denom_20_total=0, 
               denom_10_count=0, denom_10_total=0, denom_5_count=0, denom_5_total=0, denom_1_count=0, denom_1_total=0, total_bills=0, submitted_by=None):
    """Create an EOD report"""
    eod = EOD(
        tenant_id=tenant_id,
        store_id=store_id,
        report_date=report_date,
        notes=notes or "",
        cash_amount=cash_amount,
        credit_amount=credit_amount,
        card1_amount=card1_amount,
        qpay_amount=qpay_amount,
        boxes_count=boxes_count,
        accessories_amount=accessories_amount,
        magenta_amount=magenta_amount,
        inventory_sold=inventory_sold,
        over_short=over_short,
        total1=total1,
        denom_100_count=denom_100_count,
        denom_100_total=denom_100_total,
        denom_50_count=denom_50_count,
        denom_50_total=denom_50_total,
        denom_20_count=denom_20_count,
        denom_20_total=denom_20_total,
        denom_10_count=denom_10_count,
        denom_10_total=denom_10_total,
        denom_5_count=denom_5_count,
        denom_5_total=denom_5_total,
        denom_1_count=denom_1_count,
        denom_1_total=denom_1_total,
        total_bills=total_bills,
        submitted_by=submitted_by or "Unknown"
    )
    db.session.add(eod)
    db.session.commit()
    return str(eod.id)


def get_eods(tenant_id=None, store_id=None):
    """Get EOD reports, optionally filtered by tenant_id and/or store_id"""
    query = EOD.query
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    if store_id:
        query = query.filter_by(store_id=store_id)
    eods = query.order_by(EOD.report_date.desc()).all()
    
    results = []
    for eod in eods:
        eod_dict = eod.to_dict()
        
        # Get employees who worked on this report date
        report_date = eod.report_date
        store = eod.store_id
        tenant_id = eod.tenant_id
        if report_date and store:
            try:
                from datetime import datetime as dt, timedelta
                report_dt = dt.fromisoformat(report_date.replace('Z', '+00:00')) if isinstance(report_date, str) else report_date
                day_start = report_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                # Find all timeclock entries for this tenant/store on this date
                entries = TimeClock.query.filter(
                    TimeClock.tenant_id == tenant_id,
                    TimeClock.store_id == store,
                    TimeClock.clock_in >= day_start,
                    TimeClock.clock_in < day_end
                ).all()
                
                # Extract unique employee names
                employee_names = list(set([entry.employee_name for entry in entries if entry.employee_name]))
                employee_names.sort()
                eod_dict["employees_worked"] = employee_names
            except Exception as e:
                print(f"Error getting employees for EOD: {e}")
                eod_dict["employees_worked"] = []
        else:
            eod_dict["employees_worked"] = []
        
        results.append(eod_dict)
    
    return results


# ================== Billing Functions ==================

def get_current_billing_month():
    """Get current billing month in YYYY-MM format"""
    return datetime.utcnow().strftime('%Y-%m')


def get_store_billings(tenant_id=None, store_id=None, billing_month=None):
    """Get store billings, optionally filtered by tenant_id, store_id, and/or billing_month"""
    if billing_month is None:
        billing_month = get_current_billing_month()
    
    query = StoreBilling.query.filter_by(billing_month=billing_month)
    if tenant_id:
        query = query.filter_by(tenant_id=tenant_id)
    if store_id:
        query = query.filter_by(store_id=store_id)
    billings = query.order_by(StoreBilling.store_id, StoreBilling.bill_type).all()
    return [b.to_dict() for b in billings]


def get_billings_by_stores(tenant_id, billing_month=None):
    """Get billings grouped by store for managers view (current month only)"""
    if billing_month is None:
        billing_month = get_current_billing_month()
    
    billings = StoreBilling.query.filter_by(
        tenant_id=tenant_id,
        billing_month=billing_month
    ).all()
    
    # Group by store
    store_billings = {}
    for billing in billings:
        store_id = billing.store_id
        if store_id not in store_billings:
            store_billings[store_id] = {
                'electricity': {'paid': False, 'amount': 0},
                'wifi': {'paid': False, 'amount': 0},
                'gas': {'paid': False, 'amount': 0}
            }
        
        bill_type = billing.bill_type.lower()
        if bill_type in store_billings[store_id]:
            store_billings[store_id][bill_type] = {
                'paid': billing.paid,
                'amount': float(billing.amount) if billing.paid else 0
            }
    
    return store_billings


def update_billing_payment(tenant_id, store_id, bill_type, amount, billing_month=None):
    """Update or create a billing payment for a store (current month only)"""
    if billing_month is None:
        billing_month = get_current_billing_month()
    
    bill_type_lower = bill_type.lower()
    if bill_type_lower not in ['electricity', 'wifi', 'gas']:
        raise ValueError(f"Invalid bill type: {bill_type}")
    
    # Find existing billing for current month
    billing = StoreBilling.query.filter_by(
        tenant_id=tenant_id,
        store_id=store_id,
        bill_type=bill_type_lower,
        billing_month=billing_month
    ).first()
    
    if billing:
        # Update existing billing
        billing.amount = float(amount)
        billing.paid = True
        billing.payment_date = datetime.utcnow()
    else:
        # Create new billing for current month
        billing = StoreBilling(
            tenant_id=tenant_id,
            store_id=store_id,
            bill_type=bill_type_lower,
            billing_month=billing_month,
            amount=float(amount),
            paid=True,
            payment_date=datetime.utcnow()
        )
        db.session.add(billing)
    
    db.session.commit()
    return billing.to_dict()


def reset_monthly_billings(tenant_id, billing_month=None):
    """
    Reset/clear billings for a specific month (or current month if not specified).
    This effectively deletes all billing records for that month.
    Note: This is called automatically when accessing billings for a new month.
    """
    if billing_month is None:
        billing_month = get_current_billing_month()
    
    # Delete all billings for the specified month and tenant
    StoreBilling.query.filter_by(
        tenant_id=tenant_id,
        billing_month=billing_month
    ).delete()
    
    db.session.commit()


# ================== Deprecated/Legacy Functions ==================
# These are kept for backward compatibility

def get_collection(name):
    """
    Deprecated: This function is kept for backward compatibility with routes
    that directly access collections. Returns a wrapper object that provides
    MongoDB-like access patterns but uses SQLAlchemy underneath.
    """
    class CollectionWrapper:
        def __init__(self, model_class):
            self.model_class = model_class
        
        def find_one(self, query, projection=None):
            """MongoDB-like find_one"""
            obj = None
            if '_id' in query:
                try:
                    obj = self.model_class.query.get(int(query['_id']))
                except:
                    return None
            else:
                # Build SQLAlchemy query from dict
                q = self.model_class.query
                for key, value in query.items():
                    if hasattr(self.model_class, key):
                        q = q.filter(getattr(self.model_class, key) == value)
                obj = q.first()
            
            if obj:
                result = obj.to_dict() if hasattr(obj, 'to_dict') else {}
                if projection and '_id' in projection and projection['_id'] == 0:
                    result.pop('id', None)
                    result.pop('_id', None)
                return result
            return None
        
        def find(self, query, projection=None):
            """MongoDB-like find"""
            q = self.model_class.query
            for key, value in query.items():
                if hasattr(self.model_class, key):
                    if isinstance(value, dict):
                        # Handle comparison operators
                        for op, op_value in value.items():
                            if op == '$gte':
                                q = q.filter(getattr(self.model_class, key) >= op_value)
                            elif op == '$lt':
                                q = q.filter(getattr(self.model_class, key) < op_value)
                            elif op == '$ne':
                                q = q.filter(getattr(self.model_class, key) != op_value)
                    else:
                        q = q.filter(getattr(self.model_class, key) == value)
            return CollectionCursor(q, projection)
        
        def insert_one(self, document):
            """MongoDB-like insert_one"""
            obj = self.model_class(**document)
            db.session.add(obj)
            db.session.commit()
            
            class InsertResult:
                def __init__(self, obj_id):
                    self.inserted_id = obj_id
            
            return InsertResult(obj.id)
        
        def update_one(self, query, update, upsert=False):
            """MongoDB-like update_one"""
            obj = None
            if '_id' in query:
                try:
                    obj = self.model_class.query.get(int(query['_id']))
                except:
                    pass
            else:
                q = self.model_class.query
                for key, value in query.items():
                    if hasattr(self.model_class, key):
                        q = q.filter(getattr(self.model_class, key) == value)
                obj = q.first()
            
            if obj:
                if '$set' in update:
                    for key, value in update['$set'].items():
                        if hasattr(obj, key):
                            setattr(obj, key, value)
                db.session.commit()
                
                class UpdateResult:
                    def __init__(self, modified):
                        self.modified_count = 1 if modified else 0
                
                return UpdateResult(True)
            
            class UpdateResult:
                def __init__(self, modified):
                    self.modified_count = 0
            return UpdateResult(False)
        
        def update_many(self, query, update):
            """MongoDB-like update_many"""
            q = self.model_class.query
            for key, value in query.items():
                if hasattr(self.model_class, key):
                    q = q.filter(getattr(self.model_class, key) == value)
            
            count = 0
            if '$set' in update:
                count = q.update(update['$set'])
                db.session.commit()
            
            class UpdateResult:
                def __init__(self, modified):
                    self.modified_count = modified
            return UpdateResult(count)
        
        def delete_one(self, query):
            """MongoDB-like delete_one"""
            obj = None
            if '_id' in query:
                try:
                    obj = self.model_class.query.get(int(query['_id']))
                except:
                    pass
            else:
                q = self.model_class.query
                for key, value in query.items():
                    if hasattr(self.model_class, key):
                        q = q.filter(getattr(self.model_class, key) == value)
                obj = q.first()
            
            if obj:
                db.session.delete(obj)
                db.session.commit()
                
                class DeleteResult:
                    def __init__(self, deleted):
                        self.deleted_count = 1 if deleted else 0
                return DeleteResult(True)
            
            class DeleteResult:
                def __init__(self, deleted):
                    self.deleted_count = 0
            return DeleteResult(False)
        
        def delete_many(self, query):
            """MongoDB-like delete_many"""
            q = self.model_class.query
            for key, value in query.items():
                if hasattr(self.model_class, key):
                    q = q.filter(getattr(self.model_class, key) == value)
            
            count = q.count()
            q.delete()
            db.session.commit()
            
            class DeleteResult:
                def __init__(self, deleted):
                    self.deleted_count = deleted
            return DeleteResult(count)
    
    class CollectionCursor:
        def __init__(self, query, projection=None):
            self.query = query
            self.projection = projection
            self._sort_field = None
            self._sort_direction = 1
        
        def sort(self, field, direction=1):
            """MongoDB-like sort"""
            self._sort_field = field
            self._sort_direction = direction
            return self
        
        def __iter__(self):
            """Make cursor iterable"""
            q = self.query
            if self._sort_field and hasattr(q.column_descriptions[0]['type'], self._sort_field):
                attr = getattr(q.column_descriptions[0]['type'], self._sort_field)
                if self._sort_direction == -1:
                    q = q.order_by(attr.desc())
                else:
                    q = q.order_by(attr)
            
            for obj in q.all():
                result = obj.to_dict() if hasattr(obj, 'to_dict') else {}
                if self.projection and '_id' in self.projection and self.projection['_id'] == 0:
                    result.pop('id', None)
                    result.pop('_id', None)
                yield result
    
    # Map collection names to models
    collection_map = {
        'managers': Manager,
        'stores': Store,
        'employees': Employee,
        'inventory': Inventory,
        'inventory_history': InventoryHistory,
        'timeclock': TimeClock,
        'eod': EOD
    }
    
    if name in collection_map:
        return CollectionWrapper(collection_map[name])
    
    # If collection doesn't exist, return a dummy wrapper
    class DummyModel:
        pass
    return CollectionWrapper(DummyModel)
