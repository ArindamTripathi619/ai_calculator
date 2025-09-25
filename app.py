#!/usr/bin/env python3
"""
Optimized AI Calculator with Enhanced Gemini API
- Better error handling and retry logic
- Response caching to reduce API calls
- Performance optimizations
- Ready for Vertex AI when available
"""
from flask import Flask
import os
from dotenv import load_dotenv
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from aicalc.config import logger
from aicalc.ai_providers import initialize_ai_model, api_backend
from aicalc.cache import response_cache
from aicalc.cleanup import cleanup_worker, CLEANUP_INTERVAL, MAX_FILE_AGE, MAX_FILES_COUNT
from aicalc.routes import routes
import threading

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.register_blueprint(routes)

CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if os.getenv('CORS_ALLOWED_ORIGINS') else []
if CORS_ALLOWED_ORIGINS:
    CORS(app, origins=CORS_ALLOWED_ORIGINS)
else:
    CORS(app)

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
rate_limits = {
    "vertex": ["500 per day", "100 per hour", "30 per minute"],
    "gemini": ["200 per day", "50 per hour", "15 per minute"]
}
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=REDIS_URL,
    default_limits=rate_limits.get(api_backend, rate_limits["gemini"])
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

try:
    initialize_ai_model()
    logger.info(f"AI Backend: {api_backend}")
except Exception as e:
    logger.error(f"Failed to initialize AI: {e}")
    exit(1)

cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
cleanup_thread.start()
logger.info(f"Started cleanup worker thread (interval: {CLEANUP_INTERVAL/3600:.1f}h, max age: {MAX_FILE_AGE/3600:.1f}h)")

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
    # For production: gunicorn -w 4 -b 0.0.0.0:5000 app:app
