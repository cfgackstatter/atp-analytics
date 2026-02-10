# application.py
"""AWS Elastic Beanstalk entry point for ATP Analytics."""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Ensure backend module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the FastAPI app
from backend.api.main import app

# EB expects 'application' variable
application = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application, host="0.0.0.0", port=8000)