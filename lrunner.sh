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

# Add this function before start_processes
wait_for_port() {
    local port=$1
    local max_attempts=$2
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost $port; then
            return 0
        fi
        echo "Waiting for port $port... attempt $attempt/$max_attempts"
        sleep 2
        attempt=$((attempt + 1))
    done
    return 1
}

# Function to start all processes
start_processes() {
    # Clear previous processes and PM2 save file
    cleanup_pm2
    rm -f ~/.pm2/dump.pm2

    # Ensure .env exists
    if [ ! -f .env ]; then
        echo "Error: .env file not found in the root directory"
        exit 1
    fi

    # Load environment variables for all processes
    set -a
    source .env
    set +a

    echo "Starting Flask app on port 8000"
    # Start Flask using environment variables
    pm2 start --name flask-server \
              --interpreter python3 \
              ./backend/app.py \
              -- --port 8000

    # Wait for Flask to be ready
    if ! wait_for_port 8000 30; then
        echo "Failed to start Flask server"
        pm2 logs flask-server --lines 50
        cleanup_pm2
        exit 1
    fi

    echo "Flask server is running"

    # Start LLM servers with delay between each
    for ((index=8080; index<8080 + num_server; index++)); do
        echo "Running LLM server with index $index"
        SERVER_ID="server_$((index-8080))" \
        pm2 start ./llm-server/index.js \
            --name "llm-server-$index" \
            -- -p $index

        # Wait a bit between server starts to prevent resource contention
        sleep 1
        
        # Check if server started successfully
        if ! wait_for_port $index 10; then
            echo "Failed to start LLM server on port $index"
            cleanup_pm2
            exit 1
        fi
    done

    # Start scriptcron after all servers are ready
    echo "Executing scriptcron.py"
    pm2 start ./backend/scriptcron.py --name scriptcron -- -n $num_server

    # Save PM2 process list
    echo "Saving PM2 process list..."
    pm2 save

    # Start pm2 logs in the background
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
num_server=1
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
