import sys
import os
from dotenv import load_dotenv

print("✅ Loading .env.preprod.store file...")

# Correct path joining
dotenv_path = os.path.join(os.path.dirname(__file__), "env", ".env.preprod.store")
print("📍 loading .env from:", dotenv_path)

print(f"📍 Full path: {dotenv_path}")
print("🧪 File exists?", os.path.exists(dotenv_path))
print("🧾 Directory listing of ./env:", os.listdir(os.path.join(os.path.dirname(__file__), "env")))




if not os.path.exists(dotenv_path):
    print("❌ error: .env.preprod.store file not found")
    sys.exit(1)

load_dotenv(dotenv_path=dotenv_path, verbose=True)

from core import create_app  # ✅ Import AFTER loading .env

try:
    print("🔧 Creating Flask app...")
    app = create_app("store")  # ✅ Explicit app type
    print("✅ Flask Application Created Successfully")
except Exception as e:
    print("❌ ERROR: App creation failed:", e)
    sys.exit(1)

if __name__ == "__main__":
    try:
        port = int(os.getenv("PORT", 5001))
        print(f"🚀 Running Flask App on http://localhost:{port}")
        app.run(host="localhost", port=port, debug=True)
    except Exception as e:
        print("❌ ERROR: Flask App failed to run:", e)
