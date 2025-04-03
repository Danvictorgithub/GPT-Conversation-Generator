import asyncio
import logging
import random
import signal
import argparse
from aiohttp import ClientSession
from time import sleep

stop_fetching = False

# Define comprehensive chat settings
chatSettings = [
    {
        "topic": "life",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Lets pretend to have a basic conversation, also don't say that you are an AI, and dont repeat yourself, please respond with short paragraphs and limit to a basic vocabulary and grammar, I will do the same. I repeat respond with short paragraph, Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "work",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Lets pretend to have a basic conversation with minimal vocabulary, I also want you do limit your response to short paragraphs, I will do the same. I repeat respond with short paragraph, Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "travel",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "school",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "food",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!. You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "technology",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "life",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Lets pretend to have a basic conversation, also don't say that you are an AI, and dont repeat yourself, please respond with short paragraphs and limit to a basic vocabulary and grammar, I will do the same. I repeat respond with short paragraph, Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "Games",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "Entertainment",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "Books",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "Music",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    },
    {
        "topic": "Movies",
        "initial_message": "Respond to the following statement without using the word 'Exactly!', or 'Absolutely!' or 'Definitely!' because it doesn't sound human at the beginning:Let's have a simple conversation using limited vocabulary. Please keep your responses brief, and I'll do the same. Avoid repeating 'Absolutely!'You can also try to change topic if you are starting to just agree with the statement I don't want a loop of conversation just saying 'I agree!' or any statement like that'"
    }
]

class HTTPMethod:
    GET = "GET"
    POST = "POST"

# Signal handler for graceful shutdown
def signal_handler(signal, frame):
    global stop_fetching
    stop_fetching = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Generate a random subject for conversation
def generate_random_subject():
    subjects = [
        "Technology", "Science", "Health", "Education", "Business", "Entertainment", 
        "Sports", "Politics", "Environment", "History", "Travel", "Food", "Music", 
        "Books", "Movies", "Fashion", "Hobbies", "Relationships", "Fitness", "Culture",
        "Games", "Cartoons", "Toys", "Friends", "School", "Holidays"
    ]
    return random.choice(subjects)

# Fetch URL with retry logic
async def fetch_with_retry(url, method, data=None, max_retries=5, delay=1):
    attempt = 0
    while attempt < max_retries:
        try:
            async with ClientSession() as session:
                async with session.request(method, url, json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    logging.error(f"Request failed with status {response.status}")
        except Exception as e:
            logging.error(f"Request exception: {e}")
        
        attempt += 1
        if attempt < max_retries:
            await asyncio.sleep(delay)
    return None

# Generate conversation pair
async def generate_conversation_pair(flask_url, server_url, chat_setting, max_prompt):
    try:
        # Initialize chat sessions
        data = {
            "server_url": server_url,
            "initial_message": chat_setting["initial_message"],
            "topic": chat_setting["topic"],
            "max_prompt": max_prompt
        }
        
        response = await fetch_with_retry(
            f"{flask_url}/generate_conversation",
            HTTPMethod.POST,
            data
        )
        
        if not response:
            logging.error("Failed to generate conversation")
            return False
            
        logging.info(f"Successfully generated conversation with {max_prompt} prompts")
        return True

    except Exception as e:
        logging.error(f"Error generating conversation: {e}")
        return False

# Continuous fetch loop for each server
async def continuous_fetch(server_index, flask_server_url, gpt_server, chat_setting, max_prompt):
    retries = 0
    while not stop_fetching:
        try:
            logging.info(f"Starting conversation generation for server {server_index + 1}")
            success = await generate_conversation_pair(
                flask_server_url,
                gpt_server,
                chat_setting,
                max_prompt
            )
            
            if success:
                chat_setting["topic"] = generate_random_subject()
                retries = 0
                await asyncio.sleep(10)  # Wait between conversations
            else:
                retries += 1
                if retries >= 5:
                    logging.error(f"Max retries reached for server {server_index + 1}")
                    break
                await asyncio.sleep(30)  # Longer wait on failure
                
        except Exception as e:
            logging.error(f"Error in fetch loop for server {server_index + 1}: {e}")
            retries += 1
            if retries >= 5:
                break
            await asyncio.sleep(30)

async def main():
    tasks = [
        continuous_fetch(
            i,
            flask_server_url,
            gpt_servers[i],
            random.choice(chatSettings),
            max_prompt
        ) for i in range(args.n)
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to send configuration to Flask server.")
    parser.add_argument('-n', type=int, default=10, help="Number of GPT servers (default is 10)")
    parser.add_argument('--flask_server', type=str, default="http://localhost:8000", help="Flask server URL")
    parser.add_argument('--max_prompt', type=int, default=5, help="Maximum number of prompts per conversation")
    args = parser.parse_args()

    n_value = args.n
    flask_server_url = args.flask_server
    max_prompt = args.max_prompt
    gpt_servers = [f"http://localhost:{8080 + i}" for i in range(n_value)]

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        stop_fetching = True
        print("Shutting down gracefully...")