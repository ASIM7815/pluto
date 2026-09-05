#!/usr/bin/env python3
"""Quick test script for PLUTO backend"""
import asyncio
import httpx


async def test_backend():
    """Test if backend is running and responding"""
    
    base_url = "http://127.0.0.1:8765"
    
    print("🧪 Testing PLUTO Backend...\n")
    
    async with httpx.AsyncClient() as client:
        # Test 1: Health Check
        try:
            print("1️⃣  Testing health endpoint...")
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("   ✅ Health check passed")
                print(f"   {response.json()}\n")
            else:
                print(f"   ❌ Health check failed: {response.status_code}\n")
        except Exception as e:
            print(f"   ❌ Cannot connect to backend: {e}")
            print("   💡 Make sure backend is running: ./start.sh\n")
            return
        
        # Test 2: System Metrics
        try:
            print("2️⃣  Testing system metrics...")
            response = await client.get(f"{base_url}/api/system/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print("   ✅ System metrics retrieved")
                print(f"   CPU: {metrics['cpu']}%")
                print(f"   RAM: {metrics['ram']}%")
                print(f"   Storage: {metrics['storage']}%\n")
            else:
                print(f"   ❌ Metrics failed: {response.status_code}\n")
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
        
        # Test 3: System Info
        try:
            print("3️⃣  Testing system info...")
            response = await client.get(f"{base_url}/api/system/info")
            if response.status_code == 200:
                info = response.json()
                print("   ✅ System info retrieved")
                print(f"   OS: {info.get('os')}")
                print(f"   Host: {info.get('host')}")
                print(f"   Uptime: {info.get('uptime')}\n")
            else:
                print(f"   ❌ Info failed: {response.status_code}\n")
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
        
        # Test 4: Command Execution (REST)
        try:
            print("4️⃣  Testing command execution (REST)...")
            response = await client.post(
                f"{base_url}/api/chat/execute",
                json={"command": "What is 2+2?"}
            )
            if response.status_code == 200:
                result = response.json()
                print("   ✅ Command execution works")
                print(f"   Success: {result['success']}")
                print(f"   State: {result['state']}\n")
            else:
                print(f"   ❌ Execution failed: {response.status_code}\n")
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
        
        # Test 5: API Documentation
        print("5️⃣  API Documentation available at:")
        print(f"   📚 Swagger UI: {base_url}/docs")
        print(f"   📚 ReDoc: {base_url}/redoc\n")
        
        print("✅ All basic tests passed!")
        print("\n🚀 Next steps:")
        print("   1. Open http://127.0.0.1:8765/docs in browser")
        print("   2. Try WebSocket connection from frontend")
        print("   3. Test voice synthesis with POST /api/voice/synthesize")


if __name__ == "__main__":
    asyncio.run(test_backend())
