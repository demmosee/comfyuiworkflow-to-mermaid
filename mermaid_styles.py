# mermaid_styles.py

import re
try:
    import webcolors

    WEBCOLORS_AVAILABLE = True
except ImportError:
    # print("Warning: 'webcolors' library not found. Color name resolution and advanced color parsing will be limited. Run 'pip install webcolors'")
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
    "database": ('[(', ')]'),
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
        except (ValueError, AttributeError):
            if len(color_string) == 4:
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
            if "grey" in color_string: color_string = color_string.replace("grey", "gray")
            return webcolors.name_to_rgb(color_string)
        except ValueError:
            return None
    else:
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
        return normalized_style + ",color:#000"
    return normalized_style


def _resolve_style_alias(style_key_or_value, style_definitions):
    if not style_key_or_value: return ""
    cache_key = (style_key_or_value,)
    if cache_key in style_cache: return style_cache[cache_key]
    resolved_style = style_key_or_value
    is_likely_key = isinstance(style_key_or_value, str) and \
                    all(c not in style_key_or_value for c in ':;,')
    if is_likely_key:
        resolved_style = style_definitions.get(style_key_or_value, style_key_or_value)
    if isinstance(resolved_style, str) and resolved_style.strip():
        resolved_style = resolved_style.strip().replace(';', ',')
        resolved_style = ','.join(part.strip() for part in resolved_style.split(',') if part.strip())
    style_cache[cache_key] = resolved_style
    return resolved_style


def get_node_style_and_shape(node_id_num, node_type, config, node_id_to_group_names, style_definitions):
    default_shape = config.get('Default_Node_Shape', 'rectangle').strip().lower()
    default_style_key = config.get('Default_Node_Style', '')
    final_shape = default_shape
    final_style_key_or_value = default_style_key
    found_config_source = None
    node_styles_config = config.get('Node_Styles', {})
    if isinstance(node_styles_config, dict) and node_type in node_styles_config:
        node_specific_config = node_styles_config[node_type]
        if isinstance(node_specific_config, dict):
            if 'style' in node_specific_config or 'shape' in node_specific_config:
                found_config_source = node_specific_config
        elif isinstance(node_specific_config, str):
            found_config_source = {'style': node_specific_config}
    if not found_config_source or \
            (isinstance(found_config_source, dict) and \
             ('style' not in found_config_source or 'shape' not in found_config_source)):
        node_group_styles_config = config.get('Node_Group_Styles', [])
        node_groups_for_current_node = node_id_to_group_names.get(node_id_num, [])
        if isinstance(node_group_styles_config, list) and node_groups_for_current_node:
            for group_style_entry in node_group_styles_config:
                if not isinstance(group_style_entry, dict): continue
                group_name_in_config = group_style_entry.get('group_name')
                if group_name_in_config in node_groups_for_current_node:
                    if 'style' in group_style_entry or 'shape' in group_style_entry:
                        if not found_config_source:
                            found_config_source = group_style_entry.copy()
                        else:
                            if 'style' not in found_config_source and 'style' in group_style_entry:
                                found_config_source['style'] = group_style_entry['style']
                            if 'shape' not in found_config_source and 'shape' in group_style_entry:
                                found_config_source['shape'] = group_style_entry['shape']
                        if isinstance(found_config_source, dict) and \
                                'style' in found_config_source and 'shape' in found_config_source:
                            break
    if found_config_source and isinstance(found_config_source, dict):
        style_from_config = found_config_source.get('style')
        if style_from_config is not None: final_style_key_or_value = style_from_config
        shape_from_config = found_config_source.get('shape')
        if isinstance(shape_from_config, str) and shape_from_config.strip():
            final_shape = shape_from_config.strip().lower()
    resolved_style = _resolve_style_alias(final_style_key_or_value, style_definitions)
    adjusted_style = adjust_text_color_for_background(resolved_style)
    return {"style": adjusted_style, "shape": final_shape}


def get_link_style(link_index, start_node_id_num, end_node_id_num,
                   start_node_type, end_node_type,  # These can be None
                   config, node_id_to_group_names, style_definitions,
                   link_data_type=None):
    default_connector = config.get('Default_Connector', '-->').strip()
    default_add_label = config.get('Add_Link_Labels', True)
    default_style_key = ""

    final_connector = default_connector
    final_add_label = default_add_label
    final_style_key_or_value = default_style_key

    style_set_by_priority_rule = False
    add_label_set_by_priority_rule = False  # MODIFIED: New flag for add_link_label priority
    found_link_config = None

    # Priority 1: Individual Link_Styles
    if start_node_type and end_node_type:
        link_styles_config = config.get('Link_Styles', [])
        if isinstance(link_styles_config, list):
            for entry in link_styles_config:
                if isinstance(entry, dict) and \
                        entry.get('start_node_type') == start_node_type and \
                        entry.get('end_node_type') == end_node_type:
                    found_link_config = entry
                    break

    # Priority 2-4: Link_Group_Styles
    if not found_link_config:
        link_group_styles_config = config.get('Link_Group_Styles', [])
        if isinstance(link_group_styles_config, list):
            start_node_groups = node_id_to_group_names.get(start_node_id_num, [])
            end_node_groups = node_id_to_group_names.get(end_node_id_num, [])

            # Priority 2: single_to_group
            if start_node_type:
                for entry in link_group_styles_config:
                    if isinstance(entry, dict) and entry.get('type') == 'single_to_group':
                        if entry.get('single_node') == start_node_type and \
                                entry.get('group_name') in end_node_groups:
                            found_link_config = entry;
                            break
            # Priority 3a: from_node
            if not found_link_config:
                for entry in link_group_styles_config:
                    if isinstance(entry, dict) and entry.get('type') == 'from_node':
                        match = False
                        if start_node_type and entry.get('single_node') == start_node_type:
                            match = True
                        elif entry.get('group_name') in start_node_groups:
                            match = True
                        if match: found_link_config = entry; break
            # Priority 3b: to_node
            if not found_link_config:
                for entry in link_group_styles_config:
                    if isinstance(entry, dict) and entry.get('type') == 'to_node':
                        match = False
                        if end_node_type and entry.get('single_node') == end_node_type:
                            match = True
                        elif entry.get('group_name') in end_node_groups:
                            match = True
                        if match: found_link_config = entry; break
            # Priority 4: group_to_group
            if not found_link_config:
                for entry in link_group_styles_config:
                    if isinstance(entry, dict) and entry.get('type') == 'group_to_group':
                        g1, g2 = entry.get('group_name_1'), entry.get('group_name_2')
                        if g1 and g2 and g1 in start_node_groups and g2 in end_node_groups:
                            found_link_config = entry;
                            break

    # Process found_link_config from Link_Styles or Link_Group_Styles
    if found_link_config and isinstance(found_link_config, dict):
        final_connector = found_link_config.get('connector', default_connector).strip()

        style_key_from_config = found_link_config.get('style')
        if style_key_from_config is not None:  # Allows explicit empty string for "no style"
            final_style_key_or_value = style_key_from_config
            style_set_by_priority_rule = True

        add_label_from_config = found_link_config.get('add_link_label')
        if add_label_from_config is not None:  # True or False
            final_add_label = add_label_from_config
            add_label_set_by_priority_rule = True  # MODIFIED: Mark that add_label was set

    # Priority 5 (Lowest for style and add_link_label): Data_Type_Link_Styles
    # This section applies if style or add_label hasn't been set by a higher priority rule.
    if link_data_type is not None:  # link_data_type is expected to be a string
        data_type_link_styles_config = config.get('Data_Type_Link_Styles', [])
        if isinstance(data_type_link_styles_config, list):
            for entry in data_type_link_styles_config:
                config_dt = entry.get('data_type')
                if isinstance(entry, dict) and isinstance(config_dt, str) and config_dt == link_data_type:
                    # Apply style from data type if not already set by higher priority
                    if not style_set_by_priority_rule:
                        style_from_data_type = entry.get('style')
                        if style_from_data_type is not None:
                            final_style_key_or_value = style_from_data_type

                    # MODIFIED: Apply add_link_label from data type if not already set by higher priority
                    if not add_label_set_by_priority_rule:
                        add_label_from_data_type = entry.get('add_link_label')
                        if add_label_from_data_type is not None:  # Check for explicit True/False
                            final_add_label = add_label_from_data_type
                    break  # Found matching data type, processed both style and add_label if applicable

    resolved_style = _resolve_style_alias(final_style_key_or_value, style_definitions)
    return {'connector': final_connector, 'style': resolved_style, 'add_label': final_add_label}


def clear_style_cache():
    global style_cache
    style_cache = {}
