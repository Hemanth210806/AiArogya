
import google.generativeai as genai
import config

genai.configure(api_key=config.GEMINI_API_KEY)

try:
    print("Available models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")
