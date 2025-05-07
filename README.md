# comfyuiworkflow-to-mermaid
Converts ComfyUI workflows into clear Mermaid diagrams. Features a WebUI for one-click conversion of .json/PNG workflow files with direct diagram rendering, zoom, and pan. Supports extensive custom styling for nodes, groups, and links via flexible strategies. Includes automatic dark mode adaptation for diagrams.

Turning some seemingly messy ComfyUI workflows, like this:
![image](https://github.com/user-attachments/assets/2a5960e1-c8fe-4c99-9027-0e1c31df6fc2)
Into clear and simple mermaid charts like this:
![image](https://github.com/user-attachments/assets/d72edaa4-15c2-498b-9d55-f0e026e3f0d7)

Key Features:
1. Convert any ComfyUI workflow (.json/.png) to Mermaid and display it on the web UI.
2. Freely choose default Mermaid styles, node styles, and connection styles.
3. Freely change the display style of the workflow in the Mermaid chart through multiple built-in strategies.
4. Supports detecting workflow groups and supports dark mode.

Getting Started:
Download the latest release package, open wf2mermaid.exe, drag the comfyuiworkflow json into the webui interface to display the workflow's mermaid chart.

## Configuring Mermaid Styles (`Mermaid_config.json`)
The appearance of your generated Mermaid diagrams can be extensively customized using the `Mermaid_config.json` file located in the same directory as the script. If this file is not found or is invalid, internal default settings will be used.
This guide explains how to adjust different Mermaid styles, focusing on the priority system for node and link styling.
### 1. General Configuration
These top-level settings control global aspects of the diagram:
*   `Default_Graph_Direction`: Sets the overall layout direction (e.g., "TD" for Top-Down, "LR" for Left-to-Right).
    *   Example: `"Default_Graph_Direction": "LR"`
*   `Default_Connector`: The default arrow/line style used for links if no other specific style applies.
    *   Example: `"Default_Connector": "-->"`
*   `Default_Node_Style`: A global default style applied to all nodes if no other specific or group style matches. Can be a direct CSS string or a key from `Style_Definitions`.
    *   Example: `"Default_Node_Style": "fill:#eee,stroke:#666"`
*   `Default_Node_Shape`: The default shape for nodes (e.g., "rectangle", "round", "stadium").
    *   Example: `"Default_Node_Shape": "rectangle"`
*   `Add_Link_Labels`: A boolean (`true` or `false`) to globally enable or disable labels (usually data types) on links. This can be overridden by more specific link style rules.
    *   Example: `"Add_Link_Labels": true`
*   `Generate_ComfyUI_Subgraphs`: A boolean (`true` or `false`) to enable or disable the generation of subgraphs based on ComfyUI's native groups.
    *   Example: `"Generate_ComfyUI_Subgraphs": true`
*   `App_Port`: (For the web UI) The port number the local web server will run on.
    *   Example: `"App_Port": 5567`
### 2. Style Definitions (`Style_Definitions`)
This section allows you to define named style snippets (aliases) that can be reused across various node and link style configurations. This is highly recommended for consistency and easier management.
*   Each key is a style alias (e.g., "loaderstyle", "importantlink").
*   The value is a Mermaid-compatible CSS string (e.g., "fill:#ccf,stroke:#555,stroke-width:2px").
```json
"Style_Definitions": {
  "loaderstyle": "fill:#ccf,stroke:#555,stroke-width:2px",
  "samplerStyle": "fill:#d8bfd8,stroke:#663399,stroke-width:2px",
  "imagestyle": "fill:#e0ffff,stroke:blue",
  "importantlink": "stroke:red,stroke-width:3px",
  "defaultfill": "fill:#eee,stroke:#666"
}

Note on Colors & Contrast: The script automatically attempts to adjust text color (to black or white) for better contrast if a fill color is specified in a node's style. This helps ensure readability, especially with Mermaid's default dark theme.

3. Node Group Definitions (Node_Group)
Before diving into node group styling, you need to define your node groups. This section maps specific ComfyUI node types to custom group names. These group names are then used in Node_Group_Styles and Link_Group_Styles.

Node_Group is an array of group definition objects.
Each object has:
group_name: A custom name for your group (e.g., "vae_group").
nodes: An array of ComfyUI node type strings (e.g., "VAEDecode", "VAEEncode") that belong to this group.
<JSON>
"Node_Group": [
  {
    "group_name": "checkpointloader_group",
    "nodes": ["CheckpointLoaderSimple", "CheckpointLoader"]
  },
  {
    "group_name": "vae_group",
    "nodes": ["VAEDecode", "VAEEncode", "VAELoader"]
  }
]
4. Node Styling Priority
Node styles (both appearance and shape) are determined with the following priority (higher priority overrides lower):

Precise Node Type Style (Node_Styles): Most specific.
Node Group Style (Node_Group_Styles): Applies if the node belongs to a defined group.
Default Node Style (Default_Node_Style & Default_Node_Shape): Fallback.
For each setting, you can define style (CSS string or alias from Style_Definitions) and shape (Mermaid shape name). If a parameter is not specified at a higher priority level, the value from a lower priority level (or default) will be used for that specific parameter. For example, a Node_Styles entry might only define a shape, inheriting its style from a group or default.

4.1. Priority 1: Precise Node Type Style (Node_Styles)
Styles defined here apply to specific ComfyUI node types.

Node_Styles is an object where:
Keys are ComfyUI node type strings (e.g., "LoadImage", "KSampler").
Values are objects containing style and/or shape.
If the value is just a string, it's assumed to be the style.
Example:
Make all "LoadImage" nodes use imagestyle and "subroutine" shape. Make "PreviewImage" nodes have a specific fill/stroke and "round" shape. "Reroute" nodes only have their shape specified, inheriting style from lower priorities.

<JSON>
"Style_Definitions": {
  "imagestyle": "fill:#e0ffff,stroke:blue"
},
"Node_Styles": {
  "LoadImage": {
    "style": "imagestyle",
    "shape": "subroutine"
  },
  "PreviewImage": {
    "style": "fill:#cfc,stroke:green,stroke-width:2px",
    "shape": "round"
  },
  "Reroute": {
    "shape": "circle" // Style will come from group or default
  }
}

If a "LoadImage" node exists, it will use imagestyle and subroutine shape, ignoring group and default styles for these properties.

4.2. Priority 2: Node Group Style (Node_Group_Styles)
Styles defined here apply to all nodes belonging to a group defined in Node_Group.

Node_Group_Styles is an array of objects.
Each object has group_name (must match a name from Node_Group), style, and/or shape.
Example:
Nodes in "vae_group" (e.g., "VAEDecode", "VAEEncode") will use vaeStyle and "hexagon" shape, unless overridden by a Node_Styles entry for that specific node type.

<JSON>
"Style_Definitions": {
  "vaeStyle": "fill:#ffe0e0,stroke:red,stroke-width:2px"
},
"Node_Group": [
  { "group_name": "vae_group", "nodes": ["VAEDecode", "VAEEncode"] }
],
"Node_Group_Styles": [
  {
    "group_name": "vae_group",
    "style": "vaeStyle",
    "shape": "hexagon"
  }
]
If a "VAEDecode" node exists and is not specifically styled in Node_Styles, it will get vaeStyle and "hexagon" shape.

4.3. Priority 3: Default Node Style & Shape
These are the global fallbacks if no other style or shape is applied.

Default_Node_Style: A style string or alias.
Default_Node_Shape: A shape name.
Example:

<JSON>
"Style_Definitions": {
  "defaultfill": "fill:#eee,stroke:#666"
},
"Default_Node_Style": "defaultfill",
"Default_Node_Shape": "rectangle"
Any node not covered by Node_Styles or Node_Group_Styles will use defaultfill and "rectangle" shape.

5. Link Styling Priority
Link styles (connector type, CSS style, and label visibility) are determined with the following priority (higher priority overrides lower):

Precise Point-to-Point (Link_Styles): Based on start_node_type to end_node_type.
Point-to-Group / Group-to-Point (Link_Group_Styles with type: "single_to_group"): Based on a specific single_node (type) to/from a group_name. Matches bidirectionally.
From Node/Group (Link_Group_Styles with type: "from_node") / To Node/Group (Link_Group_Styles with type: "to_node"):
from_node: Styles links originating from a specific node type or any node within a specified group.
to_node: Styles links ending at a specific node type or any node within a specified group.
Group-to-Group (Link_Group_Styles with type: "group_to_group"): Based on group_name_1 to group_name_2. Matches bidirectionally.
Data Type (Data_Type_Link_Styles): Based on the data type of the link (e.g., "IMAGE", "MODEL").
Default Link Settings (Default_Connector, Add_Link_Labels): Fallback.
For each rule, you can define connector (e.g., "-->", "-.->"), style (CSS string or alias), and add_link_label (boolean). If a parameter is not specified in a rule, its value will be inherited from a lower priority rule or the default.

5.1. Priority 1: Precise Point-to-Point (Link_Styles)
Styles links between specific start and end node types.

Link_Styles is an array of objects.
Each object has start_node_type, end_node_type, and optionally connector, style, add_link_label.
Example:
A link from "CheckpointLoaderSimple" to "VAEEncode" will use a dash-dot arrow, lightredlink style, and show its label.

<JSON>
"Style_Definitions": {
  "lightredlink": "stroke:#dc3545,stroke-width:2px"
},
"Link_Styles": [
  {
    "start_node_type": "CheckpointLoaderSimple",
    "end_node_type": "VAEEncode",
    "connector": "-.->",
    "style": "lightredlink",
    "add_link_label": true
  }
]
5.2. Priority 2: Point-to-Group / Group-to-Point (Link_Group_Styles, type: "single_to_group")
Styles links between a specific node type and any node in a specified group. This rule is bidirectional.

In Link_Group_Styles array.
Object has type: "single_to_group", single_node (node type), group_name, and optionally connector, style, add_link_label.
Example:
Any link between a "CheckpointLoaderSimple" node and any node in "vae_group" (e.g., "VAEDecode") will use importantlink style. This applies if "CheckpointLoaderSimple" is the start and "vae_group" member is the end, OR if "vae_group" member is the start and "CheckpointLoaderSimple" is the end.

<JSON>
"Style_Definitions": {
  "importantlink": "stroke:red,stroke-width:3px"
},
"Node_Group": [
  { "group_name": "vae_group", "nodes": ["VAEDecode", "VAEEncode"] }
],
"Link_Group_Styles": [
  {
    "type": "single_to_group",
    "single_node": "CheckpointLoaderSimple", // This is a node type
    "group_name": "vae_group",
    "style": "importantlink"
    // Connector and add_link_label will be inherited
  }
]

5.3. Priority 3: From/To Node/Group (Link_Group_Styles, type: "from_node" or type: "to_node")
Styles links based on their origin or destination, which can be a single node type or a group.

In Link_Group_Styles array.
from_node object: type: "from_node", single_node (node type) OR group_name, and optionally connector, style, add_link_label.
to_node object: type: "to_node", single_node (node type) OR group_name, and optionally connector, style, add_link_label.
Example:
All links from any "LoadImage" node will use bluelink. All links to any node in "output_group" will use greenlink.

<JSON>
"Style_Definitions": {
  "bluelink": "stroke:#007bff,stroke-width:2px",
  "greenlink": "stroke:green,stroke-width:2px"
},
"Node_Group": [
  { "group_name": "output_group", "nodes": ["PreviewImage", "SaveImage"] }
],
"Link_Group_Styles": [
  {
    "type": "from_node",
    "single_node": "LoadImage", // This is a node type
    "style": "bluelink"
  },
  {
    "type": "to_node",
    "group_name": "output_group",
    "style": "greenlink",
    "add_link_label": false // Explicitly hide label for these
  }
]

5.4. Priority 4: Group-to-Group (Link_Group_Styles, type: "group_to_group")
Styles links between any node in one group and any node in another group. This rule is bidirectional.

In Link_Group_Styles array.
Object has type: "group_to_group", group_name_1, group_name_2, and optionally connector, style, add_link_label.
Example:
Any link between a node in "sampler_group" and a node in "vae_group" will use orangelink.

<JSON>
"Style_Definitions": {
  "orangelink": "stroke:#fd7e14,stroke-width:2px"
},
"Node_Group": [
  { "group_name": "sampler_group", "nodes": ["KSampler"] },
  { "group_name": "vae_group", "nodes": ["VAEDecode"] }
],
"Link_Group_Styles": [
  {
    "type": "group_to_group",
    "group_name_1": "sampler_group",
    "group_name_2": "vae_group",
    "style": "orangelink"
  }
]

5.5. Priority 5: Data Type (Data_Type_Link_Styles)
Styles links based on their data type (e.g., "IMAGE", "MODEL", "LATENT"). Data types are case-insensitive in the config (e.g., "IMAGE" matches "Image" from workflow).

Data_Type_Link_Styles is an array of objects.
Each object has data_type (string), and optionally style, add_link_label.
Note: connector cannot be set at this level.
Example:
All "IMAGE" links will use bluelink. All "LATENT" links will use yellowlink and will not show labels.

<JSON>
"Style_Definitions": {
  "bluelink": "stroke:#007bff,stroke-width:2px",
  "yellowlink": "stroke:#ffc107,stroke-width:2px"
},
"Data_Type_Link_Styles": [
  {
    "data_type": "IMAGE", // Will match "IMAGE", "Image", "image"
    "style": "bluelink"
  },
  {
    "data_type": "LATENT",
    "style": "yellowlink",
    "add_link_label": false // Override global or other settings
  }
]

5.6. Priority 6: Default Link Settings
These are the global fallbacks for links if no other rule applies.

Default_Connector: Default arrow/line style.
Add_Link_Labels: Global toggle for link labels.
Example:

<JSON>
"Default_Connector": "-->",
"Add_Link_Labels": true
Any link not styled by the rules above will be a solid arrow --> and show its data type label (if Add_Link_Labels is true).

Omitting Parameters
For any styling rule (node or link), if a specific parameter (e.g., shape for nodes, connector for links, style, add_link_label) is not included in the JSON object for that rule, its value will be determined by the next applicable rule in the priority list, or by the global defaults.

For instance, if a Node_Styles entry for "MyCustomNode" only specifies {"shape": "circle"}, the style for "MyCustomNode" will be sought from Node_Group_Styles (if "MyCustomNode" is in a group with a style) or Default_Node_Style.

This allows for flexible and layered styling.

