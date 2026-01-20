#!/bin/bash
# Script to check Gradio UI status in container

echo "=== Gradio UI Status Check ==="
echo ""

# 1. Check if gradio_ui.py exists
echo "1. Checking for gradio_ui.py..."
if [ -f "/app/gradio_ui.py" ]; then
    echo "   ✓ gradio_ui.py exists"
    echo "   File size: $(ls -lh /app/gradio_ui.py | awk '{print $5}')"
    echo "   Last modified: $(stat -c %y /app/gradio_ui.py 2>/dev/null || stat -f %Sm /app/gradio_ui.py 2>/dev/null)"
else
    echo "   ✗ gradio_ui.py NOT found"
fi
echo ""

# 2. Check if gradio is installed
echo "2. Checking if gradio is installed..."
if python -c "import gradio" 2>/dev/null; then
    echo "   ✓ gradio is installed"
    python -c "import gradio; print(f'   Version: {gradio.__version__}')" 2>/dev/null
else
    echo "   ✗ gradio is NOT installed"
fi
echo ""

# 3. Check if gradio_ui can be imported
echo "3. Checking if gradio_ui module can be imported..."
if python -c "from gradio_ui import create_ui" 2>/dev/null; then
    echo "   ✓ gradio_ui module imports successfully"
else
    echo "   ✗ gradio_ui module import FAILED"
    echo "   Error:"
    python -c "from gradio_ui import create_ui" 2>&1 | head -5
fi
echo ""

# 4. Check if create_ui function works
echo "4. Testing create_ui() function..."
if python -c "
import sys
sys.path.insert(0, '/app')
try:
    from gradio_ui import create_ui
    ui = create_ui()
    print('   ✓ create_ui() executed successfully')
    print(f'   UI type: {type(ui)}')
except Exception as e:
    print(f'   ✗ create_ui() FAILED: {e}')
    import traceback
    traceback.print_exc()
" 2>&1 | head -10; then
    echo ""
fi
echo ""

# 5. Check API server logs for Gradio messages
echo "5. Checking if API server is running..."
if pgrep -f "api_server.py" > /dev/null; then
    echo "   ✓ API server process is running"
    PID=$(pgrep -f "api_server.py" | head -1)
    echo "   PID: $PID"
else
    echo "   ✗ API server process NOT found"
fi
echo ""

# 6. Test endpoints
echo "6. Testing endpoints..."
echo "   Testing /health..."
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
if [ "$HEALTH_RESPONSE" = "200" ]; then
    echo "   ✓ /health returns 200"
else
    echo "   ✗ /health returns $HEALTH_RESPONSE"
fi

echo "   Testing /api..."
API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api 2>/dev/null || echo "000")
if [ "$API_RESPONSE" = "200" ]; then
    echo "   ✓ /api returns 200"
else
    echo "   ✗ /api returns $API_RESPONSE"
fi

echo "   Testing /ui..."
UI_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ui 2>/dev/null || echo "000")
if [ "$UI_RESPONSE" = "200" ] || [ "$UI_RESPONSE" = "301" ] || [ "$UI_RESPONSE" = "302" ]; then
    echo "   ✓ /ui returns $UI_RESPONSE"
else
    echo "   ✗ /ui returns $UI_RESPONSE"
    echo "   Response body (first 200 chars):"
    curl -s http://localhost:8000/ui 2>/dev/null | head -c 200
    echo ""
fi

echo "   Testing /ui/..."
UI_SLASH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ui/ 2>/dev/null || echo "000")
if [ "$UI_SLASH_RESPONSE" = "200" ]; then
    echo "   ✓ /ui/ returns 200"
else
    echo "   ✗ /ui/ returns $UI_SLASH_RESPONSE"
fi
echo ""

# 7. Check FastAPI routes
echo "7. Checking FastAPI application routes..."
if python -c "
import sys
sys.path.insert(0, '/app')
try:
    from api_server import app
    routes = [r.path for r in app.routes]
    print('   Available routes:')
    for route in sorted(set(routes)):
        print(f'     - {route}')
except Exception as e:
    print(f'   ✗ Failed to check routes: {e}')
" 2>&1; then
    echo ""
fi

# 8. Check if Gradio is mounted
echo "8. Checking if Gradio is mounted in FastAPI app..."
if python -c "
import sys
sys.path.insert(0, '/app')
try:
    from api_server import app
    import gradio as gr
    
    # Check if any route contains /ui
    routes_with_ui = [r.path for r in app.routes if '/ui' in r.path]
    if routes_with_ui:
        print('   ✓ Found routes with /ui:')
        for route in routes_with_ui:
            print(f'     - {route}')
    else:
        print('   ✗ No routes found with /ui')
        
    # Try to access Gradio app
    gradio_routes = [r for r in app.routes if hasattr(r, 'path') and '/ui' in r.path]
    print(f'   Gradio-related routes count: {len(gradio_routes)}')
except Exception as e:
    print(f'   ✗ Failed to check: {e}')
    import traceback
    traceback.print_exc()
" 2>&1; then
    echo ""
fi

echo "=== Summary ==="
echo "Run this script inside the container to diagnose Gradio UI issues."
echo "To run: bash /app/check_gradio.sh"


