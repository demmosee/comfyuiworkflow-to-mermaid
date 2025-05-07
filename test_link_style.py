import json
import os

# Attempt to import helper from mermaid_styles.py
try:
    from mermaid_styles import _resolve_style_alias
except ImportError:
    print("ERROR: Could not import _resolve_style_alias from mermaid_styles.py.")
    print("Ensure mermaid_styles.py is in the same directory.")


    # Define a dummy if import fails, so the script can partially run for structure check
    def _resolve_style_alias(style_key_or_value, style_definitions):
        print(f"WARNING: Using dummy _resolve_style_alias. Style '{style_key_or_value}' will not be resolved.")
        return style_key_or_value

CONFIG_FILE = "Mermaid_config.json"


def load_json_file(file_path):
    """Loads a JSON file."""
    if not os.path.exists(file_path):
        print(f"Error: File not found - {file_path}")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {file_path}: {e}")
        return None
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None


def preprocess_workflow_data(workflow_data, config_data):
    """
    Extracts necessary information from workflow and config.
    Returns:
        nodes_map (dict): node_id -> {type, title, display_label}
        node_id_to_group_names (dict): node_id -> list of group names
    """
    nodes_map = {}
    node_id_to_type = {}
    for node_info in workflow_data.get('nodes', []):
        node_id = node_info.get('id')
        node_type = node_info.get('type')
        node_title = node_info.get('title')
        display_label = node_title if node_title else (node_type if node_type else f"Node_{node_id}")
        if node_id is not None:
            nodes_map[node_id] = {
                "type": node_type,
                "title": node_title,
                "display_label": display_label
            }
            if node_type:
                node_id_to_type[node_id] = node_type

    node_id_to_group_names = {}
    node_group_config = config_data.get('Node_Group', [])
    node_type_to_group_names = {}
    for group_def in node_group_config:
        if isinstance(group_def, dict):
            group_name = group_def.get('group_name')
            nodes_in_group = group_def.get('nodes', [])
            if group_name and isinstance(nodes_in_group, list):
                for nt in nodes_in_group:
                    if isinstance(nt, str):
                        if nt not in node_type_to_group_names:
                            node_type_to_group_names[nt] = []
                        if group_name not in node_type_to_group_names[nt]:
                            node_type_to_group_names[nt].append(group_name)

    for node_id, n_type in node_id_to_type.items():
        groups = node_type_to_group_names.get(n_type, [])
        if groups:
            node_id_to_group_names[node_id] = groups

    return nodes_map, node_id_to_group_names


def get_rule_findings(rule_config_dict):
    """Extracts style components from a rule dictionary."""
    return {
        "connector": rule_config_dict.get('connector'),
        "style": rule_config_dict.get('style'),
        "add_label": rule_config_dict.get('add_link_label')
    }


def print_findings(priority_name, findings_dict):
    """Prints the findings for a priority level."""
    print(f"  Priority: {priority_name}")
    if findings_dict:
        print(f"    Found: Connector='{findings_dict['connector']}', "
              f"Style='{findings_dict['style']}', "
              f"AddLabel='{findings_dict['add_label']}'")
    else:
        print("    No matching rule found or rule had no relevant settings.")


def apply_style_component(current_value, new_value_from_rule, is_set_flag):
    if new_value_from_rule is not None and not is_set_flag:
        return new_value_from_rule, True
    return current_value, is_set_flag


def test_link_style_lookup(link_info, config, nodes_map, node_id_to_group_names, style_definitions):
    """
    Tests link style lookup by checking each priority level.
    """
    start_node_id_num = link_info['start_node_id_num']
    end_node_id_num = link_info['end_node_id_num']
    link_data_type = link_info['link_data_type']

    start_node_details = nodes_map.get(start_node_id_num, {})
    end_node_details = nodes_map.get(end_node_id_num, {})
    start_node_type = start_node_details.get('type')
    end_node_type = end_node_details.get('type')

    start_node_groups = node_id_to_group_names.get(start_node_id_num, [])
    end_node_groups = node_id_to_group_names.get(end_node_id_num, [])

    print(f"\n--- Testing Link: {start_node_details.get('display_label', 'UnknownNode')} "
          f"-> {end_node_details.get('display_label', 'UnknownNode')} "
          f"(Type: {link_data_type}) ---")

    # Initialize final values with defaults
    final_connector = config.get('Default_Connector', '-->')
    final_style_key_or_value = ""  # Default is no specific style class
    final_add_label = config.get('Add_Link_Labels', True)

    connector_set, style_set, add_label_set = False, False, False

    all_findings_log = []

    # Priority 1: Link_Styles (Point-to-Point)
    priority_name = "1. Link_Styles (Precise start_node_type to end_node_type)"
    current_findings = None
    if start_node_type and end_node_type:
        for entry in config.get('Link_Styles', []):
            if isinstance(entry, dict) and \
                    entry.get('start_node_type') == start_node_type and \
                    entry.get('end_node_type') == end_node_type:
                current_findings = get_rule_findings(entry)
                break
    print_findings(priority_name, current_findings)
    all_findings_log.append({"name": priority_name, "findings": current_findings})
    if current_findings:
        final_connector, connector_set = apply_style_component(final_connector, current_findings['connector'],
                                                               connector_set)
        final_style_key_or_value, style_set = apply_style_component(final_style_key_or_value, current_findings['style'],
                                                                    style_set)
        final_add_label, add_label_set = apply_style_component(final_add_label, current_findings['add_label'],
                                                               add_label_set)

    # Priority 2: Link_Group_Styles (single_to_group, bidirectional)
    priority_name = "2. Link_Group_Styles (single_to_group, bidirectional)"
    current_findings = None
    for entry in config.get('Link_Group_Styles', []):
        if isinstance(entry, dict) and entry.get('type') == 'single_to_group':
            single_cfg = entry.get('single_node')
            group_cfg = entry.get('group_name')
            if (start_node_type == single_cfg and group_cfg in end_node_groups) or \
                    (end_node_type == single_cfg and group_cfg in start_node_groups):
                current_findings = get_rule_findings(entry)
                break
    print_findings(priority_name, current_findings)
    all_findings_log.append({"name": priority_name, "findings": current_findings})
    if current_findings:
        final_connector, connector_set = apply_style_component(final_connector, current_findings['connector'],
                                                               connector_set)
        final_style_key_or_value, style_set = apply_style_component(final_style_key_or_value, current_findings['style'],
                                                                    style_set)
        final_add_label, add_label_set = apply_style_component(final_add_label, current_findings['add_label'],
                                                               add_label_set)

    # Priority 3a: Link_Group_Styles (from_node)
    priority_name = "3a. Link_Group_Styles (from_node: single_node or group_name as start)"
    current_findings = None
    for entry in config.get('Link_Group_Styles', []):
        if isinstance(entry, dict) and entry.get('type') == 'from_node':
            match = False
            if start_node_type and entry.get('single_node') == start_node_type:
                match = True
            elif entry.get('group_name') and entry.get('group_name') in start_node_groups:
                match = True
            if match:
                current_findings = get_rule_findings(entry)
                break
    print_findings(priority_name, current_findings)
    all_findings_log.append({"name": priority_name, "findings": current_findings})
    if current_findings:
        final_connector, connector_set = apply_style_component(final_connector, current_findings['connector'],
                                                               connector_set)
        final_style_key_or_value, style_set = apply_style_component(final_style_key_or_value, current_findings['style'],
                                                                    style_set)
        final_add_label, add_label_set = apply_style_component(final_add_label, current_findings['add_label'],
                                                               add_label_set)

    # Priority 3b: Link_Group_Styles (to_node)
    priority_name = "3b. Link_Group_Styles (to_node: single_node or group_name as end)"
    current_findings = None
    for entry in config.get('Link_Group_Styles', []):
        if isinstance(entry, dict) and entry.get('type') == 'to_node':
            match = False
            if end_node_type and entry.get('single_node') == end_node_type:
                match = True
            elif entry.get('group_name') and entry.get('group_name') in end_node_groups:
                match = True
            if match:
                current_findings = get_rule_findings(entry)
                break
    print_findings(priority_name, current_findings)
    all_findings_log.append({"name": priority_name, "findings": current_findings})
    if current_findings:
        final_connector, connector_set = apply_style_component(final_connector, current_findings['connector'],
                                                               connector_set)
        final_style_key_or_value, style_set = apply_style_component(final_style_key_or_value, current_findings['style'],
                                                                    style_set)
        final_add_label, add_label_set = apply_style_component(final_add_label, current_findings['add_label'],
                                                               add_label_set)

    # Priority 4: Link_Group_Styles (group_to_group, bidirectional)
    priority_name = "4. Link_Group_Styles (group_to_group, bidirectional)"
    current_findings = None
    for entry in config.get('Link_Group_Styles', []):
        if isinstance(entry, dict) and entry.get('type') == 'group_to_group':
            g1_cfg, g2_cfg = entry.get('group_name_1'), entry.get('group_name_2')
            if g1_cfg and g2_cfg:
                if (g1_cfg in start_node_groups and g2_cfg in end_node_groups) or \
                        (g2_cfg in start_node_groups and g1_cfg in end_node_groups):
                    current_findings = get_rule_findings(entry)
                    break
    print_findings(priority_name, current_findings)
    all_findings_log.append({"name": priority_name, "findings": current_findings})
    if current_findings:
        final_connector, connector_set = apply_style_component(final_connector, current_findings['connector'],
                                                               connector_set)
        final_style_key_or_value, style_set = apply_style_component(final_style_key_or_value, current_findings['style'],
                                                                    style_set)
        final_add_label, add_label_set = apply_style_component(final_add_label, current_findings['add_label'],
                                                               add_label_set)

    # Priority 5: Data_Type_Link_Styles
    priority_name = "5. Data_Type_Link_Styles"
    current_findings = None
    if link_data_type is not None:
        for entry in config.get('Data_Type_Link_Styles', []):
            if isinstance(entry, dict) and entry.get('data_type') == str(
                    link_data_type):  # Ensure comparison with string
                current_findings = get_rule_findings(entry)
                break
    print_findings(priority_name, current_findings)
    all_findings_log.append({"name": priority_name, "findings": current_findings})
    if current_findings:
        final_connector, connector_set = apply_style_component(final_connector, current_findings['connector'],
                                                               connector_set)
        final_style_key_or_value, style_set = apply_style_component(final_style_key_or_value, current_findings['style'],
                                                                    style_set)
        final_add_label, add_label_set = apply_style_component(final_add_label, current_findings['add_label'],
                                                               add_label_set)

    # Final resolved style
    resolved_final_style = _resolve_style_alias(final_style_key_or_value, style_definitions)
    print("\n  --- Final Determined Style (after applying priorities) ---")
    print(f"    Connector: {final_connector}")
    print(f"    Style Key/Value: '{final_style_key_or_value}' -> Resolved: '{resolved_final_style}'")
    print(f"    Add Label: {final_add_label}")
    print("  --------------------------------------------------------")


def main():
    config_data = load_json_file(CONFIG_FILE)
    if not config_data:
        return

    style_definitions = config_data.get('Style_Definitions', {})

    workflow_file_path = input("Enter path to ComfyUI workflow JSON file (e.g., example_workflow.json): ").strip()
    workflow_data = load_json_file(workflow_file_path)
    if not workflow_data:
        return

    nodes_map, node_id_to_group_names = preprocess_workflow_data(workflow_data, config_data)

    links = workflow_data.get('links', [])
    if not links:
        print("No links found in the workflow.")
        return

    print("\nAvailable Links:")
    link_details_list = []
    for i, link_entry in enumerate(links):
        if not isinstance(link_entry, list) or len(link_entry) < 6:
            print(f"  Skipping malformed link entry: {link_entry}")
            link_details_list.append(None)  # Placeholder for index consistency
            continue

        _link_id, start_node_id, _origin_slot, end_node_id, _dest_slot, data_type_raw = link_entry[0:6]

        start_node_info = nodes_map.get(start_node_id, {"display_label": f"UnknownNodeID_{start_node_id}"})
        end_node_info = nodes_map.get(end_node_id, {"display_label": f"UnknownNodeID_{end_node_id}"})

        # Process link_data_type: uppercase string, or empty string if None/not string.
        if isinstance(data_type_raw, str):
            data_type = data_type_raw.upper()
        elif data_type_raw is not None:
            data_type = str(data_type_raw).upper()
        else:
            data_type = ""

        link_info_obj = {
            "index": i,
            "start_node_id_num": start_node_id,
            "end_node_id_num": end_node_id,
            "link_data_type": data_type,  # Use processed data_type
            "raw_data_type_label": str(data_type_raw) if data_type_raw is not None else ""
        }
        link_details_list.append(link_info_obj)

        print(
            f"  {i}: {start_node_info['display_label']} -> {end_node_info['display_label']} (Label: {link_info_obj['raw_data_type_label']})")

    while True:
        try:
            user_input = input("\nEnter link index to test (or 'q' to quit): ").strip()
            if user_input.lower() == 'q':
                break

            link_idx = int(user_input)
            if 0 <= link_idx < len(link_details_list):
                selected_link_info = link_details_list[link_idx]
                if selected_link_info:  # Check if it was a valid link
                    test_link_style_lookup(selected_link_info, config_data, nodes_map, node_id_to_group_names,
                                           style_definitions)
                else:
                    print(f"Link at index {link_idx} was malformed and cannot be tested.")
            else:
                print(f"Invalid index. Please enter a number between 0 and {len(links) - 1}.")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'.")
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
