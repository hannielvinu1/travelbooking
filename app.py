from db import get_db
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO
import base64
from models import init_db, User, Booking
import random
from dotenv import load_dotenv 
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
 # <-- for loading .env file

# Load environment variables from .env (if present)
load_dotenv()

app = Flask(__name__)
CORS(app)

# Get secret key from environment or generate one for dev
SECRET_KEY = os.environ.get("SESSION_SECRET")

if not SECRET_KEY:
    # Automatically create a random dev key if not set
    import secrets
    SECRET_KEY = secrets.token_hex(32)
    print("⚠️  WARNING: SESSION_SECRET not found — using a temporary key for development.")

app.config["SECRET_KEY"] = SECRET_KEY
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return jsonify({"message": "Token is missing"}), 401

        if token.startswith("Bearer "):
            token = token[7:]

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user = User.get_by_id(data["user_id"])
            if not current_user:
                return jsonify({"message": "User not found"}), 401
        except Exception as e:
            return jsonify({"message": "Token is invalid", "error": str(e)}), 401

        return f(current_user, *args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user["role"] != "admin":
            return jsonify({"message": "Admin access required"}), 403
        return f(current_user, *args, **kwargs)

    return decorated


def generate_qr_code(booking_id, booking_details):
    qr_data = f"Booking ID: {booking_id}\n"
    qr_data += f"From: {booking_details['from_place']}\n"
    qr_data += f"To: {booking_details['to_place']}\n"
    qr_data += f"Date: {booking_details['date']}\n"
    qr_data += f"Passenger: {booking_details['passenger_name']}\n"
    qr_data += f"Seat: {booking_details['seat_no']}\n"
    qr_data += f"Fare: ₹{booking_details['fare']}"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    filename = f"booking_{booking_id}.png"
    filepath = os.path.join("uploads", "qr_codes", filename)
    img.save(filepath)

    return f"/api/uploads/qr_codes/{filename}"


@app.route("/api/register", methods=["POST"])
def register():
    data = request.json

    if not data or not data.get("name") or not data.get("email") or not data.get("password"):
        return jsonify({"message": "Missing required fields"}), 400

    user_id = User.create(data["name"], data["email"], data["password"])

    if not user_id:
        return jsonify({"message": "Email already exists"}), 400

    return jsonify({"message": "User registered successfully", "user_id": user_id}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json

    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"message": "Missing email or password"}), 400

    user = User.get_by_email(data["email"])

    if not user or not User.verify_password(user, data["password"]):
        return jsonify({"message": "Invalid email or password"}), 401

    token = jwt.encode(
        {
            "user_id": user["id"],
            "role": user["role"],
            "exp": datetime.utcnow() + timedelta(days=7),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    return jsonify(
        {
            "token": token,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
            },
        }
    ), 200


@app.route("/api/search", methods=["POST"])
def search():
    data = request.json
    from_place = data.get("from")
    to_place = data.get("to")
    date = data.get("date")

    transport_types = [
        {"type": "airplane", "icon": "✈️", "name": "Airplane"},
        {"type": "bus", "icon": "🚌", "name": "Bus"},
        {"type": "train", "icon": "🚆", "name": "Train"},
        {"type": "hotel", "icon": "🏨", "name": "Hotel"},
    ]

    results = []
    for transport in transport_types:
        num_options = random.randint(2, 4)
        for i in range(num_options):
            fare = random.randint(500, 10000)
            result = {
                "id": f"{transport['type']}_{i}",
                "type": transport["type"],
                "icon": transport["icon"],
                "name": f"{transport['name']} Option {i+1}",
                "from": from_place,
                "to": to_place,
                "date": date,
                "fare": fare,
                "available_seats": random.randint(5, 50),
            }
            results.append(result)

    return jsonify(results), 200


@app.route("/api/bookings", methods=["POST"])
@token_required
def create_booking(current_user):
    data = request.json

    required_fields = [
        "transport_type",
        "from_place",
        "to_place",
        "date",
        "passenger_name",
        "phone",
        "email",
        "seat_no",
        "fare",
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({"message": f"Missing field: {field}"}), 400

    booking_id = Booking.create(
        user_id=current_user["id"],
        transport_type=data["transport_type"],
        name=data.get("name"), 
        from_place=data["from_place"],
        to_place=data["to_place"],
        date=data["date"],
        passenger_name=data["passenger_name"],
        phone=data["phone"],
        email=data["email"],
        seat_no=data["seat_no"],
        fare=data["fare"],
    )

    qr_code_url = generate_qr_code(booking_id, data)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET qr_code_url = ? WHERE id = ?", (qr_code_url, booking_id))
    conn.commit()
    conn.close()

    booking = Booking.get_by_id(booking_id)

    return jsonify({"message": "Booking created successfully", "booking": booking}), 201


@app.route("/api/bookings", methods=["GET"])
@token_required
def get_bookings(current_user):
    if current_user["role"] == "admin":
        bookings = Booking.get_all()
    else:
        bookings = Booking.get_by_user(current_user["id"])

    return jsonify(bookings), 200


@app.route("/api/bookings/<int:booking_id>", methods=["GET"])
@token_required
def get_booking(current_user, booking_id):
    booking = Booking.get_by_id(booking_id)

    if not booking:
        return jsonify({"message": "Booking not found"}), 404

    if current_user["role"] != "admin" and booking["user_id"] != current_user["id"]:
        return jsonify({"message": "Access denied"}), 403

    return jsonify(booking), 200


@app.route("/api/bookings/<int:booking_id>/payment", methods=["POST"])
@token_required
def upload_payment(current_user, booking_id):
    booking = Booking.get_by_id(booking_id)

    if not booking:
        return jsonify({"message": "Booking not found"}), 404

    if booking["user_id"] != current_user["id"]:
        return jsonify({"message": "Access denied"}), 403

    if "file" not in request.files:
        return jsonify({"message": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"message": "No file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(
            f"payment_{booking_id}_{datetime.now().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}"
        )
        filepath = os.path.join("uploads", "payments", filename)
        file.save(filepath)

        payment_url = f"/api/uploads/payments/{filename}"
        Booking.update_payment_proof(booking_id, payment_url)

        return jsonify(
            {"message": "Payment proof uploaded successfully", "payment_url": payment_url}
        ), 200

    return jsonify({"message": "Invalid file type"}), 400


@app.route("/api/admin/bookings/<int:booking_id>/verify", methods=["PUT"])
@token_required
@admin_required
def verify_booking(current_user, booking_id):
    data = request.json
    action = data.get("action")

    if action not in ["approve", "reject"]:
        return jsonify({"message": "Invalid action"}), 400

    booking = Booking.get_by_id(booking_id)

    if not booking:
        return jsonify({"message": "Booking not found"}), 404

    if action == "approve":
        Booking.update_status(booking_id, "Confirmed")
        message = "Booking approved successfully"
    else:
        Booking.update_status(booking_id, "Rejected")
        message = "Booking rejected"

    return jsonify({"message": message}), 200


@app.route("/api/uploads/<path:subpath>/<filename>")
def serve_upload(subpath, filename):
    return send_from_directory(os.path.join("uploads", subpath), filename)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    os.makedirs("uploads/payments", exist_ok=True)
    os.makedirs("uploads/qr_codes", exist_ok=True)
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
