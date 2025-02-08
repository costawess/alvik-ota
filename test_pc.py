import requests
import time

timestamp = int(time.time())  # Unique timestamp
url = f"https://raw.githubusercontent.com/costawess/alvik-ota/main/test.py?nocache={timestamp}"

response = requests.get(url)
print(response.text)  # Should print the latest content
response.close()