# test_gemini_models.py
import os
from dotenv import load_dotenv
import requests

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

response = requests.get(url)
print("Available Gemini Models:")
print("=" * 60)

if response.status_code == 200:
    models = response.json()
    for model in models.get('models', []):
        if 'gemini' in model.get('name', '').lower():
            print(f"  - {model.get('name')}")
            print(f"    Supported: {model.get('supportedGenerationMethods', [])}")
            print()
else:
    print(f"Error: {response.status_code}")
    print(response.text)