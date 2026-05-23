import logging
from logging.handlers import RotatingFileHandler
import os

def get_logger(name="finance_app"):
    logger = logging.getLogger(name)
    
    # If logger already has handlers, return it to avoid duplicate logs
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.ERROR)
    
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, "app.log")
    
    # Rotating file handler: Max 1MB per file, keeping 1 backup (app.log and app.log.1)
    handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=1, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger

# Global logger instance
logger = get_logger()
