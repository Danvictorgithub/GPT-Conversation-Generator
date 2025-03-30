#!/bin/bash

# Activate the virtual environment
source ./gpt-scraperdj-astro/backend/.venv/bin/activate

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

    echo "Starting Django app on port 8000"
    pm2 start ./gpt-scraperdj-astro/backend/manage.py --name django-server -- runserver 8000

    retries=0
    max_retries=100

    while [ $retries -lt $max_retries ]; do
        # Check if Django process is still running
        pm2 describe django-server > /dev/null
        if [ $? -ne 0 ]; then
            echo "Django server process not running, attempting to start..."
            pm2 start ./gpt-scraperdj-astro/backend/manage.py --name django-server -- runserver 8000
        fi

        # Check Django logs without blocking
        error_log=$(pm2 logs django-server --nostream --lines 10 | grep "Error")
        startup_log=$(pm2 logs django-server --nostream --lines 10 | grep "Starting development server at http://127.0.0.1:8000/")

        if [[ ! -z "$startup_log" ]]; then
            echo "Django server is up and running on port 8000"
            break
        elif [[ ! -z "$error_log" ]]; then
            echo "Django server encountered an error, retrying..."
            pm2 delete django-server
            pm2 start ./gpt-scraperdj-astro/backend/manage.py --name django-server -- runserver 8000
        fi

        echo "Waiting for Django server to start... (attempt $((retries + 1))/$max_retries)"
        sleep 2
        retries=$((retries + 1))
    done

    if [ $retries -eq $max_retries ]; then
        echo "Failed to start Django server after $max_retries attempts."
        pm2 logs django-server --nostream --lines 50
        exit 1
    fi


    # Run GPT-teer with different indexes using pm2
    for ((index=8080; index<8080 + num_server; index++)); do
        echo "Running GPT-Teer with index $index"
        pm2 start ./gpt-teer/index.js --name gpt-teer-$index -- -p $index --no-headless
    done

    # Start scriptcron using pm2
    echo "Executing scriptcron.py"
    pm2 start ./gpt-wright-script/scriptcron.py --name scriptcron -- -n $num_server
    
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
trap 'kill_django_processes; exit 0' SIGINT

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
