#!/usr/bin/env python3
"""
Optimized AI Calculator with Enhanced Gemini API
- Better error handling and retry logic
- Response caching to reduce API calls
- Performance optimizations
- Ready for Vertex AI when available
"""
from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai
import os
import base64
import re
import json
import hashlib
import time
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
import threading
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# AI Configuration with fallback
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT_ID')  # For future Vertex AI
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')

# Configure AI API
api_backend = "gemini"  # Will change to "vertex" when available
model = None

def initialize_ai_model():
    """Initialize AI model with fallback"""
    global model, api_backend
    
    try:
        # Try Vertex AI first (for future use)
        if PROJECT_ID and os.path.exists(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')):
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel
                
                vertexai.init(project=PROJECT_ID, location=LOCATION)
                model = GenerativeModel('gemini-1.5-flash')
                
                # Test if it works
                test_response = model.generate_content("Test")
                api_backend = "vertex"
                logger.info("✅ Using Vertex AI")
                return
                
            except Exception as e:
                logger.info(f"Vertex AI not available: {e}")
        
        # Fallback to regular Gemini API
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

# Simple in-memory cache for responses
response_cache = {}
CACHE_TTL = 3600  # 1 hour

def get_cache_key(image_data=None, text_data=None):
    """Generate cache key from input data"""
    if image_data:
        return hashlib.md5(image_data.encode()).hexdigest()
    elif text_data:
        return hashlib.md5(text_data.encode()).hexdigest()
    return None

def get_cached_response(cache_key):
    """Get cached response if still valid"""
    if cache_key in response_cache:
        cached_data, timestamp = response_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"Cache hit for key: {cache_key[:8]}...")
            return cached_data
        else:
            # Remove expired cache
            del response_cache[cache_key]
    return None

def cache_response(cache_key, response_data):
    """Cache response data"""
    response_cache[cache_key] = (response_data, time.time())
    logger.info(f"Cached response for key: {cache_key[:8]}...")
    
    # Simple cache cleanup - remove old entries
    current_time = time.time()
    expired_keys = [k for k, (_, ts) in response_cache.items() if current_time - ts > CACHE_TTL]
    for k in expired_keys:
        del response_cache[k]

def generate_ai_response(prompt, image=None, max_retries=3):
    """Generate AI response with retry logic"""
    for attempt in range(max_retries):
        try:
            if api_backend == "vertex" and image:
                # Vertex AI approach (for future use)
                from vertexai.generative_models import Part
                img_byte_arr = BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                image_part = Part.from_data(img_byte_arr, mime_type="image/png")
                response = model.generate_content([prompt, image_part])
            elif image:
                # Regular Gemini API with image
                response = model.generate_content([prompt, image])
            else:
                # Text only
                response = model.generate_content([prompt])
            
            return response.text
            
        except Exception as e:
            logger.warning(f"AI request attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                # Wait before retry (exponential backoff)
                wait_time = (2 ** attempt) * 1
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e

app = Flask(__name__)

# Enhanced CORS setup
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if os.getenv('CORS_ALLOWED_ORIGINS') else []

if CORS_ALLOWED_ORIGINS:
    CORS(app, origins=CORS_ALLOWED_ORIGINS)
else:
    CORS(app)

# Serve static files
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# Enhanced rate limiting based on API backend
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Dynamic rate limits
rate_limits = {
    "vertex": ["500 per day", "100 per hour", "30 per minute"],
    "gemini": ["200 per day", "50 per hour", "15 per minute"]  # Slightly increased
}

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=REDIS_URL,
    default_limits=rate_limits.get(api_backend, rate_limits["gemini"])
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Initialize AI model
try:
    initialize_ai_model()
    logger.info(f"AI Backend: {api_backend}")
except Exception as e:
    logger.error(f"Failed to initialize AI: {e}")
    exit(1)

# ...existing cleanup code... (keeping the same)
CLEANUP_INTERVAL = 3600
MAX_FILE_AGE = 7200
MAX_FILES_COUNT = 500

def cleanup_generated_files():
    """Clean up old generated image files to prevent storage overflow"""
    try:
        generated_dir = os.path.join('static', 'generated')
        if not os.path.exists(generated_dir):
            return
        
        current_time = time.time()
        files_pattern = os.path.join(generated_dir, 'plot_*.png')
        files = glob.glob(files_pattern)
        
        files.sort(key=lambda x: os.path.getmtime(x))
        deleted_count = 0
        
        for file_path in files:
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > MAX_FILE_AGE:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted old generated file: {os.path.basename(file_path)} (age: {file_age/3600:.1f} hours)")
                except OSError as e:
                    logger.error(f"Failed to delete file {file_path}: {e}")
        
        remaining_files = [f for f in files if os.path.exists(f)]
        if len(remaining_files) > MAX_FILES_COUNT:
            files_to_delete = remaining_files[:-MAX_FILES_COUNT]
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted excess file: {os.path.basename(file_path)} (count management)")
                except OSError as e:
                    logger.error(f"Failed to delete excess file {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleanup completed: {deleted_count} files deleted")
        
        current_files = len(glob.glob(files_pattern))
        logger.info(f"Generated files count after cleanup: {current_files}")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def cleanup_worker():
    """Background worker that runs cleanup periodically"""
    while True:
        try:
            cleanup_generated_files()
            time.sleep(CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"Error in cleanup worker: {e}")
            time.sleep(60)

cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
cleanup_thread.start()
logger.info(f"Started cleanup worker thread (interval: {CLEANUP_INTERVAL/3600:.1f}h, max age: {MAX_FILE_AGE/3600:.1f}h)")

# ...existing matplotlib code... (keeping the same)
def generate_matplotlib_diagram(python_code, output_filename):
    """Execute matplotlib/numpy code to generate a diagram"""
    try:
        plt.figure(figsize=(8, 6), dpi=100)
        plt.style.use('default')
        
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
            'python': None,
        }
        
        exec(python_code, safe_globals)
        
        output_path = os.path.join('static', 'generated', output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        return output_filename
        
    except Exception as e:
        logger.error(f"Error generating matplotlib diagram: {str(e)}")
        plt.close()
        return None

def generate_tikz_diagram(tikz_code, output_filename):
    """Generate a diagram from TikZ code"""
    try:
        # Create a temporary directory for compilation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create the LaTeX document with TikZ code
            latex_content = f"""
\\documentclass[border=10pt,varwidth]{{standalone}}
\\usepackage{{tikz}}
\\usepackage{{pgfplots}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usetikzlibrary{{arrows,automata,positioning,shapes,patterns,decorations.pathreplacing,calc,angles,quotes}}
\\pgfplotsset{{compat=1.18}}

\\begin{{document}}
\\begin{{tikzpicture}}[auto,node distance=2cm,>=stealth']
{tikz_code}
\\end{{tikzpicture}}
\\end{{document}}
"""
            
            # Write LaTeX file
            tex_file = os.path.join(temp_dir, 'diagram.tex')
            with open(tex_file, 'w') as f:
                f.write(latex_content)
            
            # Compile with pdflatex
            try:
                result = subprocess.run([
                    'pdflatex', 
                    '-interaction=nonstopmode',
                    '-output-directory', temp_dir,
                    tex_file
                ], capture_output=True, text=True, timeout=30)
                
                pdf_file = os.path.join(temp_dir, 'diagram.pdf')
                
                if result.returncode != 0:
                    logger.error(f"pdflatex failed with return code {result.returncode}")
                    if result.stdout:
                        logger.error(f"pdflatex stdout: {result.stdout[-500:]}")  # Last 500 chars
                    if result.stderr:
                        logger.error(f"pdflatex stderr: {result.stderr}")
                    return None
                
                if not os.path.exists(pdf_file):
                    logger.error("PDF file was not generated despite successful compilation")
                    return None
                
                # Convert PDF to PNG using ImageMagick or pdftoppm
                output_path = os.path.join('static', 'generated', 'tikz', output_filename)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Try pdftoppm first (part of poppler-utils)
                try:
                    result = subprocess.run([
                        'pdftoppm',
                        '-png',
                        '-singlefile',
                        '-r', '300',  # 300 DPI for high quality
                        pdf_file,
                        output_path.replace('.png', '')
                    ], capture_output=True, text=True, timeout=15)
                    
                    if result.returncode != 0:
                        logger.error(f"pdftoppm failed with return code {result.returncode}")
                        if result.stderr:
                            logger.error(f"pdftoppm stderr: {result.stderr}")
                        raise subprocess.CalledProcessError(result.returncode, 'pdftoppm')
                    
                    return f"tikz/{output_filename}"
                    
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.warning(f"pdftoppm failed: {e}, trying ImageMagick convert...")
                    # Fallback to ImageMagick convert if available
                    try:
                        result = subprocess.run([
                            'convert',
                            '-density', '300',
                            '-quality', '100',
                            pdf_file,
                            output_path
                        ], capture_output=True, text=True, timeout=15)
                        
                        if result.returncode != 0:
                            logger.error(f"ImageMagick convert failed with return code {result.returncode}")
                            if result.stderr:
                                logger.error(f"convert stderr: {result.stderr}")
                            return None
                        
                        return f"tikz/{output_filename}"
                        
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        logger.error(f"ImageMagick convert also failed: {e}")
                        logger.error("Neither pdftoppm nor ImageMagick convert available for PDF conversion")
                        return None
                
            except subprocess.TimeoutExpired:
                logger.error("TikZ compilation timed out")
                return None
            except subprocess.CalledProcessError as e:
                logger.error(f"TikZ compilation failed with return code {e.returncode}")
                if e.stdout:
                    logger.error(f"TikZ stdout: {e.stdout}")
                if e.stderr:
                    logger.error(f"TikZ stderr: {e.stderr}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error during TikZ compilation: {str(e)}")
                return None
                
    except Exception as e:
        logger.error(f"Error generating TikZ diagram: {str(e)}")
        return None

@app.errorhandler(404)
def not_found_error(error):
    return send_from_directory('static', '404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return send_from_directory('static', '500.html'), 500

# Enhanced calculate route with caching
@app.route('/calculate', methods=['POST'])
@limiter.limit("15 per minute")  # Slightly increased limit
def calculate():
    try:
        data = request.json
        image_data = data.get('image')
        
        # Check cache first
        cache_key = get_cache_key(image_data=image_data)
        cached_result = get_cached_response(cache_key)
        
        if cached_result:
            logger.info("Returning cached result for image")
            return jsonify(cached_result)
        
        # Convert base64 image to PIL Image
        image_data = image_data.replace('data:image/png;base64,', '')
        image_bytes = base64.b64decode(image_data)
        img = Image.open(BytesIO(image_bytes))
        
        # Enhanced prompt
        prompt = (
            "You will be provided an image file containing a mathematical expression. "
            "The image has a black background with the math expression drawn in white or other colors. "
            "Identify the mathematical expression and provide a complete solution. "
            "Format your response as HTML with MathJax-compatible LaTeX for all mathematical expressions. "
            "Use \\( \\) for inline math and \\[ \\] for display math. "
            "Include step-by-step explanations where appropriate. "
            "If the problem would benefit from a visual diagram, choose the appropriate method: "
            "For simple plots, graphs, and statistical charts, use Python matplotlib code wrapped in <!--PLOT-START--> and <!--PLOT-END--> tags. "
            "For complex diagrams like DFAs, NFAs, flowcharts, automata, trees, complex geometric constructions, or formal structures, "
            "use TikZ code wrapped in <!--TIKZ-START--> and <!--TIKZ-END--> tags. "
            "For matplotlib: Use plt, np, numpy, matplotlib and standard math functions with proper labels and titles. "
            "For TikZ: Use standard TikZ syntax with automata, positioning, shapes libraries available. "
            "IMPORTANT: Do not include any markdown code block markers (like ```python or ```) in your response. "
            "IMPORTANT: Choose TikZ for formal computer science diagrams, automata, complex geometric proofs, trees. "
            "Choose matplotlib for function plots, statistical charts, simple geometric shapes. "
            "Do not reference 'python' as a variable or function name. "
            "Keep your response concise and focused on the solution."
        )
        
        # Generate response with retry logic
        response_text = generate_ai_response(prompt, img)
        
        # Process response (same as before)
        cleaned_response = response_text
        cleaned_response = re.sub(r'^```(?:html|markdown)?\s*', '', cleaned_response)
        cleaned_response = re.sub(r'\s*```$', '', cleaned_response)
        cleaned_response = re.sub(r'```\w*\s*|\s*```', '', cleaned_response)
        
        # Extract and process diagram code (matplotlib or TikZ)
        plot_image_url = None
        
        # Check for matplotlib code first
        plot_pattern = r'<!--PLOT-START-->(.*?)<!--PLOT-END-->'
        plot_match = re.search(plot_pattern, cleaned_response, re.DOTALL)
        
        # Check for TikZ code
        tikz_pattern = r'<!--TIKZ-START-->(.*?)<!--TIKZ-END-->'
        tikz_match = re.search(tikz_pattern, cleaned_response, re.DOTALL)
        
        if plot_match:
            plot_code = plot_match.group(1).strip()
            if plot_code.startswith('python'):
                plot_code = '\n'.join(plot_code.split('\n')[1:])
            
            image_filename = f"plot_{uuid.uuid4().hex[:8]}.png"
            compiled_image = generate_matplotlib_diagram(plot_code, image_filename)
            
            if compiled_image:
                plot_image_url = f"/static/generated/{compiled_image}"
                cleaned_response = re.sub(plot_pattern, 
                    f'<div class="math-diagram-container"><img src="{plot_image_url}" alt="Mathematical Diagram" class="math-diagram"></div>', 
                    cleaned_response, flags=re.DOTALL)
                logger.info(f"Successfully generated matplotlib diagram: {plot_image_url}")
                
                def delayed_delete():
                    time.sleep(600)
                    try:
                        file_path = os.path.join('static', 'generated', compiled_image)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted served image: {compiled_image}")
                    except OSError as e:
                        logger.error(f"Failed to delete served image {compiled_image}: {e}")
                
                delete_thread = threading.Thread(target=delayed_delete, daemon=True)
                delete_thread.start()
            else:
                cleaned_response = re.sub(plot_pattern, 
                    '<p><em>Diagram generation failed. Please refer to the text solution.</em></p>', 
                    cleaned_response, flags=re.DOTALL)
                logger.warning("Matplotlib diagram generation failed, removed from response")
        
        elif tikz_match:
            tikz_code = tikz_match.group(1).strip()
            
            image_filename = f"tikz_{uuid.uuid4().hex[:8]}.png"
            compiled_image = generate_tikz_diagram(tikz_code, image_filename)
            
            if compiled_image:
                plot_image_url = f"/static/generated/{compiled_image}"
                cleaned_response = re.sub(tikz_pattern, 
                    f'<div class="math-diagram-container"><img src="{plot_image_url}" alt="Mathematical Diagram" class="math-diagram"></div>', 
                    cleaned_response, flags=re.DOTALL)
                logger.info(f"Successfully generated TikZ diagram: {plot_image_url}")
                
                def delayed_delete():
                    time.sleep(600)
                    try:
                        file_path = os.path.join('static', 'generated', compiled_image)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted served image: {compiled_image}")
                    except OSError as e:
                        logger.error(f"Failed to delete served image {compiled_image}: {e}")
                
                delete_thread = threading.Thread(target=delayed_delete, daemon=True)
                delete_thread.start()
            else:
                cleaned_response = re.sub(tikz_pattern, 
                    '<p><em>Diagram generation failed. Please refer to the text solution.</em></p>', 
                    cleaned_response, flags=re.DOTALL)
                logger.warning("TikZ diagram generation failed, removed from response")
        
        result = {
            'success': True,
            'solution': cleaned_response,
            'has_diagram': plot_image_url is not None,
            'diagram_url': plot_image_url,
            'api_backend': api_backend,  # For debugging
            'cached': False
        }
        
        # Cache the result
        cache_response(cache_key, result)
        
        json.dumps(result)
        return jsonify(result)
        
    except Exception as e:
        logger.error('Error in /calculate: %s', str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again later.'
        }), 500

# Enhanced calculate-text route with caching
@app.route('/calculate-text', methods=['POST'])
@limiter.limit("15 per minute")
def calculate_text():
    try:
        data = request.json
        question_text = data.get('question')
        
        if not question_text or not question_text.strip():
            return jsonify({
                'success': False,
                'error': 'No question provided.'
            }), 400
        
        # Check cache first
        cache_key = get_cache_key(text_data=question_text)
        cached_result = get_cached_response(cache_key)
        
        if cached_result:
            logger.info("Returning cached result for text")
            return jsonify(cached_result)
        
        # Enhanced prompt for text questions
        prompt = (
            "You will be provided with a mathematical question in text format. "
            "Provide a complete solution with step-by-step explanations. "
            "Format your response as HTML with MathJax-compatible LaTeX for all mathematical expressions. "
            "Use \\( \\) for inline math and \\[ \\] for display math. "
            "If the problem would benefit from a visual diagram, choose the appropriate method: "
            "For simple plots, graphs, and statistical charts, use Python matplotlib code wrapped in <!--PLOT-START--> and <!--PLOT-END--> tags. "
            "For complex diagrams like DFAs, NFAs, flowcharts, automata, trees, complex geometric constructions, or formal structures, "
            "use TikZ code wrapped in <!--TIKZ-START--> and <!--TIKZ-END--> tags. "
            "For matplotlib: Use plt, np, numpy, matplotlib and standard math functions with proper labels and titles. "
            "For TikZ: Use standard TikZ syntax with automata, positioning, shapes libraries available. "
            "IMPORTANT: Do not include any markdown code block markers (like ```python or ```) in your response. "
            "IMPORTANT: Choose TikZ for formal computer science diagrams, automata, complex geometric proofs, trees. "
            "Choose matplotlib for function plots, statistical charts, simple geometric shapes. "
            "Keep your response clear, concise and mathematically accurate. "
            f"Question: {question_text}"
        )
        
        # Generate response with retry logic
        response_text = generate_ai_response(prompt)
        
        # Process response (same logic as calculate route)
        cleaned_response = response_text
        cleaned_response = re.sub(r'^```(?:html|markdown)?\s*', '', cleaned_response)
        cleaned_response = re.sub(r'\s*```$', '', cleaned_response)
        cleaned_response = re.sub(r'```\w*\s*|\s*```', '', cleaned_response)
        
        # Extract and process diagram code (matplotlib or TikZ)
        plot_image_url = None
        
        # Check for matplotlib code first
        plot_pattern = r'<!--PLOT-START-->(.*?)<!--PLOT-END-->'
        plot_match = re.search(plot_pattern, cleaned_response, re.DOTALL)
        
        # Check for TikZ code
        tikz_pattern = r'<!--TIKZ-START-->(.*?)<!--TIKZ-END-->'
        tikz_match = re.search(tikz_pattern, cleaned_response, re.DOTALL)
        
        if plot_match:
            plot_code = plot_match.group(1).strip()
            if plot_code.startswith('python'):
                plot_code = '\n'.join(plot_code.split('\n')[1:])
            
            image_filename = f"plot_{uuid.uuid4().hex[:8]}.png"
            compiled_image = generate_matplotlib_diagram(plot_code, image_filename)
            
            if compiled_image:
                plot_image_url = f"/static/generated/{compiled_image}"
                cleaned_response = re.sub(plot_pattern, 
                    f'<div class="math-diagram-container"><img src="{plot_image_url}" alt="Mathematical Diagram" class="math-diagram"></div>', 
                    cleaned_response, flags=re.DOTALL)
                logger.info(f"Successfully generated matplotlib diagram for text question: {plot_image_url}")
                
                def delayed_delete():
                    time.sleep(600)
                    try:
                        file_path = os.path.join('static', 'generated', compiled_image)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted served image: {compiled_image}")
                    except OSError as e:
                        logger.error(f"Failed to delete served image {compiled_image}: {e}")
                
                delete_thread = threading.Thread(target=delayed_delete, daemon=True)
                delete_thread.start()
            else:
                cleaned_response = re.sub(plot_pattern, 
                    '<p><em>Diagram generation failed. Please refer to the text solution.</em></p>', 
                    cleaned_response, flags=re.DOTALL)
                logger.warning("Matplotlib diagram generation failed for text question")
        
        elif tikz_match:
            tikz_code = tikz_match.group(1).strip()
            
            image_filename = f"tikz_{uuid.uuid4().hex[:8]}.png"
            compiled_image = generate_tikz_diagram(tikz_code, image_filename)
            
            if compiled_image:
                plot_image_url = f"/static/generated/{compiled_image}"
                cleaned_response = re.sub(tikz_pattern, 
                    f'<div class="math-diagram-container"><img src="{plot_image_url}" alt="Mathematical Diagram" class="math-diagram"></div>', 
                    cleaned_response, flags=re.DOTALL)
                logger.info(f"Successfully generated TikZ diagram for text question: {plot_image_url}")
                
                def delayed_delete():
                    time.sleep(600)
                    try:
                        file_path = os.path.join('static', 'generated', compiled_image)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted served image: {compiled_image}")
                    except OSError as e:
                        logger.error(f"Failed to delete served image {compiled_image}: {e}")
                
                delete_thread = threading.Thread(target=delayed_delete, daemon=True)
                delete_thread.start()
            else:
                cleaned_response = re.sub(tikz_pattern, 
                    '<p><em>Diagram generation failed. Please refer to the text solution.</em></p>', 
                    cleaned_response, flags=re.DOTALL)
                logger.warning("TikZ diagram generation failed for text question")
        
        result = {
            'success': True,
            'solution': cleaned_response,
            'has_diagram': plot_image_url is not None,
            'diagram_url': plot_image_url,
            'api_backend': api_backend,
            'cached': False
        }
        
        # Cache the result
        cache_response(cache_key, result)
        
        json.dumps(result)
        return jsonify(result)
        
    except Exception as e:
        logger.error('Error in /calculate-text: %s', str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again later.'
        }), 500

# Enhanced health check
@app.route('/health')
def health_check():
    """Enhanced health check endpoint"""
    try:
        cache_stats = {
            'entries': len(response_cache),
            'oldest_entry': min([ts for _, ts in response_cache.values()]) if response_cache else None
        }
        
        return jsonify({
            'status': 'healthy',
            'api_backend': api_backend,
            'project_id': PROJECT_ID if api_backend == 'vertex' else None,
            'location': LOCATION if api_backend == 'vertex' else None,
            'cache_stats': cache_stats,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
    # For production: gunicorn -w 4 -b 0.0.0.0:5000 app:app
