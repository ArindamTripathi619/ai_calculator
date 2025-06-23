from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai
import os
import base64
import re
import json
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import logging


# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name='gemini-1.5-flash')

app = Flask(__name__)

# Set up CORS
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if os.getenv('CORS_ALLOWED_ORIGINS') else []

if CORS_ALLOWED_ORIGINS:
    CORS(app, origins=CORS_ALLOWED_ORIGINS)
else:
    CORS(app)  # Fallback: allow all (not recommended for production)

# Serve static files using send_from_directory
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# Initialize Flask-Limiter with Redis for production
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=REDIS_URL,
    default_limits=["200 per day", "50 per hour"]
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

@app.errorhandler(404)
def not_found_error(error):
    return send_from_directory('static', '404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return send_from_directory('static', '500.html'), 500

@app.route('/calculate', methods=['POST'])
@limiter.limit("10 per minute")  # Limit to 10 requests per minute
def calculate():
    try:
        # Get image data from request
        data = request.json
        image_data = data.get('image')
        
        # Convert base64 image to PIL Image
        image_data = image_data.replace('data:image/png;base64,', '')
        image_bytes = base64.b64decode(image_data)
        img = Image.open(BytesIO(image_bytes))
        
        # Save temporarily (optional)
        # temp_image_path = "temp_image.png"
        # img.save(temp_image_path)
        
        # Prompt for Gemini API
        prompt = (
            "You will be provided an image file containing a mathematical expression. "
            "The image has a black background with the math expression drawn in white or other colors. "
            "Identify the mathematical expression and provide a complete solution. "
            "Format your response as HTML with MathJax-compatible LaTeX for all mathematical expressions. "
            "Use \\( \\) for inline math and \\[ \\] for display math. "
            "Include step-by-step explanations where appropriate. "
            "IMPORTANT: Do not include any markdown code block markers (like ```html or ```) in your response. "
            "Keep your response concise and focused on the solution."
        )
        
        # Generate response
        response = model.generate_content([prompt, img])
        
        # Clean up
        # if os.path.exists(temp_image_path):
        #     os.remove(temp_image_path)
        
        # Clean the response to remove any markdown code block markers
        cleaned_response = response.text
        # Remove ```html at the beginning and ``` at the end if present
        cleaned_response = re.sub(r'^```(?:html|markdown)?\s*', '', cleaned_response)
        cleaned_response = re.sub(r'\s*```$', '', cleaned_response)
        # Remove any other markdown code blocks that might be present
        cleaned_response = re.sub(r'```\w*\s*|\s*```', '', cleaned_response)
        
        # Ensure the response is properly escaped for JSON
        result = {
            'success': True,
            'solution': cleaned_response
        }
        
        # Validate JSON before returning
        # This ensures we're sending valid JSON
        json.dumps(result)
        
        return jsonify(result)
    except Exception as e:
        logger.error('Error in /calculate: %s', str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again later.'
        }), 500

if __name__ == '__main__':
    # Make sure static folder exists
    if not os.path.exists('static'):
        os.makedirs('static')
    port = int(os.environ.get("PORT", 5000))
    # Set debug=False for production
    app.run(debug=False, host='0.0.0.0', port=port)
    # For production, use a WSGI server like Gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:5000 app:app