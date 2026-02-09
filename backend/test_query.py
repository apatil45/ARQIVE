"""
Test RAG query endpoint
"""
import asyncio
import time
import requests
import json

def test_query():
    """Test the RAG query endpoint"""
    base_url = "http://localhost:8000"
    
    print("=" * 60)
    print("Testing ARQIVE RAG Query")
    print("=" * 60)
    
    # Step 1: Login
    print("\n1. Logging in...")
    try:
        login_response = requests.post(
            f"{base_url}/auth/login",
            data={"username": "admin", "password": "admin"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        login_response.raise_for_status()
        token = login_response.json()["access_token"]
        print(f"   [OK] Login successful")
        print(f"   Token: {token[:30]}...")
    except Exception as e:
        print(f"   [FAIL] Login failed: {e}")
        return
    
    # Step 2: Test query
    print("\n2. Testing RAG query...")
    query = "What documents are available? What information can you find?"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    query_data = {
        "query": query,
        "max_results": 3,
        "stream": False
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/query",
            headers=headers,
            json=query_data,
            timeout=30
        )
        end_time = time.time()
        duration = end_time - start_time
        
        response.raise_for_status()
        result = response.json()
        
        print(f"   [OK] Query successful!")
        print(f"   Response time: {duration:.2f} seconds")
        print(f"\n   Query: {query}")
        print(f"\n   Answer (first 300 chars):")
        answer = result.get('answer', '')
        try:
            print(f"   {answer[:300]}...")
        except UnicodeEncodeError:
            # Fallback for Windows console encoding issues
            print(f"   {answer[:300].encode('ascii', 'ignore').decode('ascii')}...")
        print(f"\n   Sources: {', '.join(result.get('sources', []))}")
        print(f"   Citations: {len(result.get('citations', []))}")
        
        # Performance analysis
        print(f"\n   Performance:")
        if duration < 3:
            print(f"   [GOOD] Fast response (< 3s)")
        elif duration < 6:
            print(f"   [WARN] Moderate response (3-6s)")
        else:
            print(f"   [SLOW] Slow response (> 6s)")
            
    except requests.exceptions.Timeout:
        print(f"   [FAIL] Query timed out (> 30s)")
    except Exception as e:
        print(f"   [FAIL] Query failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
    
    # Step 3: Test second query (should use cache)
    print("\n3. Testing second query (should use cache)...")
    query2 = "Summarize the main topics"
    
    query_data2 = {
        "query": query2,
        "max_results": 3,
        "stream": False
    }
    
    try:
        start_time = time.time()
        response2 = requests.post(
            f"{base_url}/query",
            headers=headers,
            json=query_data2,
            timeout=30
        )
        end_time = time.time()
        duration2 = end_time - start_time
        
        response2.raise_for_status()
        result2 = response2.json()
        
        print(f"   [OK] Second query successful!")
        print(f"   Response time: {duration2:.2f} seconds")
        if duration > 0:
            improvement = ((duration - duration2) / duration * 100)
            print(f"   Improvement: {improvement:.1f}% faster")
        
    except Exception as e:
        print(f"   [FAIL] Second query failed: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_query()

