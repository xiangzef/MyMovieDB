import requests
import json

url = "http://localhost:8000/scrape/fix"

try:
    response = requests.post(url, json={}, stream=True)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print("\nSSE Stream:")
    print("-" * 50)
    
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            print(decoded)
            
except Exception as e:
    print(f"Error: {e}")
