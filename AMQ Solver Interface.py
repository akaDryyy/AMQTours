import subprocess
import time
import requests
import webbrowser

# 1. Start uvicorn
uvicorn_process = subprocess.Popen(
    ["uvicorn", "api:app", "--reload"],
)

# 2. Wait for the API to be ready
print("Waiting for uvicorn to start...")

while True:
    try:
        requests.get("http://127.0.0.1:8000")
        break
    except requests.exceptions.ConnectionError:
        time.sleep(1)

print("Uvicorn is running!")

# 3. Start Flask
flask_process = subprocess.Popen(
    ["flask", "--app", "main", "run"]
)

# 4. Open browser
time.sleep(2)
webbrowser.open("http://127.0.0.1:5000/usual")

# Keep script alive
uvicorn_process.wait()
flask_process.wait()