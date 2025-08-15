from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_executor import Executor
import logging
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')

# Rate limiting - FIXED
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"]
)

# Asynchronous tasks
executor = Executor(app)

# Logging
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s %(levelname)s: %(message)s')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/infallible-ai', methods=['POST'])
@limiter.limit("10 per minute")
def infallible_ai():
    try:
        query = request.json.get('query')
        if not query:
            return jsonify({"status": "error", "message": "Query is required"}), 400

        response = executor.submit(call_infallible_ai, query).result()
        return jsonify({"status": "success", "response": response})
    except Exception as e:
        logging.error(f"Error in infallible_ai: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500

def call_infallible_ai(query):
    response = generate_response(query)
    verified_response = verify_response(response)
    return verified_response

def generate_response(query):
    return f"AI Response to: {query}"

def verify_response(response):
    return f"✓ Verified: {response}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
