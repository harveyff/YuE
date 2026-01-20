#!/bin/bash
# Script to check if YuE container is running the new version with Gradio UI

echo "=== YuE Version Check ==="
echo ""

# Check if gradio_ui.py exists
echo "1. Checking for gradio_ui.py..."
if [ -f "/app/gradio_ui.py" ]; then
    echo "   ✓ gradio_ui.py exists"
    echo "   File size: $(ls -lh /app/gradio_ui.py | awk '{print $5}')"
else
    echo "   ✗ gradio_ui.py NOT found"
fi
echo ""

# Check if top_200_tags.json exists
echo "2. Checking for top_200_tags.json..."
if [ -f "/app/top_200_tags.json" ]; then
    echo "   ✓ top_200_tags.json exists"
    echo "   File size: $(ls -lh /app/top_200_tags.json | awk '{print $5}')"
else
    echo "   ✗ top_200_tags.json NOT found"
fi
echo ""

# Check if gradio is installed
echo "3. Checking if gradio is installed..."
if python -c "import gradio" 2>/dev/null; then
    echo "   ✓ gradio is installed"
    python -c "import gradio; print(f'   Version: {gradio.__version__}')" 2>/dev/null
else
    echo "   ✗ gradio is NOT installed"
fi
echo ""

# Check if fastapi is installed
echo "4. Checking if fastapi is installed..."
if python -c "import fastapi" 2>/dev/null; then
    echo "   ✓ fastapi is installed"
    python -c "import fastapi; print(f'   Version: {fastapi.__version__}')" 2>/dev/null
else
    echo "   ✗ fastapi is NOT installed"
fi
echo ""

# Check api_server.py for Gradio references
echo "5. Checking api_server.py for Gradio code..."
if grep -q "gradio" /app/api_server.py 2>/dev/null; then
    echo "   ✓ api_server.py contains gradio references"
    echo "   Gradio import found: $(grep -c 'import gradio\|from gradio' /app/api_server.py || echo 0) times"
else
    echo "   ✗ api_server.py does NOT contain gradio references"
fi
echo ""

# Check environment variables
echo "6. Checking environment variables..."
echo "   STAGE1_MODEL: ${STAGE1_MODEL:-not set}"
echo "   STAGE2_MODEL: ${STAGE2_MODEL:-not set}"
echo "   OUTPUT_DIR: ${OUTPUT_DIR:-not set}"
echo "   PORT: ${PORT:-not set}"
echo "   HOST: ${HOST:-not set}"
echo ""

# Check if service is running and accessible
echo "7. Checking service endpoints..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✓ /health endpoint is accessible"
    curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || echo "   Response: $(curl -s http://localhost:8000/health)"
else
    echo "   ✗ /health endpoint is NOT accessible"
fi
echo ""

# Check if Gradio UI is accessible
echo "8. Checking Gradio UI endpoint..."
if curl -s http://localhost:8000/ | grep -q "gradio\|YuE Music Generation" 2>/dev/null; then
    echo "   ✓ Gradio UI appears to be accessible at /"
else
    echo "   ⚠ Gradio UI check inconclusive (may need to check manually)"
fi
echo ""

# Check API info endpoint
echo "9. Checking /api endpoint..."
if curl -s http://localhost:8000/api > /dev/null 2>&1; then
    echo "   ✓ /api endpoint is accessible"
    curl -s http://localhost:8000/api | python -m json.tool 2>/dev/null || echo "   Response: $(curl -s http://localhost:8000/api)"
else
    echo "   ✗ /api endpoint is NOT accessible"
fi
echo ""

echo "=== Summary ==="
if [ -f "/app/gradio_ui.py" ] && python -c "import gradio" 2>/dev/null; then
    echo "✓ This appears to be the NEW version with Gradio UI"
else
    echo "✗ This appears to be the OLD version without Gradio UI"
fi

