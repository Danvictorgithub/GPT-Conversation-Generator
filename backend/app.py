from datetime import datetime
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
import requests
import argparse
import logging
from time import sleep
from concurrent.futures import ThreadPoolExecutor

# Update environment loading to look for .env in parent directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8000)
args = parser.parse_args()

# Initialize Flask with proper startup logging
app = Flask(__name__)
app.config['STARTUP_COMPLETE'] = False
executor = ThreadPoolExecutor(max_workers=10)

# Add logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Remove @app.before_first_request and replace with startup function
def configure_app():
    app.config['STARTUP_COMPLETE'] = True
    logger.info("Flask application is ready to handle requests")

# Add this after your routes
@app.before_request
def before_request():
    if not app.config.get('STARTUP_COMPLETE', False):
        configure_app()
    logger.info(f"Request to {request.path} with method {request.method}")

class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class Conversation(db.Model):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    start_conversation: Mapped[str] = mapped_column()
    end_conversation: Mapped[str] = mapped_column()
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class HTTPMethod:
    GET = "GET"
    POST = "POST"

def fetch_url(url, method=HTTPMethod.POST, data=None, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, json=data, timeout=30)
            if response.status_code == 200:
                return response.json()
            logging.error(f"Request failed with status {response.status_code}")
        except Exception as e:
            logging.error(f"Request attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                sleep(2 ** attempt)  # Exponential backoff
    return None

@app.route("/")
def hello():
    return {"message": "Welcome to GPT-Conversation Data Collector API"}


def clean_text(text):
    """Clean any remaining problematic characters"""
    if not text:
        return text
    
    import re
    # Only clean basic formatting, main cleaning is done by LLM server
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

@app.route("/generate_conversation", methods=["POST"])
def generate_conversation():
    try:
        data = request.json
        if not data:
            return {"message": "No data provided"}, 400

        server_url = data.get('server_url')
        server_url_2 = data.get('server_url_2', server_url)  # Use same URL if second not provided
        initial_message = data.get('initial_message')
        topic = data.get('topic')
        max_prompt = data.get('max_prompt', 5)

        # Initialize chat sessions
        try:
            response1 = fetch_url(f"{server_url}/start")
            response2 = fetch_url(f"{server_url_2}/start")
            
            if not response1 or not response2:
                return {"message": "Failed to initialize chat sessions"}, 500
            
            chat_one = response1["chatId"]
            chat_two = response2["chatId"]
            
            logging.info("Chat sessions initialized")
            
            # Send initial messages
            initial_prompt = f"{initial_message} topic: {topic}"
            initial_response_one = fetch_url(
                f"{server_url}/conversation",
                data={"chatId": chat_one, "prompt": initial_prompt}
            )
            
            initial_response_two = fetch_url(
                f"{server_url_2}/conversation",
                data={"chatId": chat_two, "prompt": initial_prompt}
            )
            
            if not initial_response_one or not initial_response_two:
                return {"message": "Failed to send initial messages"}, 500

            # Start conversation loop
            no_conversation = 0
            chat_one_response = initial_response_one
            
            # Start the conversation with second chat
            chat_two_response = fetch_url(
                f"{server_url_2}/conversation",
                data={"chatId": chat_two, "prompt": "You start the conversation"}
            )

            # Main conversation loop
            for _ in range(max_prompt):
                if not chat_two_response:
                    break

                # First chat responds to second
                chat_one_response = fetch_url(
                    f"{server_url}/conversation",
                    data={"chatId": chat_one, "prompt": chat_two_response["response"]}
                )
                if not chat_one_response:
                    break
                
                logging.info(f"Chat One response: {chat_one_response['response'][:100]}...")
                # sleep(10)  # Wait between responses

                # Second chat responds to first
                chat_two_response = fetch_url(
                    f"{server_url_2}/conversation",
                    data={"chatId": chat_two, "prompt": chat_one_response["response"]}
                )
                if not chat_two_response:
                    break

                logging.info(f"Chat Two response: {chat_two_response['response'][:100]}...")
                
                # Save responses directly since they're already cleaned by the LLM server
                if chat_one_response and chat_two_response:
                    conversation = Conversation(
                        start_conversation=chat_one_response["response"],
                        end_conversation=chat_two_response["response"]
                    )
                    db.session.add(conversation)
                    db.session.commit()
                
                no_conversation += 1
                logging.info(f"Conversation pair {no_conversation} saved")
                sleep(10)

            return {"message": "Conversation generated successfully", "pairs_generated": no_conversation}

        except Exception as e:
            logging.error(f"Error during conversation: {str(e)}")
            return {"message": str(e), "pairs_generated": no_conversation}, 400

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return {"message": str(e)}, 500

@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"}), 200


app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
with app.app_context():
    db.create_all()

# Modified startup code
if __name__ == "__main__":
    logger.info(f"Starting Flask application on port {args.port}")
    try:
        app.run(
            host='0.0.0.0', 
            port=args.port, 
            debug=False
        )
    except Exception as e:
        logger.error(f"Failed to start Flask application: {e}")
        raise
