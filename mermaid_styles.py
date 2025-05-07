
import re

try:
    import webcolors

    WEBCOLORS_AVAILABLE = True
except ImportError:
    WEBCOLORS_AVAILABLE = False

# --- Constants ---
CONTRAST_THRESHOLD = 4.5
DEFAULT_DARK_THEME_TEXT_COLOR_RGB = (255, 255, 255)  # White

# --- Style Definitions Cache ---
style_cache = {}

# --- Mermaid Shape Syntax Mapping ---
MERMAID_SHAPE_SYNTAX = {
    "rectangle": ('[', ']'), "round": ('(', ')'),
    "stadium": ('([', '])'), "subroutine": ('[[', ']]'),
    "cylinder": ('[(', ')]'), "circle": ('((', '))'),
    "rhombus": ('{', '}'), "diamond": ('{', '}'),
    "hexagon": ('{{', '}}'), "parallelogram": ('[/', '/]'),
    "parallelogram_alt": ('[\\', '\\]'), "trapezoid": ('[/', '\\]'),
    "trapezoid_alt": ('[\\', '/]'), "double_circle": ('(((', ')))'),
    "database": ('[(', ')]'),  # common alias for cylinder
}
DEFAULT_SHAPE_SYNTAX = ('[', ']')


def get_mermaid_shape_syntax(shape_name):
    if not isinstance(shape_name, str): return DEFAULT_SHAPE_SYNTAX
    return MERMAID_SHAPE_SYNTAX.get(shape_name.strip().lower(), DEFAULT_SHAPE_SYNTAX)


def parse_color(color_string):
    if not color_string or not isinstance(color_string, str): return None
    color_string = color_string.strip().lower()
    if color_string.startswith('#'):
        try:
            return webcolors.hex_to_rgb(color_string)
        except (ValueError, AttributeError):  # AttributeError for webcolors not found
            if len(color_string) == 4:  # Try to expand 3-char hex
                try:
                    norm_hex = '#' + color_string[1] * 2 + color_string[2] * 2 + color_string[3] * 2
                    return webcolors.hex_to_rgb(norm_hex)
                except (ValueError, AttributeError):
                    return None
            return None
    if color_string.startswith('rgb(') and color_string.endswith(')'):
        try:
            parts = color_string[4:-1].split(',')
            if len(parts) == 3:
                r, g, b = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
                if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255: return (r, g, b)
            return None
        except (ValueError, IndexError):
            return None
    if WEBCOLORS_AVAILABLE:
        try:
            if "grey" in color_string: color_string = color_string.replace("grey", "gray")  # common alternative
            return webcolors.name_to_rgb(color_string)
        except ValueError:
            return None
    else:  # Basic fallback if webcolors is not available
        basic_colors = {
            "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0),
            "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
            "cyan": (0, 255, 255), "magenta": (255, 0, 255),
            "lightgrey": (211, 211, 211), "lightgray": (211, 211, 211),
            "grey": (128, 128, 128), "gray": (128, 128, 128),
            "darkgrey": (169, 169, 169), "darkgray": (169, 169, 169)
        }
        return basic_colors.get(color_string, None)
    return None


def _calculate_relative_luminance(rgb):
    if not isinstance(rgb, (tuple, list)) or len(rgb) != 3: return 0.0
    r, g, b = rgb
    rgb_normalized = []
    for val in [r, g, b]:
        v = val / 255.0
        if v <= 0.03928:
            rgb_normalized.append(v / 12.92)
        else:
            rgb_normalized.append(((v + 0.055) / 1.055) ** 2.4)
    R, G, B_ = rgb_normalized
    return 0.2126 * R + 0.7152 * G + 0.0722 * B_


def calculate_contrast_ratio(rgb1, rgb2):
    try:
        lum1 = _calculate_relative_luminance(rgb1)
        lum2 = _calculate_relative_luminance(rgb2)
        return (max(lum1, lum2) + 0.05) / (min(lum1, lum2) + 0.05)
    except Exception:
        return 1.0


def adjust_text_color_for_background(style_string):
    if not style_string or not isinstance(style_string, str): return style_string
    normalized_style = ','.join(part.strip() for part in style_string.split(',') if part.strip())
    if re.search(r'(?:^|,)\s*color\s*:', normalized_style, re.IGNORECASE): return normalized_style
    fill_color_value = None
    for prop in (p.strip() for p in normalized_style.split(',') if p.strip()):
        if prop.lower().startswith('fill:'):
            try:
                fill_color_value = prop.split(':', 1)[1].strip(); break
            except IndexError:
                continue
    if not fill_color_value: return normalized_style
    bg_rgb = parse_color(fill_color_value)
    if bg_rgb is None: return normalized_style
    contrast = calculate_contrast_ratio(bg_rgb, DEFAULT_DARK_THEME_TEXT_COLOR_RGB)
    if contrast < CONTRAST_THRESHOLD:
        return normalized_style + ",color:#000"  # Add black text for light backgrounds
    return normalized_style


def _resolve_style_alias(style_key_or_value, style_definitions):
    if not style_key_or_value: return ""  # Handle empty or None input gracefully
    cache_key = (style_key_or_value,)  # Make it a tuple for dict key
    if cache_key in style_cache: return style_cache[cache_key]

    resolved_style = style_key_or_value
    # Heuristic: if it doesn't contain typical CSS characters, it might be a key
    is_likely_key = isinstance(style_key_or_value, str) and \
                    all(c not in style_key_or_value for c in ':;,')

    if is_likely_key:
        resolved_style = style_definitions.get(style_key_or_value, style_key_or_value)

    # Normalize the resolved style (string or the original value if not found/not string)
    if isinstance(resolved_style, str) and resolved_style.strip():
        resolved_style = resolved_style.strip().replace(';', ',')  # Replace semicolons with commas
        # Consolidate multiple commas and remove leading/trailing ones
        resolved_style = ','.join(part.strip() for part in resolved_style.split(',') if part.strip())

    style_cache[cache_key] = resolved_style
    return resolved_style


def get_node_style_and_shape(node_id_num, node_type, config, node_id_to_group_names, style_definitions):
    # Defaults
    default_shape_val = config.get('Default_Node_Shape', 'rectangle').strip().lower()
    default_style_key_val = config.get('Default_Node_Style', '')

    final_shape = default_shape_val
    final_style_key_or_value = default_style_key_val

    shape_found = False
    style_found = False

    # Priority 1: Precise Node Styles (Node_Styles)
    node_styles_config = config.get('Node_Styles', {})
    if isinstance(node_styles_config, dict) and node_type in node_styles_config:
        node_specific_config = node_styles_config[node_type]

        if isinstance(node_specific_config, str):  # Assumed to be style only
            if node_specific_config is not None:  # Allow explicit empty string
                final_style_key_or_value = node_specific_config
                style_found = True
        elif isinstance(node_specific_config, dict):
            if 'style' in node_specific_config:  # Allows explicit empty string
                final_style_key_or_value = node_specific_config['style']
                style_found = True
            if 'shape' in node_specific_config and node_specific_config['shape']:  # Ensure shape is not empty string
                final_shape = node_specific_config['shape'].strip().lower()
                shape_found = True

    # Priority 2: Group Node Styles (Node_Group_Styles)
    # Only apply if corresponding component (style or shape) was not found in Priority 1
    if not (style_found and shape_found):
        node_group_styles_config = config.get('Node_Group_Styles', [])
        # Ensure node_id_to_group_names provides a list, even if empty
        node_groups_for_current_node = node_id_to_group_names.get(node_id_num, [])

        if isinstance(node_group_styles_config, list) and node_groups_for_current_node:
            for group_style_entry in node_group_styles_config:
                if not isinstance(group_style_entry, dict): continue
                group_name_in_config = group_style_entry.get('group_name')

                if group_name_in_config in node_groups_for_current_node:
                    if not style_found and 'style' in group_style_entry:
                        final_style_key_or_value = group_style_entry['style']
                        style_found = True
                    if not shape_found and 'shape' in group_style_entry and group_style_entry['shape']:
                        final_shape = group_style_entry['shape'].strip().lower()
                        shape_found = True

                    if style_found and shape_found:  # Both components found from this or higher priority
                        break

                        # Priority 3: Defaults are already set as initial values for final_shape and final_style_key_or_value

    resolved_style = _resolve_style_alias(final_style_key_or_value, style_definitions)
    adjusted_style = adjust_text_color_for_background(resolved_style)

    return {"style": adjusted_style, "shape": final_shape}


def _apply_style_component(current_value, new_value_from_rule, is_set_flag):
    """
    Helper to update a style component (connector, style, add_label) if it's
    defined in the rule and not already set by a higher priority rule.
    Returns the (potentially updated) value and the updated is_set_flag.
    """
    if new_value_from_rule is not None and not is_set_flag:
        return new_value_from_rule, True
    return current_value, is_set_flag


def get_link_style(link_index, start_node_id_num, end_node_id_num,
                   start_node_type, end_node_type,
                   config, node_id_to_group_names, style_definitions,
                   link_data_type=None):
    # Default values from config
    final_connector = config.get('Default_Connector', '-->').strip()
    final_add_label = config.get('Add_Link_Labels', True)
    final_style_key_or_value = ""  # Default link style (resolved from empty string)

    # Flags to track if a component has been set
    connector_set = False
    style_set = False
    add_label_set = False

    # Helper to process a rule dictionary and update components
    def process_rule(rule_config_dict):
        nonlocal final_connector, connector_set
        nonlocal final_style_key_or_value, style_set
        nonlocal final_add_label, add_label_set

        # Check and apply 'connector'
        final_connector, connector_set = _apply_style_component(
            final_connector, rule_config_dict.get('connector'), connector_set
        )
        # Check and apply 'style'
        final_style_key_or_value, style_set = _apply_style_component(
            final_style_key_or_value, rule_config_dict.get('style'), style_set
        )
        # Check and apply 'add_link_label'
        final_add_label, add_label_set = _apply_style_component(
            final_add_label, rule_config_dict.get('add_link_label'), add_label_set
        )
        # Return True if all components are now set, allowing early exit from loops
        return connector_set and style_set and add_label_set

    # --- Start of Priority Checks ---
    all_components_set = lambda: connector_set and style_set and add_label_set

    # Priority 1: Individual Link_Styles (start_node_type to end_node_type)
    if not all_components_set() and start_node_type and end_node_type:
        link_styles_config = config.get('Link_Styles', [])
        if isinstance(link_styles_config, list):
            for entry in link_styles_config:
                if isinstance(entry, dict) and \
                        entry.get('start_node_type') == start_node_type and \
                        entry.get('end_node_type') == end_node_type:
                    if process_rule(entry): break

                    # Prepare group info for subsequent checks
    start_node_groups = node_id_to_group_names.get(start_node_id_num, [])
    end_node_groups = node_id_to_group_names.get(end_node_id_num, [])
    link_group_styles_config = config.get('Link_Group_Styles', [])

    # Priority 2: single_to_group (bidirectional)
    if not all_components_set() and isinstance(link_group_styles_config, list):
        for entry in link_group_styles_config:
            if not isinstance(entry, dict) or entry.get('type') != 'single_to_group':
                continue

            single_node_cfg = entry.get('single_node')
            group_name_cfg = entry.get('group_name')

            # Check standard direction: single_node (start) -> group_name (end)
            if start_node_type == single_node_cfg and group_name_cfg in end_node_groups:
                if process_rule(entry): break
            # Check reverse direction: group_name (start) -> single_node (end)
            elif end_node_type == single_node_cfg and group_name_cfg in start_node_groups:
                if process_rule(entry): break

            if all_components_set(): break

    # Priority 3a: from_node (single_node or group_name as start)
    if not all_components_set() and isinstance(link_group_styles_config, list):
        for entry in link_group_styles_config:
            if not isinstance(entry, dict) or entry.get('type') != 'from_node':
                continue

            match = False
            if start_node_type and entry.get('single_node') == start_node_type:
                match = True
            # Check if the rule's group_name is one of the start_node's groups
            elif entry.get('group_name') and entry.get('group_name') in start_node_groups:
                match = True

            if match:
                if process_rule(entry): break
            if all_components_set(): break

    # Priority 3b: to_node (single_node or group_name as end)
    if not all_components_set() and isinstance(link_group_styles_config, list):
        for entry in link_group_styles_config:
            if not isinstance(entry, dict) or entry.get('type') != 'to_node':
                continue

            match = False
            if end_node_type and entry.get('single_node') == end_node_type:
                match = True
            # Check if the rule's group_name is one of the end_node's groups
            elif entry.get('group_name') and entry.get('group_name') in end_node_groups:
                match = True

            if match:
                if process_rule(entry): break
            if all_components_set(): break

    # Priority 4: group_to_group (bidirectional)
    if not all_components_set() and isinstance(link_group_styles_config, list):
        for entry in link_group_styles_config:
            if not isinstance(entry, dict) or entry.get('type') != 'group_to_group':
                continue

            g1_cfg = entry.get('group_name_1')
            g2_cfg = entry.get('group_name_2')

            if not (g1_cfg and g2_cfg): continue  # Both group names must be defined in rule

            # Check standard direction: g1_cfg (start) -> g2_cfg (end)
            if g1_cfg in start_node_groups and g2_cfg in end_node_groups:
                if process_rule(entry): break
            # Check reverse direction: g2_cfg (start) -> g1_cfg (end)
            elif g2_cfg in start_node_groups and g1_cfg in end_node_groups:  # Note: g1_cfg and g2_cfg are from the rule
                if process_rule(entry): break

            if all_components_set(): break

    # Priority 5: Data_Type_Link_Styles
    if not all_components_set() and link_data_type is not None:
        data_type_link_styles_config = config.get('Data_Type_Link_Styles', [])
        if isinstance(data_type_link_styles_config, list):
            for entry in data_type_link_styles_config:
                if not isinstance(entry, dict): continue

                config_dt = entry.get('data_type')
                # Ensure link_data_type is compared as string if config_dt is string
                if isinstance(config_dt, str) and config_dt == str(link_data_type):
                    if process_rule(entry): break
                    # No early exit here as it's the last rule-based source before defaults are finalized

    # Resolve the final style alias for the link style string
    resolved_style = _resolve_style_alias(final_style_key_or_value, style_definitions)

    return {'connector': final_connector, 'style': resolved_style, 'add_label': final_add_label}


def clear_style_cache():
    global style_cache
    style_cache = {}
