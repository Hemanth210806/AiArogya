
import os
import google.generativeai as genai
from PIL import Image
import config

# Configure
genai.configure(api_key=config.GEMINI_API_KEY)
# Use the model name found in the list
model = genai.GenerativeModel("gemini-flash-latest")

def test():
    print(f"Testing with API Key: {config.GEMINI_API_KEY[:10]}...")
    
    img_path = os.path.join("static", "uploads", "Screenshot_2026-05-08_211748.png")
    if not os.path.exists(img_path):
        print(f"Error: {img_path} not found")
        return

    img = Image.open(img_path)
    prompt = "What is in this image? Return a short JSON object."
    
    try:
        print("Sending request to Gemini...")
        response = model.generate_content([prompt, img])
        print("Response received:")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
