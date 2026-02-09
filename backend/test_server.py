"""
Quick test script to verify server can start
"""
import asyncio
import sys
from contextlib import asynccontextmanager

async def test_server_startup():
    """Test if server can start without errors"""
    print("Testing server startup...")
    
    try:
        # Test imports
        print("1. Testing imports...")
        from main import app
        print("   ✓ All imports successful")
        
        # Test config
        print("2. Testing configuration...")
        from config import settings
        print(f"   ✓ Config loaded - SECRET_KEY: {'Set' if len(settings.SECRET_KEY) >= 32 else 'Not set'}")
        print(f"   ✓ USE_S3: {settings.USE_S3}")
        print(f"   ✓ OLLAMA_URL: {settings.OLLAMA_BASE_URL}")
        
        # Test database initialization
        print("3. Testing database initialization...")
        from db.sqlite import SQLiteDB
        from db.vector import VectorDB
        
        sqlite_db = SQLiteDB()
        vector_db = VectorDB()
        
        await sqlite_db.initialize()
        print("   ✓ SQLite DB initialized")
        
        await vector_db.initialize()
        print("   ✓ Vector DB initialized")
        
        print("\n✅ All tests passed! Server should start successfully.")
        print("\nTo start the server, run: python main.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during startup test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_server_startup())
    sys.exit(0 if success else 1)






