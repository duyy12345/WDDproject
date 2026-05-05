from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

SECRET_KEY = "BCE_SECRET_KEY"

def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1',   # Use IP to avoid socket issues
        port=3306,           # Explicit port (change to 3307 if XAMPP uses that)
        user='root',
        password='',         # XAMPP default is empty
        db='bce_system',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# ─────────────────────────────────────────────
#  Auth Decorators
# ─────────────────────────────────────────────
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_id = data['id']
            current_user_role = data.get('role', 'user')
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token!'}), 401
        return f(current_user_id, current_user_role, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            if data.get('role') != 'admin':
                return jsonify({'error': 'Admin access required!'}), 403
            current_user_id = data['id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token!'}), 401
        return f(current_user_id, *args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
#  Basic Routes
# ─────────────────────────────────────────────
@app.route('/')
def home():
    return "Flask Backend is running normally!"

@app.route('/test-db')
def test_db():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            result = cursor.fetchone()
        connection.close()
        return jsonify({"status": "Success", "version": result})
    except Exception as e:
        return jsonify({"status": "Connection Error", "error": str(e)})

# ─────────────────────────────────────────────
#  Public Routes
# ─────────────────────────────────────────────
@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT e.*, v.name as venue_name, v.capacity 
            FROM Events e 
            LEFT JOIN Venues v ON e.venue_id = v.venue_id
        """
        cursor.execute(query)
        events = cursor.fetchall()
        conn.close()
        return jsonify(events), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─────────────────────────────────────────────
#  Auth Routes
# ─────────────────────────────────────────────
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided!'}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Please provide both email and password!'}), 400

    hashed_password = generate_password_hash(password)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO Users (email, password, role) VALUES (%s, %s, %s)"
        cursor.execute(sql, (email, hashed_password, 'user'))
        conn.commit()
        return jsonify({'message': 'Registration successful!'}), 201
    except pymysql.err.IntegrityError:
        return jsonify({'error': 'Email already exists!'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            if conn and conn.open:
                conn.close()
        except Exception:
            pass

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided!'}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Please provide both email and password!'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'message': 'Email does not exist'}), 401
        if not check_password_hash(user['password'], password):
            return jsonify({'message': 'Incorrect password'}), 401

        token = jwt.encode({
            'id': user['user_id'],
            'role': user.get('role', 'user'),
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, SECRET_KEY, algorithm="HS256")

        return jsonify({
            'message': 'Login successful',
            'token': token,
            'role': user.get('role', 'user')
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            if conn and conn.open:
                conn.close()
        except Exception:
            pass

# ─────────────────────────────────────────────
#  Admin Routes (protected by @admin_required)
# ─────────────────────────────────────────────
@app.route('/api/admin/events', methods=['GET'])
@admin_required
def admin_get_events(current_user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Events")
        data = cursor.fetchall()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/events/add', methods=['POST'])
@admin_required
def add_event(current_user_id):
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided!'}), 400

    title = data.get('title')
    category = data.get('category')
    start_date = data.get('start_date')
    venue_id = data.get('venue_id')
    base_price = data.get('base_price')

    if not all([title, category, start_date, venue_id, base_price is not None]):
        return jsonify({'error': 'All fields are required!'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO Events (title, category, start_date, venue_id, base_price) 
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (title, category, start_date, venue_id, base_price))
        conn.commit()
        return jsonify({'message': 'Event added successfully!'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            if conn and conn.open:
                conn.close()
        except Exception:
            pass

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_all_users(current_user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, email, role FROM Users")
        users = cursor.fetchall()
        conn.close()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─────────────────────────────────────────────
#  Run
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, port=5000)
