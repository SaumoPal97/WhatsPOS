import os
import threading
from services.db import db
from flask import Flask, request, jsonify
from services.agent import process_whatsapp_message
from services.whatsapp import send_text_message, send_media_message
from services.db import User

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR}/database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        query_params = request.args.to_dict()  # Parse query parameters
        mode = query_params["hub.mode"]
        challenge = query_params["hub.challenge"]
        verify_token = query_params["hub.verify_token"]

        if mode is not None and verify_token == os.environ.get("WEBHOOK_SECRET"):
            return challenge
        return jsonify({"error": "Invalid or missing query params"}), 400

    if request.method == 'POST':
        body = request.get_json(silent=True)  # Parse JSON body
        if body is None:
            return jsonify({"error": "Invalid or missing JSON body"}), 400
        print("body", body)

         # Start long task in a separate thread
        thread = threading.Thread(target=handle_whatsapp_message, args=(body,))
        thread.start()
        return jsonify({"message": "Received POST request", "body": body})



# Extracting the relevant data
def extract_message_info(data):
    try:
        entry = data.get("entry", [])[0]  # Get first entry
        changes = entry.get("changes", [])[0]  # Get first change
        value = changes.get("value", {})

        # Extract phone number and name
        contact = value.get("contacts", [])[0]
        name = contact.get("profile", {}).get("name")
        phone_number = contact.get("wa_id")

        # Extract message text
        message = value.get("messages", [])[0]
        message_text = message.get("text", {}).get("body")

        return {
            "user_phone": phone_number,
            "user_name": name,
            "message": message_text
        }
    
    except IndexError:
        return {"error": "Invalid JSON structure"}
    

def handle_whatsapp_message(data):
    with app.app_context():
        body = extract_message_info(data)
        if body.get("error", None) is None:
            user_phone = body["user_phone"]
            message = body["message"]
            user_name = body["user_name"]


            # Check if user exists
            user = User.query.filter_by(phone_number=user_phone).first()
            
            if not user:
                # Create new user
                user = User(phone_number=user_phone, user_name=user_name)
                db.session.add(user)
                db.session.commit()
                
                # Send welcome messages
                welcome_message = (
                    f"Welcome {user_name}! 👋\n\n"
                    "I'm your business assistant. Here's how you can use me:\n\n"
                    "1️⃣ Add inventory: 'add 5 apples at $2 each'\n"
                    "2️⃣ Record income: 'received $100 from sales'\n"
                    "3️⃣ Record expense: 'spent $50 on supplies'\n"
                    "4️⃣ Get reports: 'show me today's sales'\n"
                    "5️⃣ View graphs: 'show sales graph for last week'\n\n"
                    "Let's start by adding your first inventory item! 📦"
                )
                send_text_message(welcome_message, user_phone)
                return
            
            # Process message for existing user
            response = process_whatsapp_message(message, user.id)
            if response["type"] == "text":
                send_text_message(response["content"], user_phone)
            else:
                send_media_message(response["content"], response["caption"], user_phone)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
