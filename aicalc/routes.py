from flask import Blueprint, request, jsonify, send_from_directory
from PIL import Image
import base64
import re
import uuid
import time
import os
import json
from datetime import datetime
from io import BytesIO
import threading
from aicalc.cache import get_cache_key, get_cached_response, cache_response, response_cache
from aicalc.ai_providers import generate_ai_response, api_backend
from aicalc.diagrams import generate_matplotlib_diagram, generate_tikz_diagram
from aicalc.config import logger

routes = Blueprint('routes', __name__)

@routes.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@routes.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@routes.app_errorhandler(404)
def not_found_error(error):
    return send_from_directory('static', '404.html'), 404

@routes.app_errorhandler(500)
def internal_error(error):
    return send_from_directory('static', '500.html'), 500

@routes.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        image_data = data.get('image')
        cache_key = get_cache_key(image_data=image_data)
        cached_result = get_cached_response(cache_key)
        if cached_result:
            logger.info("Returning cached result for image")
            return jsonify(cached_result)
        image_data = image_data.replace('data:image/png;base64,', '')
        image_bytes = base64.b64decode(image_data)
        img = Image.open(BytesIO(image_bytes))
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
            "When creating TikZ tree diagrams, ensure adequate spacing between nodes by using appropriate sibling distances. "
            "For binary trees, use sibling distances of at least 4cm for level 1, 2cm for level 2, 1cm for level 3, etc. "
            "Make sure nodes don't overlap and text is clearly readable. "
            "IMPORTANT: Do not include any markdown code block markers (like ```python or ```) in your response. "
            "IMPORTANT: Choose TikZ for formal computer science diagrams, automata, complex geometric proofs, trees. "
            "Choose matplotlib for function plots, statistical charts, simple geometric shapes. "
            "Do not reference 'python' as a variable or function name. "
            "Keep your response concise and focused on the solution."
        )
        response_text = generate_ai_response(prompt, img)
        cleaned_response = response_text
        cleaned_response = re.sub(r'^```(?:html|markdown)?\s*', '', cleaned_response)
        cleaned_response = re.sub(r'\s*```$', '', cleaned_response)
        cleaned_response = re.sub(r'```\w*\s*|\s*```', '', cleaned_response)
        plot_image_url = None
        plot_pattern = r'<!--PLOT-START-->(.*?)<!--PLOT-END-->'
        plot_match = re.search(plot_pattern, cleaned_response, re.DOTALL)
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
            'api_backend': api_backend,
            'cached': False
        }
        cache_response(cache_key, result)
        json.dumps(result)
        return jsonify(result)
    except Exception as e:
        logger.error('Error in /calculate: %s', str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again later.'
        }), 500

@routes.route('/calculate-text', methods=['POST'])
def calculate_text():
    try:
        data = request.json
        question_text = data.get('question')
        if not question_text or not question_text.strip():
            return jsonify({
                'success': False,
                'error': 'No question provided.'
            }), 400
        cache_key = get_cache_key(text_data=question_text)
        cached_result = get_cached_response(cache_key)
        if cached_result:
            logger.info("Returning cached result for text")
            return jsonify(cached_result)
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
            "When creating TikZ tree diagrams, ensure adequate spacing between nodes by using appropriate sibling distances. "
            "For binary trees, use sibling distances of at least 4cm for level 1, 2cm for level 2, 1cm for level 3, etc. "
            "Make sure nodes don't overlap and text is clearly readable. "
            "IMPORTANT: Do not include any markdown code block markers (like ```python or ```) in your response. "
            "IMPORTANT: Choose TikZ for formal computer science diagrams, automata, complex geometric proofs, trees. "
            "Choose matplotlib for function plots, statistical charts, simple geometric shapes. "
            "Keep your response clear, concise and mathematically accurate. "
            f"Question: {question_text}"
        )
        response_text = generate_ai_response(prompt)
        cleaned_response = response_text
        cleaned_response = re.sub(r'^```(?:html|markdown)?\s*', '', cleaned_response)
        cleaned_response = re.sub(r'\s*```$', '', cleaned_response)
        cleaned_response = re.sub(r'```\w*\s*|\s*```', '', cleaned_response)
        plot_image_url = None
        plot_pattern = r'<!--PLOT-START-->(.*?)<!--PLOT-END-->'
        plot_match = re.search(plot_pattern, cleaned_response, re.DOTALL)
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
        cache_response(cache_key, result)
        json.dumps(result)
        return jsonify(result)
    except Exception as e:
        logger.error('Error in /calculate-text: %s', str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again later.'
        }), 500

@routes.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200
