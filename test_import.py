# test_imports.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from naledi.mncchain.mncauth import mncauth
    print("✅ mncauth module imported successfully")
except ModuleNotFoundError as e:
    print("❌ ModuleNotFoundError:", e)
