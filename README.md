## comfyuiworkflow-to-mermaid
Converts ComfyUI workflows into clear Mermaid diagrams. Features a WebUI for one-click conversion of .json/PNG workflow files with direct diagram rendering, zoom, and pan. Supports extensive custom styling for nodes, groups, and links via flexible strategies. Includes automatic dark mode adaptation for diagrams.

Turning some seemingly messy ComfyUI workflows, like this:
![image](https://github.com/user-attachments/assets/2a5960e1-c8fe-4c99-9027-0e1c31df6fc2)
Into clear and simple mermaid charts like this:
![image](https://github.com/user-attachments/assets/d72edaa4-15c2-498b-9d55-f0e026e3f0d7)

##Key Features:
1. Convert any ComfyUI workflow (.json/.png) to Mermaid and display it on the web UI.
2. Freely choose default Mermaid styles, node styles, and connection styles.
3. Freely change the display style of the workflow in the Mermaid chart through multiple built-in strategies.
4. Supports detecting workflow groups and supports dark mode.

Getting Started:
Download the latest release package, open wf2mermaid.exe, drag the comfyuiworkflow json into the webui interface to display the workflow's mermaid chart.
## Configuring Mermaid Styles (`Mermaid_config.json`)
Customize your Mermaid diagrams using `Mermaid_config.json`. If this file is missing or invalid, default settings are applied.
### 1. General Configuration
Global settings for the diagram:
*   `Default_Graph_Direction`: Diagram layout (e.g., `"TD"`, `"LR"`).
    *   Example: `"Default_Graph_Direction": "LR"`
*   `Default_Connector`: Default line style for links (e.g., `"-->"`).
    *   Example: `"Default_Connector": "---"`
*   `Default_Node_Style`: Default CSS style for all nodes (can be a direct string or an alias from `Style_Definitions`).
    *   Example: `"Default_Node_Style": "fill:#f9f,stroke:#333,stroke-width:2px"`
*   `Default_Node_Shape`: Default shape for nodes (e.g., `"rectangle"`, `"round"`).
    *   Example: `"Default_Node_Shape": "stadium"`
*   `Add_Link_Labels`: Show (`true`) or hide (`false`) data type labels on links globally.
    *   Example: `"Add_Link_Labels": false`
*   `Generate_ComfyUI_Subgraphs`: Enable (`true`) or disable (`false`) subgraphs from ComfyUI groups.
    *   Example: `"Generate_ComfyUI_Subgraphs": true`
*   `App_Port`: (For web UI) Port for the local server.
    *   Example: `"App_Port": 5567`
### 2. Style Definitions (`Style_Definitions`)
Define reusable style aliases. The key is your alias name, and the value is the Mermaid CSS string.
```json
"Style_Definitions": {
  "loaderStyle": "fill:#ccf,stroke:#555",
  "importantLink": "stroke:red,stroke-width:3px"
}
收起
3. Node Group Definitions (Node_Group)
Map ComfyUI node types to custom group names. These group names are used for group-based styling.

group_name: Your custom name for the group.
nodes: An array of ComfyUI node type strings belonging to this group.
<JSON>
"Node_Group": [
  {
    "group_name": "vae_nodes",
    "nodes": ["VAEDecode", "VAEEncode", "VAELoader"]
  }
]
4. Node Styling
You can style nodes based on their specific type, the group they belong to, or use a default style. Each rule can specify style (CSS string or alias) and/or shape.

Specific Node Type (Node_Styles): Styles for individual ComfyUI node types.

Keys are node types (e.g., "LoadImage"). Values are objects with style and/or shape.
<JSON>
"Node_Styles": {
  "LoadImage": { "style": "loaderStyle", "shape": "subroutine" },
  "PreviewImage": { "shape": "round" } // Style inherited
}
Node Group (Node_Group_Styles): Styles for nodes within a defined group.

An array of objects, each with group_name, style, and/or shape.
<JSON>
"Node_Group_Styles": [
  { "group_name": "vae_nodes", "style": "fill:#ffe0e0", "shape": "hexagon" }
]
Default Node Style & Shape: Fallback styles (Default_Node_Style, Default_Node_Shape in General Configuration).

Node Styling Priority:
Specific Node Type (Node_Styles) > Node Group (Node_Group_Styles) > Default Node Settings.
Higher priority settings override lower ones for the properties they define (style or shape).

5. Link Styling
Customize link appearance (connector, style, label visibility) using various rules. Each rule can specify connector, style (CSS string or alias), and/or add_link_label (boolean).

Point-to-Point (Link_Styles): For links between specific start_node_type and end_node_type.

<JSON>
"Link_Styles": [
  {
    "start_node_type": "CheckpointLoaderSimple",
    "end_node_type": "VAEEncode",
    "style": "importantLink",
    "connector": "-.->"
  }
]
Group-Based (Link_Group_Styles): An array of objects, each with a type:

type: "single_to_group": Between a single_node (type) and a group_name. Bidirectional.
<JSON>
{ "type": "single_to_group", "single_node": "LoadImage", "group_name": "vae_nodes", "style": "stroke:blue" }
type: "from_node": Links originating from a single_node (type) or a group_name.
<JSON>
{ "type": "from_node", "single_node": "LoadImage", "style": "stroke:green" }
type: "to_node": Links ending at a single_node (type) or a group_name.
<JSON>
{ "type": "to_node", "group_name": "output_group", "style": "stroke:purple", "add_link_label": false }
type: "group_to_group": Between group_name_1 and group_name_2. Bidirectional.
<JSON>
{ "type": "group_to_group", "group_name_1": "vae_nodes", "group_name_2": "sampler_nodes", "connector": "---" }
Data Type (Data_Type_Link_Styles): Based on the link's data_type (e.g., "IMAGE", "MODEL").

<JSON>
"Data_Type_Link_Styles": [
  { "data_type": "IMAGE", "style": "stroke:cyan,stroke-width:2px" },
  { "data_type": "LATENT", "add_link_label": true } // Override global
]
Default Link Settings: Fallbacks (Default_Connector, Add_Link_Labels in General Configuration).

Link Styling Priority:

Point-to-Point (Link_Styles)
Point-to-Group (Link_Group_Styles with type: "single_to_group")
From/To Node/Group (Link_Group_Styles with type: "from_node" or type: "to_node")
Group-to-Group (Link_Group_Styles with type: "group_to_group")
Data Type (Data_Type_Link_Styles)
Default Link Settings. Higher priority settings override lower ones for the properties they define (connector, style, or add_link_label).
Omitting Parameters
If a styling rule (for nodes or links) doesn't specify a parameter (e.g., shape for nodes, style for links), that parameter's value will be determined by the next applicable rule in the priority list or by the global defaults.
