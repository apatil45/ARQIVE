"""
Check GPU availability for Ollama
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
import httpx

print("=" * 60)
print("GPU Detection Check")
print("=" * 60)
print()

# Check 1: Ollama version endpoint
print("1. Checking Ollama version endpoint...")
try:
    response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/version", timeout=5)
    if response.status_code == 200:
        version_info = response.json()
        print(f"   Ollama version: {version_info}")
        print(f"   Full response: {version_info}")
    else:
        print(f"   Error: Status {response.status_code}")
except Exception as e:
    print(f"   Error: {e}")

print()

# Check 2: PyTorch CUDA
print("2. Checking PyTorch CUDA...")
try:
    import torch
    print(f"   PyTorch installed: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA device count: {torch.cuda.device_count()}")
        print(f"   CUDA device 0: {torch.cuda.get_device_name(0)}")
        print(f"   CUDA version: {torch.version.cuda}")
except ImportError:
    print("   PyTorch not installed")
except Exception as e:
    print(f"   Error: {e}")

print()

# Check 3: Ollama models
print("3. Checking Ollama models...")
try:
    from ollama import Client
    client = Client(host=settings.OLLAMA_BASE_URL)
    models = client.list()
    print(f"   Models found: {len(models.get('models', []))}")
    for model in models.get('models', []):
        print(f"   - {model.get('name', 'unknown')}")
        details = model.get('details', {})
        if details:
            print(f"     Details: {details}")
            backend = details.get('backend', '')
            print(f"     Backend: {backend}")
except Exception as e:
    print(f"   Error: {e}")

print()
print("=" * 60)



