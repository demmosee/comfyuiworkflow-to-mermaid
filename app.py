import os
import sys
import json
from flask import Flask, request, jsonify, send_from_directory
import traceback
import webbrowser
import threading

def get_base_path():

    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
# print(f"DEBUG: Application Base Directory determined as: {BASE_DIR}") 

# --- Application Base Default Configuration ---
APP_BASE_DEFAULTS = {
    "Default_Graph_Direction": "TD",
    "Generate_ComfyUI_Subgraphs": True,
    "Default_Connector": "-->",
    "Default_Node_Shape": "rectangle",
    "Add_Link_Labels": True,
    "App_Port": 5000,
}

effective_default_config = APP_BASE_DEFAULTS.copy()

# --- Import Core Functionality from Existing Script ---
try:
    from workflow_to_mermaid import workflow_to_mermaid, default_config as imported_mermaid_generator_defaults
    import mermaid_styles
    print("Successfully imported workflow_to_mermaid and mermaid_styles modules.")
    effective_default_config.update(imported_mermaid_generator_defaults)
    effective_default_config["App_Port"] = APP_BASE_DEFAULTS["App_Port"]
except ImportError as e:
    print(f"Error: Could not import necessary modules: {e}")
    print("Please ensure app.py, workflow_to_mermaid.py, and mermaid_styles.py are in the same directory or accessible.")
    def workflow_to_mermaid(workflow, config): # pylint: disable=unused-argument
        raise RuntimeError("Core conversion module failed to load, cannot perform conversion.")

# --- Flask Application Setup ---
STATIC_FOLDER_PATH = os.path.join(BASE_DIR, 'static')
# print(f"DEBUG: Static folder path set to: {STATIC_FOLDER_PATH}")

app = Flask(__name__, static_folder=STATIC_FOLDER_PATH, static_url_path='')

MERMAID_CONFIG_PATH = os.path.join(BASE_DIR, "Mermaid_config.json")
# print(f"DEBUG: Mermaid_config.json path set to: {MERMAID_CONFIG_PATH}")

# --- Helper Function: Load Server Startup Configuration (e.g., Port) ---
def get_server_startup_config():
    default_port_value = APP_BASE_DEFAULTS["App_Port"]
    current_port = default_port_value
    if os.path.exists(MERMAID_CONFIG_PATH):
        try:
            with open(MERMAID_CONFIG_PATH, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            app_port_from_file = user_config.get("App_Port")
            if app_port_from_file is not None:
                try:
                    port_val = int(app_port_from_file)
                    if 1024 <= port_val <= 65535:
                        current_port = port_val
                        print(f"Using port from '{MERMAID_CONFIG_PATH}': {current_port}.")
                    else:
                        print(f"Warning: Port {port_val} in config file is out of valid range (1024-65535). Using default port {default_port_value}.")
                        current_port = default_port_value
                except ValueError:
                    print(f"Warning: 'App_Port' in config file is not a valid integer: '{app_port_from_file}'. Using default port {default_port_value}.")
                    current_port = default_port_value
            else:
                print(f"Did not find 'App_Port' in '{MERMAID_CONFIG_PATH}'. Using default port {default_port_value}.")
        except json.JSONDecodeError:
            print(f"Warning: Could not parse config file '{MERMAID_CONFIG_PATH}'. Using default port {default_port_value}.")
        except Exception as e:
            print(f"Error loading startup config file '{MERMAID_CONFIG_PATH}': {e}. Using default port {default_port_value}.")
    else:
        print(f"Config file '{MERMAID_CONFIG_PATH}' not found. Using default port {default_port_value}.")
    return current_port

# --- Helper Function: Load Mermaid UI Configuration ---
def load_mermaid_config():
    config = effective_default_config.copy()
    if os.path.exists(MERMAID_CONFIG_PATH):
        try:
            with open(MERMAID_CONFIG_PATH, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            config.update(user_config)
            print(f"Successfully loaded and merged configuration from '{MERMAID_CONFIG_PATH}'.")
        except json.JSONDecodeError:
            print(f"Warning: Could not parse config file '{MERMAID_CONFIG_PATH}'. Using internal default configuration only.")
        except Exception as e:
            print(f"Unknown error loading config file '{MERMAID_CONFIG_PATH}': {e}. Using internal default configuration only.")
    else:
        print(f"Warning: Config file '{MERMAID_CONFIG_PATH}' not found. Using internal default configuration.")
    config["Generate_ComfyUI_Subgraphs"] = str(config.get("Generate_ComfyUI_Subgraphs", True)).lower() == 'true'
    config["Add_Link_Labels"] = str(config.get("Add_Link_Labels", True)).lower() == 'true'
    return config

# --- Helper Function: Save Configuration ---
def save_mermaid_config(new_config_data):
    try:
        current_full_config = {}
        if os.path.exists(MERMAID_CONFIG_PATH):
            try:
                with open(MERMAID_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    current_full_config = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to read existing config '{MERMAID_CONFIG_PATH}', updating based on defaults: {e}")
                current_full_config = effective_default_config.copy()
        else:
            current_full_config = effective_default_config.copy()
        for key, value in new_config_data.items():
            current_full_config[key] = value
        with open(MERMAID_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(current_full_config, f, indent=2, ensure_ascii=False)
        print(f"Configuration successfully saved to '{MERMAID_CONFIG_PATH}'.")
        return True
    except Exception as e:
        print(f"Error: Failed to save configuration to '{MERMAID_CONFIG_PATH}': {e}")
        traceback.print_exc()
        return False

# --- API Endpoint: Handle Conversion Request ---
@app.route('/api/convert', methods=['POST'])
def handle_convert():
    print("Received /api/convert request")
    try:
        data = request.get_json()
        if not data or 'workflow_json' not in data:
            return jsonify({"status": "error", "message": "Missing 'workflow_json' field in request body"}), 400
        workflow_json_string = data['workflow_json']
        try:
            workflow_dict = json.loads(workflow_json_string)
            if not isinstance(workflow_dict, dict):
                raise ValueError("Provided JSON is not a valid object (dictionary)")
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Provided Workflow JSON is invalid"}), 400
        except ValueError as ve:
            return jsonify({"status": "error", "message": str(ve)}), 400
        current_config = load_mermaid_config()
        mermaid_code = workflow_to_mermaid(workflow_dict, current_config)
        return jsonify({"status": "success", "mermaid_code": mermaid_code})
    except RuntimeError as re:
        print(f"Runtime error: {re}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(re)}), 500
    except Exception as e:
        print(f"Uncaught error processing conversion request: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Internal server error: {str(e)}"}), 500

# --- API Endpoint: Get Current Config Settings ---
@app.route('/api/get_config', methods=['GET'])
def get_config_settings():
    print("Received /api/get_config request")
    try:
        current_config = load_mermaid_config()
        dc = effective_default_config
        frontend_settings = {
            "Default_Graph_Direction": current_config.get("Default_Graph_Direction", dc.get("Default_Graph_Direction", "TD")),
            "Generate_ComfyUI_Subgraphs": current_config.get("Generate_ComfyUI_Subgraphs", dc.get("Generate_ComfyUI_Subgraphs", True)),
            "Default_Connector": current_config.get("Default_Connector", dc.get("Default_Connector", "-->")),
            "Default_Node_Shape": current_config.get("Default_Node_Shape", dc.get("Default_Node_Shape", "rectangle")),
            "Add_Link_Labels": current_config.get("Add_Link_Labels", dc.get("Add_Link_Labels", True))
        }
        return jsonify({"status": "success", "settings": frontend_settings})
    except Exception as e:
        print(f"Error getting configuration: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Failed to get configuration: {str(e)}"}), 500

# --- API Endpoint: Update Config Settings ---
@app.route('/api/update_config', methods=['POST'])
def update_config_settings():
    print("Received /api/update_config request")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Missing configuration data in request body"}), 400
        allowed_keys_map = {
            "Default_Graph_Direction": str, "Generate_ComfyUI_Subgraphs": bool,
            "Default_Connector": str, "Default_Node_Shape": str, "Add_Link_Labels": bool
        }
        update_payload = {}
        for key, expected_type in allowed_keys_map.items():
            if key in data:
                value = data[key]
                if expected_type is bool:
                    if isinstance(value, bool): update_payload[key] = value
                    elif isinstance(value, str) and value.lower() in ['true', 'false']: update_payload[key] = value.lower() == 'true'
                    else: return jsonify({"status": "error", "message": f"Incorrect value type for field '{key}'. Expected boolean, received {type(value).__name__}."}), 400
                elif expected_type is str:
                    if isinstance(value, str): update_payload[key] = value
                    else: return jsonify({"status": "error", "message": f"Incorrect value type for field '{key}'. Expected string, received {type(value).__name__}."}), 400
                else: # Should not happen with current allowed_keys_map
                    if isinstance(value, expected_type): update_payload[key] = value
                    else: return jsonify({"status": "error", "message": f"Incorrect value type for field '{key}'. Expected {expected_type.__name__}, received {type(value).__name__}."}), 400
        if not update_payload:
            return jsonify({"status": "error", "message": "No valid configuration items provided for update"}), 400
        if save_mermaid_config(update_payload):
            return jsonify({"status": "success", "message": "Configuration updated. Please reload workflow or refresh to see changes."})
        else:
            return jsonify({"status": "error", "message": "Failed to save configuration to file."}), 500
    except Exception as e:
        print(f"Error updating configuration: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Failed to update configuration: {str(e)}"}), 500

# --- Route: Serve Frontend Page ---
@app.route('/')
def serve_index():
    print("Request for root path /, serving index.html")
    try:
        # app.static_folder is now an absolute path set during Flask initialization
        return send_from_directory(app.static_folder, 'index.html')
    except FileNotFoundError:
        # Construct the full path for a more informative error message
        expected_file_path = os.path.join(app.static_folder, 'index.html')
        return f"Error: Frontend file '{expected_file_path}' not found. Ensure frontend files are correctly placed.", 404

# --- Start Server ---
if __name__ == '__main__':

    DEBUG_MODE = True

    server_port = get_server_startup_config()
    url_to_open = f"http://127.0.0.1:{server_port}"

    def open_browser_after_delay():
        try:
            print(f"Preparing to open browser to: {url_to_open} in 1 second.")
            webbrowser.open_new_tab(url_to_open)
            print("Browser open command issued.")
        except Exception as e:
            print(f"Could not automatically open browser: {e}")

    print(f"Starting Flask server, listening on 0.0.0.0, port {server_port}...")
    print(f"Open your browser and go to {url_to_open}")

    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, open_browser_after_delay).start()

    app.run(debug=DEBUG_MODE, host='0.0.0.0', port=server_port, use_reloader=DEBUG_MODE)
