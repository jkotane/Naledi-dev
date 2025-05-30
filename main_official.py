import sys
#from apps import create_app
import os
from dotenv import load_dotenv

# temporary fix for the issue with the dotenv package
#from dotenv import load_dotenv

print("✅ Loading .env.preprod.official file...")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

dotenv_path = os.path.join(os.path.dirname(__file__), 'env/.env.preprod.official')
print("loading .env from ", {dotenv_path})
# Manually load .env file

if not os.path.exists(dotenv_path):
    print("❌ error: .env.preprod.official file not found")
    exit(1)


load_dotenv(dotenv_path=dotenv_path, verbose=True)

from core import create_app  # ✅ Import AFTER loading .env

#db_uri = os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL")
try:
    print("trying to create flask app")
    app = create_app("official")  # Explicitly call the function
    #from main_official import app
   # print(app.url_map)       # to be removed after debuging

    print("✅ Flask Application Created Successfully")
except Exception as e:
    print("❌ ERROR: App creation failed:", e)
    sys.exit(1)  # Exit with error


if __name__ == "__main__":
    try:
        port = int(os.getenv("PORT", 5002))  # Use PORT from Cloud Run (default to 8080)
        print(f"✅ Running Flask App on port {port}")
        app.run(host="localhost", port=5002, debug=True)  # Force it to use the correct port
    except Exception as e:
        print("❌ ERROR: Flask App failed to run:", e)