from dotenv import load_dotenv

# ponytail: loaded here, not in main.py, so it runs before any src module
# reads env at import time — for both the API and the Celery worker.
load_dotenv()
