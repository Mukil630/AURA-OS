import os
import time
from google import genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv(r"C:\Users\mukil\jarvis-core\.env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

t0 = time.time()
img = Image.open(r"C:\Users\mukil\jarvis-core\storage\screenshots\tenses_next_clicked.png")
crop = img.crop((700, 200, 1450, 1150))
print(f"Crop ready in {time.time() - t0:.2f}s")

prompt = 'Read the passage and answer the 3 questions. Return strictly valid JSON: {"q1_answer": "B", "q2_answer": "B", "q3_answer": "B"}'
t1 = time.time()
resp = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=[crop, prompt]
)
print(f"Gemini responded in {time.time() - t1:.2f}s:")
print(resp.text)
