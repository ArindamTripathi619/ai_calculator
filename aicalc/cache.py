from aicalc.config import logger
import hashlib
import time

response_cache = {}
CACHE_TTL = 3600  # 1 hour

def get_cache_key(image_data=None, text_data=None):
    if image_data:
        return hashlib.md5(image_data.encode()).hexdigest()
    elif text_data:
        return hashlib.md5(text_data.encode()).hexdigest()
    return None

def get_cached_response(cache_key):
    if cache_key in response_cache:
        cached_data, timestamp = response_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"Cache hit for key: {cache_key[:8]}...")
            return cached_data
        else:
            del response_cache[cache_key]
    return None

def cache_response(cache_key, response_data):
    response_cache[cache_key] = (response_data, time.time())
    logger.info(f"Cached response for key: {cache_key[:8]}...")
    current_time = time.time()
    expired_keys = [k for k, (_, ts) in response_cache.items() if current_time - ts > CACHE_TTL]
    for k in expired_keys:
        del response_cache[k]
