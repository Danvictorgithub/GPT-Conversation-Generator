#!/bin/bash

# Activate the virtual environment
source ./backend/.venv/bin/activate

# Function to stop and delete all pm2 processes
cleanup_pm2() {
    echo "Stopping and deleting all pm2 processes..."
    pm2 stop all
    pm2 delete all
}

# Add this new function
clear_screenshots() {
    echo "Clearing screenshots directory..."
    if [ -d "./screenshots" ]; then
        rm -rf ./screenshots/*
        echo "Screenshots directory cleared"
    fi
}

# Function to start all processes
start_processes() {
    # Clear previous processes
    cleanup_pm2

    # Load environment variables
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    echo "Starting Flask app on port 8000"
    pm2 start ./backend/app.py --name flask-server -- --port 8000

    retries=0
    max_retries=100

    while [ $retries -lt $max_retries ]; do
        # Check if Flask process is still running
        pm2 describe flask-server > /dev/null
        if [ $? -ne 0 ]; then
            echo "Flask server process not running, attempting to start..."
            pm2 start ./backend/app.py --name flask-server -- --port 8000
        fi

        # Check if the Flask server is responding
        if curl -s http://localhost:8000 > /dev/null; then
            echo "Flask server is up and running on port 8000"
            break
        else
            echo "Waiting for Flask server to start... (attempt $((retries + 1))/$max_retries)"
            sleep 2
            retries=$((retries + 1))
        fi
    done

    if [ $retries -eq $max_retries ]; then
        echo "Failed to start Flask server after $max_retries attempts."
        pm2 logs flask-server --nostream --lines 50
        exit 1
    fi

    # Run LLM servers with different indexes using pm2
    for ((index=8080; index<8080 + num_server; index++)); do
        echo "Running LLM server with index $index"
        SERVER_ID="server_$((index-8080))" \
        LLM_PROVIDER="${LLM_PROVIDER:-openai}" \
        LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:1234/v1}" \
        LLM_API_KEY="${LLM_API_KEY}" \
        MODEL_NAME="${MODEL_NAME:-gpt-3.5-turbo}" \
        pm2 start ./llm-server/index.js --name llm-server-$index -- -p $index
    done

    # Start scriptcron using pm2
    echo "Executing scriptcron.py"
    pm2 start ./backend/scriptcron.py --name scriptcron -- -n $num_server
    
    # Start pm2 logs in the background and save its PID
    pm2 logs & 
    pm2_logs_pid=$!
    
    echo "All tasks started successfully."
}

# Function to kill all processes
kill_processes() {
    echo "Killing all processes..."
    cleanup_pm2

    # Kill the pm2 logs process
    if [ -n "$pm2_logs_pid" ]; then
        echo "Killing pm2 logs process with PID $pm2_logs_pid"
        kill $pm2_logs_pid
        wait $pm2_logs_pid 2>/dev/null
    fi

    # Clear screenshots
    clear_screenshots

    echo "All processes killed."
}

# Function to kill processes on Ctrl+C
kill_django_processes() {
    echo "Killing all processes..."
    cleanup_pm2

    # Kill the pm2 logs process
    if [ -n "$pm2_logs_pid" ]; then
        echo "Killing pm2 logs process with PID $pm2_logs_pid"
        kill $pm2_logs_pid
        wait $pm2_logs_pid 2>/dev/null
    fi

    # Clear screenshots
    clear_screenshots

    echo "All processes killed."
}

# Trap SIGINT (Ctrl+C) to kill all processes
trap 'kill_processes; exit 0' SIGINT

# Define the number of servers
num_server=12
data_collection_time=$((60 * 30))  # 30 minutes
collection_restart_time=$((60 * 1))  # 1 minute

# Main loop
while true; do
    start_processes
    echo "Running processes for $data_collection_time seconds..."
    sleep $data_collection_time
    kill_processes
    echo "Waiting for $collection_restart_time seconds before restarting..."
    sleep $collection_restart_time
done
