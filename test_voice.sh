#!/bin/bash
# Test PLUTO's new female voice

echo "🎤 Testing PLUTO Female Voice"
echo "==============================="
echo ""

echo "Test 1: Simple greeting..."
curl -X POST http://127.0.0.1:8765/api/chat/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "Say hello in a friendly way"}' \
  2>/dev/null | python3 -m json.tool

echo ""
echo "Test 2: Open YouTube (context test)..."
curl -X POST http://127.0.0.1:8765/api/chat/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "Open YouTube"}' \
  2>/dev/null | python3 -m json.tool

echo ""
echo "Test 3: Silence command..."
curl -X POST http://127.0.0.1:8765/api/chat/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "silence"}' \
  2>/dev/null | python3 -m json.tool

echo ""
echo "✅ All tests completed!"
