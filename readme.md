🐍 Python 3.10 Virtual Environment
# Create venv
python3.10 -m venv venv

# Activate venv
# Windows PowerShell
venv\Scripts\Activate
# Linux/Mac
source venv/bin/activate

# Deactivate venv
deactivate


📦 Dependencies
# Install a package
pip install flask requests

# Install from requirements.txt
pip install -r requirements.txt

# Save installed packages
pip freeze > requirements.txt

# Upgrade pip
pip install --upgrade pip


Run server
# Run default (reload disabled)
uvicorn main:app --host 0.0.0.0 --port 8000

# Run with auto-reload (for development)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run with multiple workers
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000

python3.10 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000