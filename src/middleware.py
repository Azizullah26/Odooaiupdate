import os
import logging
from flask import Flask, request, jsonify, session, g
from flask_caching import Cache
from functools import wraps
from odoo_client import OdooClient  # Assumes you have this
from rasa_nlp import RasaNLPProcessor
from datetime import timedelta
import re
from typing import Optional
import summary_report

# --- Minimal Middleware class for direct use ---
class Middleware:
    def __init__(self, odoo_client):
        self.odoo = odoo_client
        self.summary_report = summary_report.SummaryReport()

    def find_WO_id(self, text: str) -> Optional[str]:
        """
        Extracts the work‐order reference from free text.  
        1) Looks for "wo ref" or "work order ref" followed by an alphanumeric string.
        2) Falls back to numeric-only patterns (e.g. "WO 1234", "project id 5678").
        """
        # 1) Alphanumeric WO ref after "wo ref" or "work order ref"
        match = re.search(
            r'\bwo\s*ref(?:erence)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\s\-_]+)',
            text,
            re.IGNORECASE
        )
        if match:
            # strip trailing punctuation/spaces
            return match.group(1).strip().rstrip('?.!,;')

        # 2) Fallback: purely numeric ID after "wo", "wo number", etc.
        match = re.search(
            r'\b(?:project\s*id|wo(?:\s*number)?|work\s*order\s*number)\s*[:\-]?\s*(\d+)\b',
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(1)

        # 3) Last‐ditch: any standalone 3-6 digit sequence
        match = re.search(r'\b(\d{3,6})\b', text)
        return match.group(1) if match else None

    def process(self, parsed_query):
        
        intent   = parsed_query.get('intent')
        entities = parsed_query.get('entities')
        #entities = self.find_WO_id(parsed_query.get('original_query'))
        #print(entities)

         # 1) Check user permission before anything else but for demo purposes we will skip this
        user_id = input("Please enter your user ID: ").strip()

        if user_id == '1':
            print("Permission granted")
        else:
            return {'success': False, 'error': 'Permission denied.'}

        if intent == "unknown":
            return {'success': False, 'result': f'Unknown intent: {intent}.', 
            'response': "The app is under modification. Please look for what you need manually"}

        #if not self.authenticate_user(intent):
        #    return {'success': False, 'error': 'Authorization failed.'}
        project_header = self.odoo.work_order_header(entities)

        # 2) Dispatch 
        if intent == 'work_order_details':
            result = self.odoo.work_order_details(entities)
            #print(result) 

        elif intent == 'work_order_finances':
            result = self.odoo.work_order_finances(entities)

        elif intent == 'work_order_papers':
            result = self.odoo.work_order_papers(entities) 

        elif intent == 'time_taken':
            result = self.odoo.work_order_time(entities)

        elif intent == 'get_work_orders':
            result = self.odoo.get_work_orders(entities)

        elif intent == 'work_order_employees':
            result = self.odoo.work_order_employees(entities)

        response = self.generate_summary_report(intent, project_header, result)

        if result and response and project_header:
            return {'success': True,'result': result ,'response': response}

        # Add more intent-method mappings as needed
        

    def generate_summary_report(self, intent: str, project_header: dict[str, any], result: dict[str, any]) -> str:
        """
        If the last query was an expense request, render the full markdown
        report. Otherwise return an empty string.
        """
        #this is the odoo result
        header  = project_header.get('project_header', {})
        odoo_result = result.get('data',{})
        #print(odoo_result)

        # If the Odoo call failed, show its error
        if not result.get('success', False):
            return result.get('error', "")

        if not project_header.get('success', False):
            return project_header.get('error', "")

        header = self.summary_report.generate_header(header)

        if intent == 'work_order_finances':
            summary = self.summary_report.generate_expense_report(odoo_result)

        elif intent == 'work_order_details':
            summary = self.summary_report.generate_details_report(odoo_result)

        elif intent == 'work_order_papers':
            summary = self.summary_report.generate_papers_report(odoo_result)

        elif intent == 'work_order_time':
            summary = self.summary_report.generate_time_report(odoo_result)

        elif intent == 'get_work_orders':
            summary = self.summary_report.generate_work_orders_report(odoo_result)

            return summary

        elif intent == 'work_order_employees':
            summary = self.summary_report.generate_employees_report(odoo_result)
            
        return header + "\n" + summary


    def authenticate_user(self, intent: str) -> bool:
        """
        Prompt for user ID, verify permission for the given intent.
        Returns True if allowed, else prints error and returns False.
        """
        try:
            uid = int(input("Please enter your user ID: ").strip())
        except ValueError:
            print("❌ Invalid user ID format.")
            return False

        res = self.odoo.verify_user_permission(uid, intent)
        if not res['success']:
            print(f"❌ {res['error']}")
            return False

        return True


# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Caching setup
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# NLP and Odoo client
nlp = RasaNLPProcessor()
odoo = OdooClient()

# Attempt to login right away
if not odoo.authenticate():
    logger.critical("Could not authenticate to Odoo – check your ODOO_* env vars")
    raise SystemExit(1)

# --- Authentication & Session Management ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    username = data.get('username')
    password = data.get('password')
    # Replace with real authentication logic
    if username == 'admin' and password == 'admin':
        session['user_id'] = username
        session.permanent = True
        logger.info(f"User {username} logged in.")
        return jsonify({'message': 'Login successful'})
    else:
        logger.warning(f"Failed login attempt for user {username}")
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route("/project/<int:project_id>/expense", methods=["GET"])
@login_required
def get_project_expense(project_id):
    result = odoo.get_work_order_expense(project_id)
    return jsonify(result)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    user = session.pop('user_id', None)
    logger.info(f"User {user} logged out.")
    return jsonify({'message': 'Logged out'})

# --- NLP Handling ---
@app.route('/nlp', methods=['POST'])
@login_required
def nlp_query():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    query = data.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    cache_key = f"nlp:{query}"
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for query: {query}")
        return jsonify({'result': cached, 'cached': True})
    try:
        result = nlp.parse_query(query)
        cache.set(cache_key, result)
        logger.info(f"NLP processed for query: {query}")
        return jsonify({'result': result, 'cached': False})
    except Exception as e:
        logger.error(f"NLP error: {str(e)}")
        return jsonify({'error': 'NLP processing failed', 'details': str(e)}), 500

# --- Odoo API Proxy ---
@app.route("/project/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    """
    Returns the JSON for a single project by its numeric ID.
    """
    result = odoo.get_project(project_id)
    return jsonify(result)

@app.route('/odoo', methods=['POST'])
@login_required
def odoo_proxy():
    """
    Generic proxy: expects a JSON body:
      { "method": "method_name", "params": [ ... ] }
    and calls that method on the OdooClient.
    """
    body = request.get_json(force=True)
    method = body.get("method")
    params = body.get("params", [])

    if not method:
        return jsonify({"error": "Missing 'method' in request body"}), 400

    # Dispatch to your OdooClient instance
    if not hasattr(odoo, method):
        return jsonify({"error": f"Unknown method '{method}'"}), 400

    try:
        result = getattr(odoo, method)(*params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/project/<int:project_id>/manager", methods=["GET"])
@login_required
def get_project_manager(project_id):
    """Return the project’s manager info."""
    result = odoo.get_project_manager(project_id)
    return jsonify(result)
@login_required
def odoo_proxy():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    method = data.get('method')
    params = data.get('params', {})
    cache_key = f"odoo:{method}:{str(params)}"
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for Odoo method: {method}")
        return jsonify({'result': cached, 'cached': True})
    try:
        result = odoo.call_method(method, **params)
        cache.set(cache_key, result)
        logger.info(f"Odoo API call: {method}")
        return jsonify({'result': result, 'cached': False})
    except Exception as e:
        logger.error(f"Odoo API error: {str(e)}")
        return jsonify({'error': 'Odoo API call failed', 'details': str(e)}), 500


# --- Error Handling ---
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

# --- Main Entrypoint ---
if __name__ == '__main__':
    app.run(debug=True)
