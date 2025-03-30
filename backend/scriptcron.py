import asyncio
import logging
import random
import signal
import argparse
from aiohttp import ClientSession

# Define the number of servers
n_value = 16

# Define chatSettings (example settings, replace with actual settings)
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

stop_fetching = False

def signal_handler(signal, frame):
    global stop_fetching
    stop_fetching = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def generate_random_subject():
    subjects = [
        "Technology", "Science", "Health", "Education", "Business", "Entertainment", 
        "Sports", "Politics", "Environment", "History", "Travel", "Food", "Music", 
        "Books", "Movies", "Fashion", "Hobbies", "Relationships", "Fitness", "Culture",
        "Games", "Cartoons", "Toys", "Friends", "School", "Holidays"
    ]
    
    return random.choice(subjects)

class HTTPMethod:
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

async def fetch_url(url, method: HTTPMethod = HTTPMethod.GET, *args, **kwargs):
    async with ClientSession() as session:
        method_action = {
            HTTPMethod.GET: session.get,
            HTTPMethod.POST: session.post,
            HTTPMethod.DELETE: session.delete,
            HTTPMethod.PUT: session.put,
        }.get(method, session.get)  # Default to GET if method is not found

        async with method_action(url, *args, **kwargs) as response:
            return await response.json()

async def fetch_with_retry(url, method, data, max_retries=5, delay=1):
    attempt = 0
    while attempt < max_retries:
        try:
            async with ClientSession() as session:
                async with session.request(method, url, json=data) as response:
                    response_text = await response.text()
                    if response.status == 200:
                        return await response.json()
                    else:
                        logging.error(f"Request to {url} failed with status {response.status}: {response_text}")
        except Exception as e:
            logging.error(f"Exception during request to {url}: {e}")
        
        attempt += 1
        if attempt < max_retries:
            await asyncio.sleep(delay)  # Exponential backoff
    return None

MAX_RETRIES = 100

async def continuous_fetch(server_index):
    gpt_server = gpt_servers[server_index]
    chat_setting = random.choice(chatSettings)
    retries = 0

    while not stop_fetching:
        try:
            url = f"{gen_server}/api/generate_conversation"
            data = {
                "server_url": gpt_server,
                "chat_setting": chat_setting
            }
            response = await fetch_with_retry(url, HTTPMethod.POST, data, max_retries=MAX_RETRIES)
            if response:
                logging.info(f"Successfully fetched data from {url}")
                retries = 0  # Reset retries on success
            else:
                logging.error(f"Failed to fetch data from {url} after {MAX_RETRIES} retries")
                retries += 1
                if retries >= MAX_RETRIES:
                    logging.error(f"Max retries reached for server {server_index + 1}. Stopping fetch loop.")
                    break
            
            # Update topic regardless of fetch success
            chat_setting["topic"] = generate_random_subject()
        
        except Exception as e:
            logging.error(f"Error in continuous fetch loop for server {server_index + 1}: {e}")
            retries += 1
            if retries >= MAX_RETRIES:
                logging.error(f"Max retries reached for server {server_index + 1} due to exceptions. Stopping fetch loop.")
                break
        
        # Optional: Add a small delay between iterations for this specific server
        await asyncio.sleep(0.1)
    
    print(f"Stopping fetch loop for server {server_index + 1}")

# Define the argument parser
parser = argparse.ArgumentParser(description="Script to continuously fetch data from servers.")

# Add arguments
parser.add_argument('-n', type=int, default=10, help="An integer number (default is 10)")

# Parse the arguments
args = parser.parse_args()

# Access the value of 'n'
n_value = args.n

# Define the gen_server and gpt_servers
gen_server = "http://localhost:8000"
gpt_servers = [f"http://localhost:{8080 + i}" for i in range(n_value)]

async def main():
    tasks = [continuous_fetch(i) for i in range(n_value)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user")