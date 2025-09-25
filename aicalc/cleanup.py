import os
import glob
import time
from aicalc.config import logger

CLEANUP_INTERVAL = 3600
MAX_FILE_AGE = 7200
MAX_FILES_COUNT = 500

def cleanup_generated_files():
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
    while True:
        try:
            cleanup_generated_files()
            time.sleep(CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"Error in cleanup worker: {e}")
            time.sleep(60)
