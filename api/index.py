"""
Vercel serverless function entry point for Flask app
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set environment for Vercel
os.environ.setdefault('FLASK_ENV', 'production')

# Import Flask app - wrap import in try/except to handle import errors
app = None
create_app = None

try:
    from backend.app import create_app
except (ImportError, ModuleNotFoundError) as import_error:
    # Handle import errors (missing dependencies, circular imports, etc.)
    import traceback
    print("=" * 80)
    print("IMPORT ERROR: Failed to import backend.app")
    print(f"Error: {str(import_error)}")
    print("TRACEBACK:")
    traceback.print_exc()
    print("=" * 80)
    # Create minimal error app
    from flask import Flask, jsonify
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def import_error_handler(path):
        return jsonify({
            "error": "Import error",
            "message": f"Failed to import application: {str(import_error)}"
        }), 500

# Create Flask app instance (only if import succeeded)
if create_app is not None:
    try:
        app = create_app()
    except Exception as e:
        # Log initialization errors for debugging
        import traceback
        print("=" * 80)
        print("FATAL ERROR: Failed to initialize Flask app")
        print(f"Error: {str(e)}")
        print("TRACEBACK:")
        traceback.print_exc()
        print("=" * 80)
        
        # Create a minimal error app to prevent complete failure
        from flask import Flask, jsonify
        error_app = Flask(__name__)
        
        @error_app.route('/', defaults={'path': ''})
        @error_app.route('/<path:path>')
        def error_handler(path):
            return jsonify({
                "error": "Application initialization failed",
                "message": str(e)
            }), 500
        
        app = error_app

# Ensure app is always defined
if app is None:
    from flask import Flask, jsonify
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def unknown_error_handler(path):
        return jsonify({
            "error": "Unknown error",
            "message": "Application failed to initialize"
        }), 500

# Export app for Vercel
# Vercel Python runtime will automatically handle WSGI apps
__all__ = ['app']
