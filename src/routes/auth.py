from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login route: accepts JSON {username, password} and authenticates.

    Behavior:
    - Expects JSON with 'username' and 'password'.
    - Attempts to import User from src.models.user and db from src.models.
    - Supports the following password checks in order:
        1) If User has method `check_password`, call it with the raw password.
        2) If User has attribute `password_hash`, use werkzeug.security.check_password_hash.
        3) If User has attribute `password`, compare raw equality (not recommended).
    - Returns 200 and basic user info on success, 400/401/500 on errors.
    """
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400

    try:
        # Lazy import so app can still run if User model isn't present yet.
        from src.models.user import User
        from src.models import db
    except Exception as e:
        return jsonify({'error': 'User model not available', 'detail': str(e)}), 500

    try:
        # Attempt to find the user by username field (try common column names)
        user = None
        for field in ('username', 'email'):
            try:
                user = User.query.filter(getattr(User, field) == username).first()
                if user:
                    break
            except Exception:
                # If the attribute doesn't exist on the model, skip
                user = None

        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401

        # 1) Prefer check_password method if model provides it
        if hasattr(user, 'check_password') and callable(getattr(user, 'check_password')):
            valid = user.check_password(password)
        # 2) Fall back to password_hash attribute
        elif hasattr(user, 'password_hash'):
            valid = check_password_hash(getattr(user, 'password_hash'), password)
        # 3) As last resort, compare raw password field (insecure)
        elif hasattr(user, 'password'):
            valid = (getattr(user, 'password') == password)
        else:
            return jsonify({'error': 'No password verifier available for User model'}), 500

        if not valid:
            return jsonify({'error': 'Invalid credentials'}), 401

        # Success: return minimal user info
        user_info = None
        try:
            user_info = user.to_dict()
        except Exception:
            # fallback to basic fields
            user_info = {'id': getattr(user, 'id', None), 'username': getattr(user, 'username', None)}

        return jsonify({'message': 'Login successful', 'user': user_info}), 200

    except Exception as e:
        return jsonify({'error': 'Authentication failed', 'detail': str(e)}), 500


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user. Expects JSON: {username, email, password}.

    - username (required), password (required), email (optional)
    - hashes password using werkzeug.generate_password_hash via User.set_password
    - returns 201 with user info on success
    """
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400

    try:
        from src.models.user import User
        from src.models import db
    except Exception as e:
        return jsonify({'error': 'User model not available', 'detail': str(e)}), 500

    # Check uniqueness
    existing = None
    try:
        existing = User.query.filter((User.username == username) | (User.email == email)).first()
    except Exception:
        # If email attr is not present or other issue, try username-only
        existing = User.query.filter_by(username=username).first()

    if existing:
        return jsonify({'error': 'User with that username or email already exists'}), 400

    try:
        user = User(username=username, email=email)
        # Use model helper if available
        if hasattr(user, 'set_password') and callable(getattr(user, 'set_password')):
            user.set_password(password)
        else:
            # Fallback: set password_hash directly
            from werkzeug.security import generate_password_hash
            user.password_hash = generate_password_hash(password)

        db.session.add(user)
        db.session.commit()

        return jsonify({'message': 'User created', 'user': user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create user', 'detail': str(e)}), 500
