from datetime import datetime
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from aiohttp import ClientSession
import asyncio

load_dotenv()
app = Flask(__name__)


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


async def fetch_url(session, url, method="POST", data=None):
    async with session.post(url, json=data) as response:
        return await response.json()


@app.route("/")
def hello():
    return {"message": "Welcome to GPT-Conversation Data Collector API"}


@app.route("/generate_conversation", methods=["POST"])
def generate_conversation():
    data = request.json
    server_urls = [data.get("server_url")]
    server_urls.append(data.get("server_url_2", server_urls[0]))

    async def process_conversation():
        async with ClientSession() as session:
            # Initialize chats
            responses = await asyncio.gather(
                *[fetch_url(session, f"{url}/start") for url in server_urls]
            )
            chat_one_id = responses[0]["chatId"]
            chat_two_id = responses[1]["chatId"]

            # Send initial messages
            initial_response_one = await fetch_url(
                session,
                f"{server_urls[0]}/conversation/",
                data={
                    "chatId": chat_one_id,
                    "prompt": f"{data['initial_message']} topic: {data['topic']}",
                },
            )
            initial_response_two = await fetch_url(
                session,
                f"{server_urls[1]}/conversation/",
                data={
                    "chatId": chat_two_id,
                    "prompt": f"{data['initial_message']} topic: {data['topic']}",
                },
            )

            # Generate conversation
            no_conversation = 0
            chat_one_response = initial_response_one
            chat_two_response = await fetch_url(
                session,
                f"{server_urls[1]}/conversation/",
                data={"chatId": chat_two_id, "prompt": "You start the conversation"},
            )

            for _ in range(data["max_prompt"]):
                chat_one_response = await fetch_url(
                    session,
                    f"{server_urls[0]}/conversation/",
                    data={
                        "chatId": chat_one_id,
                        "prompt": chat_two_response["response"],
                    },
                )
                chat_two_response = await fetch_url(
                    session,
                    f"{server_urls[1]}/conversation/",
                    data={
                        "chatId": chat_two_id,
                        "prompt": chat_one_response["response"],
                    },
                )
                no_conversation += 1

            return {
                "message": "Conversation generated successfully.",
                "no_conversation": no_conversation,
            }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(process_conversation())
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 400


app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
