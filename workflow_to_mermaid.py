import json
import os
import numbers
import traceback  # Keep for error handling

# --- Import the style and shape functions ---
try:
    # --- MODIFIED: Import new combined function and syntax getter ---
    from mermaid_styles import (
        get_node_style_and_shape,
        get_link_style,
        clear_style_cache,
        get_mermaid_shape_syntax,
        _resolve_style_alias,  # Keep for default node style resolution
        adjust_text_color_for_background  # Keep for default node style resolution
    )
except ImportError:
    print("Error: Could not import 'mermaid_styles.py'. Please ensure it is in the same directory as this script.")


    # Define dummy functions to prevent NameError
    def get_node_style_and_shape(*args, **kwargs):
        return {"style": "", "shape": "rectangle"}


    def get_link_style(link_index, start_node_id_num, end_node_id_num,
                       start_node_type, end_node_type,
                       config, node_id_to_group_names, style_definitions,
                       link_data_type=None,  # Added for dummy
                       **kwargs):
        return {'connector': '-->', 'style': '', 'add_label': True}


    def clear_style_cache():
        pass


    def get_mermaid_shape_syntax(shape_name):
        return ('[', ']')


    def _resolve_style_alias(s, d):
        return s  # Dummy for standalone


    def adjust_text_color_for_background(s):
        return s  # Dummy for standalone

# --- Internal Default Configuration ---
default_config = {
    "Default_Graph_Direction": "TD",
    "Link_Styles": [],
    "Node_Styles": {},  # Now expects objects: {"NodeType": {"style": "...", "shape": "..."}}
    "Default_Connector": "-->",
    "Default_Node_Style": "",
    "Add_Link_Labels": True,
    "Generate_ComfyUI_Subgraphs": True,
    "Style_Definitions": {},
    "Node_Group_Styles": [],
    "Link_Group_Styles": [],
    "Data_Type_Link_Styles": [],  # ADDED: For link styling based on data type
    "Node_Group": [],
    "Default_Node_Shape": "rectangle",
}

# --- Configuration File Loading ---
config_path = "Mermaid_config.json"  # Relative path
config = None  # Will hold the final configuration

# Determine the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the absolute path to the config file
absolute_config_path = os.path.join(script_dir, config_path)

if os.path.exists(absolute_config_path):
    try:
        with open(absolute_config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        print(f"Successfully loaded configuration from '{absolute_config_path}'.")
        config = default_config.copy()
        config.update(user_config)
    except json.JSONDecodeError:
        print(f"Error: Could not parse config file '{absolute_config_path}'. Using internal default configuration.")
        config = default_config.copy()
    except Exception as e:
        print(f"Unknown error loading config file '{absolute_config_path}': {e}. Using internal default configuration.")
        config = default_config.copy()
else:
    print(f"Warning: Config file '{absolute_config_path}' not found. Using internal default configuration.")
    config = default_config.copy()

# --- Mermaid Link Style Templates (Unchanged) ---
LINK_LABEL_FORMATS = {
    "-->": "-- {} -->", "---": "-- {} ---", "-.->": "-. {} .->", "-.-": "-. {} .-",
    "==>": "== {} ==>", "===": "== {} ===", "--o": "-- {} --o", "o--": "o-- {} --",
    "o--o": "o-- {} --o", "--x": "-- {} --x", "x--": "x-- {} --", "x--x": "x-- {} --x",
    "<-->": "<-- {} -->", "<-.->": "<-. {} .->", "<==>": "<== {} ==>",
}


# --- Helper Function (calculate_overlap_area remains unchanged) ---
# Calculates the overlapping area between a node and a group.
def calculate_overlap_area(node, group) -> float:
    node_pos = node.get('pos')
    node_size = node.get('size')
    nx, ny, nw, nh = None, None, None, None
    if isinstance(node_pos, list) and len(node_pos) >= 2:
        nx, ny = node_pos[0], node_pos[1]
    elif isinstance(node_pos, dict):
        px_key = "0" if "0" in node_pos else (0 if 0 in node_pos else None)
        py_key = "1" if "1" in node_pos else (1 if 1 in node_pos else None)
        if px_key is not None and py_key is not None:
            nx = node_pos.get(px_key)
            ny = node_pos.get(py_key)
    if isinstance(node_size, list) and len(node_size) >= 2:
        nw, nh = node_size[0], node_size[1]
    elif isinstance(node_size, dict):
        sx_key = "0" if "0" in node_size else (0 if 0 in node_size else None)
        sy_key = "1" if "1" in node_size else (1 if 1 in node_size else None)
        if sx_key is not None and sy_key is not None:
            nw = node_size.get(sx_key)
            nh = node_size.get(sy_key)
    if not all(isinstance(v, numbers.Number) for v in [nx, ny, nw, nh]):
        return 0.0
    if nw <= 0 or nh <= 0:
        return 0.0
    bounding = group.get('bounding')
    gx, gy, gw, gh = None, None, None, None
    if isinstance(bounding, list) and len(bounding) >= 4:
        if all(isinstance(v, numbers.Number) for v in bounding[:4]):
            gx, gy, gw, gh = bounding[0], bounding[1], bounding[2], bounding[3]
        else:
            return 0.0
    else:
        return 0.0
    if gw <= 0 or gh <= 0:
        return 0.0
    node_left = nx
    node_top = ny
    node_right = nx + nw
    node_bottom = ny + nh
    group_left = gx
    group_top = gy
    group_right = gx + gw
    group_bottom = gy + gh
    intersection_left = max(node_left, group_left)
    intersection_top = max(node_top, group_top)
    intersection_right = min(node_right, group_right)
    intersection_bottom = min(node_bottom, group_bottom)
    if intersection_left < intersection_right and intersection_top < intersection_bottom:
        overlap_width = intersection_right - intersection_left
        overlap_height = intersection_bottom - intersection_top
        overlap_area = overlap_width * overlap_height
        return float(overlap_area)
    else:
        return 0.0


# --- Main Conversion Function ---
# Converts a ComfyUI workflow JSON into a Mermaid graph definition string.
def workflow_to_mermaid(workflow, config_param) -> str:
    clear_style_cache()

    # --- Configuration Values ---
    Graph_Direction = config_param.get('Default_Graph_Direction', 'TD').strip()
    default_connector = config_param.get('Default_Connector', '-->').strip()
    generate_comfyui_subgraphs = config_param.get('Generate_ComfyUI_Subgraphs', True)
    style_definitions = config_param.get('Style_Definitions', {})
    node_group_config = config_param.get('Node_Group', [])
    default_node_shape = config_param.get('Default_Node_Shape', 'rectangle')

    # --- Pre-process Group Information (Based on Node Type) ---
    node_type_to_group_names = {}
    for group_def in node_group_config:
        if isinstance(group_def, dict):
            group_name = group_def.get('group_name')
            nodes_in_group = group_def.get('nodes', [])
            if group_name and isinstance(nodes_in_group, list):
                for node_type in nodes_in_group:
                    if isinstance(node_type, str):
                        if node_type not in node_type_to_group_names:
                            node_type_to_group_names[node_type] = []
                        if group_name not in node_type_to_group_names[node_type]:
                            node_type_to_group_names[node_type].append(group_name)

    # Map node IDs to their type, title, display label, and config groups
    node_id_to_group_names = {}
    node_id_to_type = {}
    node_id_to_display_label = {}
    nodes = workflow.get('nodes', [])
    for node in nodes:
        node_id_num = node.get('id')
        node_type = node.get('type')
        node_title = node.get('title')
        display_label = node_title if node_title else (node_type if node_type else 'Unknown')
        if node_id_num is not None:
            node_id_to_display_label[node_id_num] = display_label
            if node_type:
                node_id_to_type[node_id_num] = node_type
                groups_for_node = node_type_to_group_names.get(node_type, [])
                if groups_for_node:
                    node_id_to_group_names[node_id_num] = groups_for_node

    # --- Mermaid Output Initialization ---
    graph_text = "graph " + Graph_Direction
    start_text = graph_text + '\n'
    start_text += "    %% Node Definitions (Label: Title or Type)"
    empty_text = "    "
    mermaid_list = []

    # Add default node style definition
    default_Node_Style_Key = config_param.get('Default_Node_Style', '').strip()
    default_Node_Style_Value = _resolve_style_alias(default_Node_Style_Key, style_definitions)
    adjusted_default_style = adjust_text_color_for_background(default_Node_Style_Value)

    if adjusted_default_style:
        node_default_text = empty_text + "classDef default " + adjusted_default_style + ";"
        mermaid_list.append(node_default_text)

    link_style_list = []
    node_style_list = []

    # --- Process Nodes ---
    for node in nodes:
        node_id_num = node.get('id')
        if node_id_num is None:
            print(f"Warning: Node without ID found, skipped. Node data: {node}")
            continue

        node_id = "N" + str(node_id_num).strip()
        display_label = node_id_to_display_label.get(node_id_num, 'Unknown')
        escaped_label = display_label.replace('"', '#quot;')
        node_type = node_id_to_type.get(node_id_num)

        style_and_shape_info = {"style": "", "shape": default_node_shape}
        if node_type:
            style_and_shape_info = get_node_style_and_shape(
                node_id_num, node_type, config_param, node_id_to_group_names, style_definitions
            )
        else:
            style_and_shape_info["style"] = adjusted_default_style  # Use default if no type

        node_shape_name = style_and_shape_info['shape']
        current_node_style = style_and_shape_info['style']
        shape_syntax = get_mermaid_shape_syntax(node_shape_name)

        nodetext = f'{empty_text}{node_id}{shape_syntax[0]}"{escaped_label}"{shape_syntax[1]}'
        mermaid_list.append(nodetext)

        if current_node_style:
            node_style_list.append({'nodeid': node_id, "style": current_node_style})

    # --- Process Links ---
    mermaid_list.append("    %% Connections")
    links = workflow.get('links', [])

    for i, link in enumerate(links):
        if not isinstance(link, list) or len(link) < 6:
            print(f"Warning: Malformed link found, skipped. Link data: {link}")
            continue

        link_id = link[0]
        start_node_id_num = link[1]
        # slot_origin = link[2] # Unused
        end_node_id_num = link[3]
        # slot_dest = link[4] # Unused
        link_data_type_raw = link[5]

        # Prepare link_data_type: uppercase string, or empty string if None/not string.
        if isinstance(link_data_type_raw, str):
            link_data_type = link_data_type_raw.upper()
        elif link_data_type_raw is not None:
            link_data_type = str(link_data_type_raw).upper()  # Convert to string and uppercase
        else:
            link_data_type = ""  # Default to empty string for None or other non-string types

        link_text_label = str(link_data_type_raw) if link_data_type_raw is not None else ""

        start_node_type = node_id_to_type.get(start_node_id_num)
        end_node_type = node_id_to_type.get(end_node_id_num)

        if start_node_id_num not in node_id_to_display_label or end_node_id_num not in node_id_to_display_label:
            print(
                f"Warning: Link {link_id} connects to unknown or skipped node ({start_node_id_num} -> {end_node_id_num}), skipping this link.")
            continue

        start_node_id = "N" + str(start_node_id_num).strip()
        end_node_id = "N" + str(end_node_id_num).strip()

        # Get link style, connector, and label visibility from mermaid_styles
        link_style_info = get_link_style(
            i, start_node_id_num, end_node_id_num,
            start_node_type, end_node_type,  # Can be None
            config_param, node_id_to_group_names, style_definitions,
            link_data_type=link_data_type  # Pass the processed data type
        )

        current_connector = link_style_info['connector']
        add_label = link_style_info['add_label']
        current_link_style_value = link_style_info['style']

        # Optional: Info if styling might be partial due to unknown node types
        # if start_node_type is None or end_node_type is None:
        #     print(f"Info: Link {link_id} (Data Type: {link_data_type}) involves unknown node types. Connector: {current_connector}, Style: '{current_link_style_value}', AddLabel: {add_label}")

        if current_connector not in LINK_LABEL_FORMATS:
            print(
                f"Warning: Connector '{current_connector}' for link {link_id} is invalid, using default '{default_connector}'.")
            current_connector = default_connector

        if current_link_style_value:
            link_style_list.append({"index": i, 'style': current_link_style_value})

        escaped_label = link_text_label.replace('"', '#quot;')
        if add_label and escaped_label:
            connector_format = LINK_LABEL_FORMATS.get(current_connector, "-- {} -->")  # Default format
            connector_text = connector_format.format(escaped_label)
        else:
            connector_text = current_connector

        linktext = f"{empty_text}{start_node_id} {connector_text} {end_node_id}"
        mermaid_list.append(linktext)

    # --- Process ComfyUI Groups (Subgraphs) ---
    group_assignments = {}
    comfy_groups = workflow.get('groups', [])
    if generate_comfyui_subgraphs and comfy_groups and nodes:
        for node in nodes:
            node_id_num = node.get('id')
            if node_id_num is None: continue
            node_size = node.get('size')
            nw, nh = None, None
            if isinstance(node_size, list) and len(node_size) >= 2:
                if all(isinstance(v, numbers.Number) for v in node_size[:2]):
                    nw, nh = node_size[0], node_size[1]
            elif isinstance(node_size, dict):
                sx_key = "0" if "0" in node_size else (0 if 0 in node_size else None)
                sy_key = "1" if "1" in node_size else (1 if 1 in node_size else None)
                if sx_key is not None and sy_key is not None:
                    _nw = node_size.get(sx_key)
                    _nh = node_size.get(sy_key)
                    if isinstance(_nw, numbers.Number) and isinstance(_nh, numbers.Number):
                        nw, nh = _nw, _nh
            if nw is None or nh is None or nw <= 0 or nh <= 0:
                node_area = 0.0
            else:
                node_area = float(nw * nh)

            best_group_index = -1
            max_overlap = -1.0
            for group_index, group in enumerate(comfy_groups):
                if not isinstance(group, dict): continue
                overlap = calculate_overlap_area(node, group)
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_group_index = group_index

            if best_group_index != -1 and node_area > 0:
                overlap_ratio = max_overlap / node_area
                if overlap_ratio >= 0.4:  # Threshold
                    if best_group_index not in group_assignments:
                        group_assignments[best_group_index] = []
                    group_assignments[best_group_index].append(node_id_num)

    # --- Generate Mermaid Subgraph Code from ComfyUI group assignments ---
    if group_assignments:
        mermaid_list.append("    %% ComfyUI Groups (Subgraphs)")
        sorted_group_indices = sorted(group_assignments.keys())
        for group_index in sorted_group_indices:
            assigned_node_ids = group_assignments[group_index]
            if 0 <= group_index < len(comfy_groups):
                group = comfy_groups[group_index]
                if not isinstance(group, dict): continue
                title = group.get('title', f'Group_{group_index + 1}')
                subgraph_title = title.strip()
                if not subgraph_title: subgraph_title = f'Group_{group_index + 1}'
                escaped_group_title = subgraph_title.replace('"', '#quot;')
                subtext = f'{empty_text}subgraph "{escaped_group_title}"'
                mermaid_list.append(subtext)
                for node_id_num in assigned_node_ids:
                    idtext = f"{empty_text}{empty_text}N{str(node_id_num).strip()}"
                    mermaid_list.append(idtext)
                mermaid_list.append(empty_text + "end")
            else:
                print(f"Warning: Invalid group_index found while generating ComfyUI groups: {group_index}")

    # --- Add Style Definitions ---
    if node_style_list or link_style_list:
        mermaid_list.append("    %% Styling (Based on Node Type/Group/Data Type)")  # Updated comment
        for nodestyle in node_style_list:
            node_id = nodestyle.get('nodeid')
            style = nodestyle.get('style')
            if node_id and style:
                styletext = f"{empty_text}style {node_id} {style}"
                mermaid_list.append(styletext)
        for linkstyle in link_style_list:
            index = linkstyle.get('index')
            style = linkstyle.get('style')
            if index is not None and style:  # Allow empty string style to be applied if explicitly set
                styletext = f"{empty_text}linkStyle {str(index).strip()} {style}"
                mermaid_list.append(styletext)

    # --- Combine Final Mermaid Code ---
    mermaid_code = start_text
    for mermaid_line in mermaid_list:
        mermaid_code += "\n" + mermaid_line
    return mermaid_code


# --- Main Execution Block (for standalone testing) ---
if __name__ == '__main__':
    # Re-import helpers if running as main, as they might be dummies otherwise
    # This is already handled by the try-except at the top for _resolve_style_alias etc.

    # Example: Provide a workflow file path for testing
    # Construct path relative to the script directory for testing
    script_dir_main = os.path.dirname(os.path.abspath(__file__))
    test_workflow_file_path = os.path.join(script_dir_main, "example_workflow.json")

    if not os.path.exists(test_workflow_file_path):
        print(f"Test workflow file not found: '{test_workflow_file_path}'. Create one or update path for testing.")
        dummy_workflow_data = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "title": "Load Image A", "pos": [0, 0], "size": [100, 50]},
                {"id": 2, "type": "CLIPTextEncode", "title": "Prompt", "pos": [0, 100], "size": [100, 50]},
                {"id": 3, "type": "KSampler", "title": "Sample", "pos": [200, 50], "size": [100, 100]}
            ],
            "links": [
                [1, 1, 0, 3, 0, "IMAGE"],
                [2, 2, 0, 3, 1, "CONDITIONING"],
                [3, 1, 0, 2, 0, "LATENT"]  # Example with a different type
            ],
            "groups": []
        }
        with open(test_workflow_file_path, 'w', encoding='utf-8') as f_dummy:
            json.dump(dummy_workflow_data, f_dummy, indent=2)
        print(f"Created a dummy workflow file: '{test_workflow_file_path}' for testing.")

    workflow_dict = None
    try:
        with open(test_workflow_file_path, 'r', encoding='utf-8') as f:
            workflow_dict = json.load(f)

        if workflow_dict and isinstance(workflow_dict, dict):
            print("JSON workflow file loaded successfully for testing.")
            # Use the global 'config' loaded earlier
            mermaid_code_output = workflow_to_mermaid(workflow_dict, config)
            # print("\n--- Generated Mermaid Code (for testing) ---")
            # print(mermaid_code_output)
            # print("--------------------------------------------\n")
            # Save to a file for easy viewing
            output_mermaid_file = os.path.join(script_dir_main, "test_output.mmd")
            with open(output_mermaid_file, 'w', encoding='utf-8') as f_out:
                f_out.write(mermaid_code_output)
            print(f"Standalone test finished. Mermaid code generated and saved to '{output_mermaid_file}'.")

        else:
            print(f"Error: Content of file '{test_workflow_file_path}' is not a valid JSON object (dictionary).")

    except FileNotFoundError:
        print(f"Error: Workflow file '{test_workflow_file_path}' not found.")
    except json.JSONDecodeError:
        print(f"Error: Could not parse file '{test_workflow_file_path}'. Please check if it is valid JSON format.")
    except Exception as e:
        print(f"An unknown error occurred while processing the workflow file: {e}")
        traceback.print_exc()

# Ensure these are available globally if mermaid_styles import failed and __main__ is run
# This is defensive coding, already handled by dummy functions at the top.
if 'adjust_text_color_for_background' not in globals():
    def adjust_text_color_for_background(s): return s
if '_resolve_style_alias' not in globals():
    def _resolve_style_alias(s, d): return s
