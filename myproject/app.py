from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pymysql
import jwt
import datetime
from datetime import date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from decimal import Decimal

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
# Rate limiting (ADDED)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

SECRET_KEY = "BCE_SECRET_KEY"

def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        db=os.getenv('DB_NAME', 'bce_system'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# JWT Decorators (CHANGED)
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth = request.headers['Authorization'].split()
            if len(auth) == 2 and auth[0] == 'Bearer':
                token = auth[1]
        
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_id = data['id']
            current_user_role = data.get('role', 'user')
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user_id, current_user_role, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(current_user_id, current_user_role, *args, **kwargs):
        if current_user_role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(current_user_id, current_user_role, *args, **kwargs)
    return decorated

# Input validation decorator (ADDED)
def validate_event_data(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        data = request.json or {}
        required = ['title', 'category', 'start_date', 'venue_id', 'base_price']
        for field in required:
            if field not in data or data[field] is None:
                return jsonify({'error': f'Missing {field}'}), 400
        
        title = data.get('title', '')
        if not isinstance(title, str) or len(title) < 3 or len(title) > 255:
            return jsonify({'error': 'Title must be 3-255 chars'}), 400
        if data['base_price'] < 0:
            return jsonify({'error': 'Price cannot be negative'}), 400
        if data['venue_id'] < 1:
            return jsonify({'error': 'Invalid venue ID'}), 400
        
        return f(*args, **kwargs)
    return decorated

# UTILITY FUNCTIONS (ADDED)
def calculate_days_advance(event_start_date):
    """Req 2: Calculate advance booking days"""
    today = date.today()
    return (event_start_date - today).days

def get_advance_discount(days_advance):
    """Req 2: Table 2 discount logic"""
    if 50 <= days_advance <= 60:
        return 0.20
    elif 35 <= days_advance < 50:
        return 0.15
    elif 25 <= days_advance < 35:
        return 0.10
    elif 15 <= days_advance < 25:
        return 0.05
    return 0.00


def serialize_db_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime.datetime)):
        return value.isoformat()
    return value


def serialize_row(row):
    return {k: serialize_db_value(v) for k, v in row.items()}


def get_current_price(event_id):
    """Req 5: Dynamic pricing - 25% off if <50% booked within 10 days"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.base_price, v.capacity, 
                       COALESCE(COUNT(b.booking_id), 0) as booked_count,
                       DATEDIFF(e.start_date, CURDATE()) as days_left
                FROM Events e 
                JOIN Venues v ON e.venue_id = v.venue_id
                LEFT JOIN Bookings b ON e.event_id = b.event_id 
                    AND b.status = 'confirmed'
                WHERE e.event_id = %s
                GROUP BY e.event_id, v.capacity
            """, (event_id,))
            result = cursor.fetchone()
            
            if result and result['days_left'] <= 10 and result['booked_count'] < result['capacity'] * 0.5:
                return round(float(result['base_price']) * 0.75, 2)
            return float(result['base_price']) if result else 0
    finally:
        conn.close()

def calculate_available_slots(event_id, specific_date=None):
    """Req 1: Venue capacity check"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if specific_date:  # Multi-day event specific date
                cursor.execute("""
                    SELECT v.capacity - COALESCE(SUM(b.num_tickets), 0) as available
                    FROM Events e 
                    JOIN Venues v ON e.venue_id = v.venue_id
                    LEFT JOIN Bookings b ON e.event_id = b.event_id 
                        AND b.event_date = %s AND b.status = 'confirmed'
                    WHERE e.event_id = %s
                """, (specific_date, event_id))
            else:
                cursor.execute("""
                    SELECT v.capacity - COALESCE(SUM(b.num_tickets), 0) as available
                    FROM Events e 
                    JOIN Venues v ON e.venue_id = v.venue_id
                    LEFT JOIN Bookings b ON e.event_id = b.event_id 
                        AND b.status = 'confirmed'
                    WHERE e.event_id = %s
                """, (event_id,))
            
            result = cursor.fetchone()
            return result['available'] if result else 0
    finally:
        conn.close()

def generate_receipt(booking_id):
    """Req 2: Complete price breakdown"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.*, e.title, e.base_price, e.start_date, u.email
                FROM Bookings b
                JOIN Events e ON b.event_id = e.event_id
                JOIN Users u ON b.user_id = u.user_id
                WHERE b.booking_id = %s
            """, (booking_id,))
            booking = cursor.fetchone()
            
            days_advance = calculate_days_advance(booking['start_date'])
            advance_discount = get_advance_discount(days_advance)
            
            receipt = {
                'booking_id': booking['booking_id'],
                'event': booking['title'],
                'date': booking['event_date'].strftime('%Y-%m-%d'),
                'tickets': booking['num_tickets'],
                'base_price_per_ticket': booking['original_price'] / booking['num_tickets'] if booking['num_tickets'] else 0,
                'advance_discount': f"{advance_discount*100}%",
                'student_discount': f"{(booking['student_discount']/booking['original_price']*100) if booking['original_price'] else 0}%",
                'final_price': booking['final_price'],
                'disclaimer': 'Students: Bring student ID to event'
            }
            return receipt
    finally:
        conn.close()

# ROUTES
@app.route('/')
def home():
    return render_template('webUI.html')

# AUTH ROUTES (CHANGED)
@app.route('/api/signup', methods=['POST'])
@limiter.limit("5 per minute")
def signup():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    is_student = data.get('is_student', False)
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Users (email, password_hash, first_name, last_name, role, is_student) VALUES (%s, %s, %s, %s, 'user', %s)",
                (email, hashed_password, 'User', 'Account', is_student)
            )
            conn.commit()
        return jsonify({'message': 'User created successfully'}), 201
    except pymysql.err.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                token = jwt.encode({
                    'id': user['user_id'],
                    'role': user['role'],
                    'exp': datetime.datetime.utcnow() + timedelta(hours=24)
                }, SECRET_KEY, algorithm="HS256")
                
                return jsonify({
                    'message': 'Login successful',
                    'token': token,
                    'role': user['role'],
                    'is_student': user['is_student']
                }), 200
            return jsonify({'error': 'Invalid credentials'}), 401
    finally:
        conn.close()

# EVENTS ROUTES (CHANGED/ADDED)
@app.route('/api/events', methods=['GET'])
def get_events():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.*, v.name as venue_name, v.capacity
                FROM Events e 
                LEFT JOIN Venues v ON e.venue_id = v.venue_id
                ORDER BY e.start_date
            """)
            events = cursor.fetchall()

        response = []
        for event in events:
            event['current_price'] = get_current_price(event['event_id'])
            event['available_slots'] = calculate_available_slots(event['event_id'])
            response.append(serialize_row(event))

        return jsonify(response), 200
    finally:
        conn.close()

@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT e.*, v.name as venue_name, v.capacity
                FROM Events e
                LEFT JOIN Venues v ON e.venue_id = v.venue_id
                WHERE e.event_id = %s
            """, (event_id,))
            event = cursor.fetchone()
            if not event:
                return jsonify({'error': 'Event not found'}), 404

            event['current_price'] = get_current_price(event_id)
            event['available_slots'] = calculate_available_slots(event_id)
            return jsonify(serialize_row(event)), 200
    finally:
        conn.close()

@app.route('/api/admin/events/add', methods=['POST'])
@token_required
@admin_required
@validate_event_data
def add_event(current_user_id, current_user_role):
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Handle multi-day events (Req 6)
            duration_days = 1
            end_date = data['start_date']
            if 'duration_days' in data:
                duration_days = data['duration_days']
                end_date = (date.fromisoformat(data['start_date']) + 
                           timedelta(days=duration_days-1)).isoformat()
            
            cursor.execute("""
                INSERT INTO Events (title, category, start_date, end_date, 
                                  duration_days, venue_id, base_price)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (data['title'], data['category'], data['start_date'], 
                  end_date, duration_days, data['venue_id'], data['base_price']))
            conn.commit()
            return jsonify({'message': 'Event created successfully'}), 201
    finally:
        conn.close()

# BOOKING ROUTES (ADDED)
@app.route('/api/bookings/book', methods=['POST'])
@token_required
@limiter.limit("10 per hour")
def create_booking(current_user_id, current_user_role):
    data = request.json
    event_id = data['event_id']
    num_tickets = data.get('num_tickets', 1)
    specific_date = data.get('event_date')  # Req 6: Multi-day
    is_student = data.get('is_student', False)
    
    # Req 1: Capacity check
    available = calculate_available_slots(event_id, specific_date)
    if available < num_tickets:
        # Req 4: Waiting list
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO WaitingList (user_id, event_id, event_date)
                    VALUES (%s, %s, %s)
                """, (current_user_id, event_id, specific_date))
                conn.commit()
                position = cursor.lastrowid
            return jsonify({
                'message': 'Event full. Added to waiting list.',
                'position': position
            }), 200
        finally:
            conn.close()
    
    # Pricing calculation (Req 2,3,5,6)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Events WHERE event_id = %s", (event_id,))
            event = cursor.fetchone()
            if not event:
                return jsonify({'error': 'Event not found'}), 404
            
            current_price = get_current_price(event_id)
            daily_price = current_price / event['duration_days'] if event['duration_days'] > 1 else current_price
            
            days_advance = calculate_days_advance(date.fromisoformat(specific_date or event['start_date']))
            advance_disc = get_advance_discount(days_advance)
            student_disc = 0.10 if is_student else 0
            
            total_base = daily_price * num_tickets
            total_discount = total_base * (advance_disc + student_disc)
            final_price = total_base - total_discount
            
            # Create booking
            cursor.execute("""
                INSERT INTO Bookings (user_id, event_id, event_date, num_tickets,
                                    original_price, discount_amount, final_price, 
                                    student_discount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (current_user_id, event_id, specific_date or event['start_date'],
                  num_tickets, total_base, total_discount, final_price,
                  total_base * student_disc))
            conn.commit()
            
            booking_id = cursor.lastrowid
            receipt = generate_receipt(booking_id)
            
        return jsonify({
            'success': True,
            'booking_id': booking_id,
            'receipt': receipt
        }), 201
    finally:
        conn.close()

@app.route('/api/bookings/cancel/<int:booking_id>', methods=['POST'])
@token_required
def cancel_booking(current_user_id, current_user_role, booking_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verify ownership
            cursor.execute("SELECT * FROM Bookings WHERE booking_id = %s", (booking_id,))
            booking = cursor.fetchone()
            if not booking or booking['user_id'] != current_user_id:
                return jsonify({'error': 'Booking not found or unauthorized'}), 404
            
            days_to_event = (booking['event_date'] - date.today()).days
            
            # Req 7: Cancellation charges
            if days_to_event >= 40:
                charge = 0
            elif 25 <= days_to_event < 40:
                charge = booking['final_price'] * 0.40
            else:
                charge = booking['final_price']
            
            cursor.execute("""
                UPDATE Bookings 
                SET status = 'cancelled', cancellation_charge = %s 
                WHERE booking_id = %s
            """, (charge, booking_id))
            conn.commit()
            
            # Req 4: Notify waiting list
            cursor.execute("""
                SELECT * FROM WaitingList 
                WHERE event_id = %s AND status = 'pending' 
                ORDER BY request_timestamp ASC LIMIT 1
            """, (booking['event_id'],))
            wait_user = cursor.fetchone()
            
            if wait_user:
                # Auto-confirm first waiting list user if slots available
                available = calculate_available_slots(booking['event_id'])
                if available > 0:
                    cursor.execute("""
                        INSERT INTO Bookings (user_id, event_id, event_date, 
                                           num_tickets, original_price, final_price)
                        VALUES (%s, %s, %s, 1, %s, %s)
                    """, (wait_user['user_id'], booking['event_id'], 
                          booking['event_date'], booking['original_price'], 
                          booking['final_price']))
                    cursor.execute("UPDATE WaitingList SET status = 'confirmed' WHERE wait_id = %s", 
                                 (wait_user['wait_id'],))
                    conn.commit()
        
        return jsonify({
            'message': 'Booking cancelled',
            'cancellation_charge': charge
        }), 200
    finally:
        conn.close()

@app.route('/api/bookings/my-bookings', methods=['GET'])
@token_required
def get_user_bookings(current_user_id, current_user_role):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.*, e.title, e.start_date, v.name as venue
                FROM Bookings b
                JOIN Events e ON b.event_id = e.event_id
                JOIN Venues v ON e.venue_id = v.venue_id
                WHERE b.user_id = %s
                ORDER BY b.event_date DESC
            """, (current_user_id,))
            bookings = cursor.fetchall()
        return jsonify(bookings), 200
    finally:
        conn.close()

# Admin routes (existing + added)
@app.route('/api/admin/users', methods=['GET'])
@token_required
@admin_required
def get_all_users(current_user_id, current_user_role):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, email, role, is_student, created_at FROM Users")
            users = cursor.fetchall()
        return jsonify(users), 200
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)