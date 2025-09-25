import os
import google.generativeai as genai
from openai import OpenAI
from aicalc.config import logger
from io import BytesIO
import base64

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
VISION_MODEL = os.getenv('OPENROUTER_VISION_MODEL', 'qwen/qwen-2.5-72b-instruct')

api_backend = "gemini"
model = None
openrouter_client = None
if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

def initialize_ai_model():
    global model, api_backend
    try:
        if PROJECT_ID and os.path.exists(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')):
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel
                vertexai.init(project=PROJECT_ID, location=LOCATION)
                model = GenerativeModel('gemini-1.5-flash')
                test_response = model.generate_content("Test")
                api_backend = "vertex"
                logger.info("✅ Using Vertex AI")
                return
            except Exception as e:
                logger.info(f"Vertex AI not available: {e}")
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(model_name='gemini-1.5-flash')
            api_backend = "gemini"
            logger.info("✅ Using Gemini API")
        else:
            raise Exception("No AI API configured")
    except Exception as e:
        logger.error(f"Failed to initialize AI model: {e}")
        raise

def generate_ai_response(prompt, image=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            if api_backend == "vertex" and image:
                from vertexai.generative_models import Part
                img_byte_arr = BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                image_part = Part.from_data(img_byte_arr, mime_type="image/png")
                response = model.generate_content([prompt, image_part])
            elif image:
                response = model.generate_content([prompt, image])
            else:
                response = model.generate_content([prompt])
            return response.text
        except Exception as e:
            if openrouter_client:
                logger.warning(f"Google Generative AI failed: {e}. Falling back to OpenRouter.")
                try:
                    if image:
                        buffered = BytesIO()
                        image.save(buffered, format="PNG")
                        img_b64 = base64.b64encode(buffered.getvalue()).decode()
                        image_url = f"data:image/png;base64,{img_b64}"
                        completion = openrouter_client.chat.completions.create(
                            model=VISION_MODEL,
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": prompt},
                                        {"type": "image_url", "image_url": {"url": image_url}}
                                    ]
                                }
                            ],
                            max_tokens=1024
                        )
                        return completion.choices[0].message.content
                    else:
                        completion = openrouter_client.chat.completions.create(
                            model=VISION_MODEL,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=1024
                        )
                        return completion.choices[0].message.content
                except Exception as oe:
                    logger.error(f"OpenRouter fallback also failed: {oe}")
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 1
                        logger.info(f"Retrying in {wait_time} seconds...")
                        import time
                        time.sleep(wait_time)
                    else:
                        raise oe
            else:
                logger.warning(f"AI request attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    logger.info(f"Retrying in {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                else:
                    raise e
