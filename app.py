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
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
import uuid
import io
import glob
import time
import threading
from datetime import datetime, timedelta


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

# Cleanup configuration
CLEANUP_INTERVAL = 3600  # Run cleanup every hour (3600 seconds)
MAX_FILE_AGE = 7200      # Delete files older than 2 hours (7200 seconds)
MAX_FILES_COUNT = 500    # Maximum number of files to keep

def cleanup_generated_files():
    """
    Clean up old generated image files to prevent storage overflow
    """
    try:
        generated_dir = os.path.join('static', 'generated')
        if not os.path.exists(generated_dir):
            return
        
        current_time = time.time()
        files_pattern = os.path.join(generated_dir, 'plot_*.png')
        files = glob.glob(files_pattern)
        
        # Sort files by modification time (oldest first)
        files.sort(key=lambda x: os.path.getmtime(x))
        
        deleted_count = 0
        
        # Delete files older than MAX_FILE_AGE
        for file_path in files:
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > MAX_FILE_AGE:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted old generated file: {os.path.basename(file_path)} (age: {file_age/3600:.1f} hours)")
                except OSError as e:
                    logger.error(f"Failed to delete file {file_path}: {e}")
        
        # If we still have too many files, delete the oldest ones
        remaining_files = [f for f in files if os.path.exists(f)]
        if len(remaining_files) > MAX_FILES_COUNT:
            files_to_delete = remaining_files[:-MAX_FILES_COUNT]  # Keep only the newest MAX_FILES_COUNT files
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted excess file: {os.path.basename(file_path)} (count management)")
                except OSError as e:
                    logger.error(f"Failed to delete excess file {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleanup completed: {deleted_count} files deleted")
        
        # Log current file count
        current_files = len(glob.glob(files_pattern))
        logger.info(f"Generated files count after cleanup: {current_files}")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def cleanup_worker():
    """
    Background worker that runs cleanup periodically
    """
    while True:
        try:
            cleanup_generated_files()
            time.sleep(CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"Error in cleanup worker: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

# Start cleanup worker thread
cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
cleanup_thread.start()
logger.info(f"Started cleanup worker thread (interval: {CLEANUP_INTERVAL/3600:.1f}h, max age: {MAX_FILE_AGE/3600:.1f}h)")

# Matplotlib diagram generation function
def generate_matplotlib_diagram(python_code, output_filename):
    """
    Execute matplotlib/numpy code to generate a diagram
    Returns the path to the generated image or None if failed
    """
    try:
        # Create a new figure
        plt.figure(figsize=(8, 6), dpi=100)
        plt.style.use('default')
        
        # Define a safe execution environment
        safe_globals = {
            'plt': plt,
            'np': np,
            'numpy': np,
            'matplotlib': matplotlib,
            'nx': nx,
            'networkx': nx,
            'sin': np.sin,
            'cos': np.cos,
            'tan': np.tan,
            'log': np.log,
            'exp': np.exp,
            'sqrt': np.sqrt,
            'pi': np.pi,
            'e': np.e,
            'linspace': np.linspace,
            'arange': np.arange,
            'array': np.array,
            'range': range,
            'len': len,
            'abs': abs,
            'max': max,
            'min': min,
            'python': None,  # Prevent undefined 'python' references
        }
        
        # Execute the plotting code
        exec(python_code, safe_globals)
        
        # Save the plot
        output_path = os.path.join('static', 'generated', output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        return output_filename
        
    except Exception as e:
        logger.error(f"Error generating matplotlib diagram: {str(e)}")
        plt.close()  # Ensure plot is closed even on error
        return None

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
            "If the problem would benefit from a visual diagram (graphs, plots, functions, geometry, etc.), "
            "include Python matplotlib code wrapped in <!--PLOT-START--> and <!--PLOT-END--> tags. "
            "The code should use matplotlib (plt) and numpy (np) to create clear, labeled diagrams. "
            "Examples: function plots, geometric shapes, coordinate systems, statistical charts, etc. "
            "Make sure to include proper labels, titles, and formatting for clarity. "
            "IMPORTANT: Do not include any markdown code block markers (like ```python or ```) in your response. "
            "IMPORTANT: Only use plt, np, numpy, matplotlib and standard math functions in the code. "
            "Do not reference 'python' as a variable or function name. "
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
        
        # Extract and process matplotlib code if present
        plot_image_url = None
        plot_pattern = r'<!--PLOT-START-->(.*?)<!--PLOT-END-->'
        plot_match = re.search(plot_pattern, cleaned_response, re.DOTALL)
        
        if plot_match:
            plot_code = plot_match.group(1).strip()
            # Clean the code - remove "python" if it appears at the start
            if plot_code.startswith('python'):
                plot_code = '\n'.join(plot_code.split('\n')[1:])
            # Generate unique filename for the image
            image_filename = f"plot_{uuid.uuid4().hex[:8]}.png"
            
            # Generate matplotlib diagram
            compiled_image = generate_matplotlib_diagram(plot_code, image_filename)
            
            if compiled_image:
                plot_image_url = f"/static/generated/{compiled_image}"
                # Remove plot code from response and add image reference
                cleaned_response = re.sub(plot_pattern, 
                    f'<div class="math-diagram-container"><img src="{plot_image_url}" alt="Mathematical Diagram" class="math-diagram"></div>', 
                    cleaned_response, flags=re.DOTALL)
                logger.info(f"Successfully generated matplotlib diagram: {plot_image_url}")
                
                # Schedule file deletion after 10 minutes (enough time for user to view)
                def delayed_delete():
                    time.sleep(600)  # 10 minutes
                    try:
                        file_path = os.path.join('static', 'generated', compiled_image)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted served image: {compiled_image}")
                    except OSError as e:
                        logger.error(f"Failed to delete served image {compiled_image}: {e}")
                
                # Start deletion in background
                delete_thread = threading.Thread(target=delayed_delete, daemon=True)
                delete_thread.start()
            else:
                # Remove plot code if generation failed
                cleaned_response = re.sub(plot_pattern, 
                    '<p><em>Diagram generation failed. Please refer to the text solution.</em></p>', 
                    cleaned_response, flags=re.DOTALL)
                logger.warning("Matplotlib diagram generation failed, removed from response")
        
        # Ensure the response is properly escaped for JSON
        result = {
            'success': True,
            'solution': cleaned_response,
            'has_diagram': plot_image_url is not None,
            'diagram_url': plot_image_url
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