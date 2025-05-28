import streamlit as st
import requests
import json
import re

# Set page config and title
st.set_page_config(page_title="Furze from Firehills", page_icon="🌿")

# Initialize session state for navigation
if "page" not in st.session_state:
    st.session_state["page"] = "Home"

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state["messages"] = {}
    for page in ["Furze AI", "Eco System Identification", "Eco System + SWOT", "Eco System + SWOT + Scenarios"]:
        st.session_state["messages"][page] = []

# Initialize debug mode in session state
if "debug_mode" not in st.session_state:
    st.session_state["debug_mode"] = False

# API endpoints for different chat modules
API_ENDPOINTS = {
    "Furze AI": "https://web-server-5a231649.fctl.app/api/v1/run/55de672f-c877-4541-8890-2554b2e810a8",
    "Eco System Identification": "https://web-server-5a231649.fctl.app/api/v1/run/9da63433-bb7b-4f41-a5e5-89d025345030",
    "Eco System + SWOT": "https://web-server-5a231649.fctl.app/api/v1/run/11c72c82-1c0f-44fa-b4a9-a6ac8d8d6d9c",
    "Eco System + SWOT + Scenarios": "https://web-server-5a231649.fctl.app/api/v1/run/b362ee31-f35a-4f72-8751-7c38dad04625"
}

# Request timeout settings (in seconds)
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 300.0

def convert_table_to_html(table_lines):
    """Convert table lines to HTML table"""
    if not table_lines:
        return ""
    
    # Clean up table lines and parse cells
    cleaned_lines = []
    for line in table_lines:
        line = line.strip()
        if line and '|' in line:
            # Split by | and clean up cells
            cells = [cell.strip() for cell in line.split('|')]
            # Remove empty cells at start and end (common in markdown tables)
            while cells and not cells[0]:
                cells.pop(0)
            while cells and not cells[-1]:
                cells.pop()
            if cells:  # Only add non-empty rows
                cleaned_lines.append(cells)
    
    if len(cleaned_lines) < 2:
        return ""
    
    # Check if second line is a separator (markdown table format)
    separator_idx = -1
    for i, cells in enumerate(cleaned_lines):
        if len(cells) > 0 and all(re.match(r'^[\s\-:]*

def render_message_with_tables(message_text):
    """Render message text with proper table formatting"""
    # Add custom CSS for table styling that respects Streamlit's theme
    st.markdown("""
    <style>
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1em 0;
        font-family: inherit;
        font-size: inherit;
        color: inherit;
    }
    .custom-table th,
    .custom-table td {
        padding: 8px 12px;
        text-align: left;
        border: 1px solid rgba(128, 128, 128, 0.3);
        vertical-align: top;
    }
    .custom-table th {
        font-weight: bold;
        border-bottom: 2px solid rgba(128, 128, 128, 0.5);
        background-color: rgba(128, 128, 128, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # If there are no pipes, it's definitely not a table
    if '|' not in message_text:
        st.markdown(message_text)
        return
    
    try:
        # Split message into lines
        lines = message_text.split('\n')
        i = 0
        content_parts = []
        
        while i < len(lines):
            line = lines[i].strip()
            
            # More flexible table detection - look for lines with multiple pipes
            if '|' in line and line.count('|') >= 2:
                # Found potential table start
                table_lines = []
                table_start_idx = i
                
                # Collect all consecutive table lines
                while i < len(lines):
                    current_line = lines[i].strip()
                    # Accept any line with at least 2 pipes (allowing for various table formats)
                    if '|' in current_line and current_line.count('|') >= 2:
                        table_lines.append(current_line)
                        i += 1
                    elif current_line == '':  # Allow empty lines within table
                        i += 1
                        continue
                    else:
                        break
                
                # Debug output
                if st.session_state.get("debug_mode", False):
                    st.write(f"Found {len(table_lines)} potential table lines")
                    st.code('\n'.join(table_lines[:3]))  # Show first 3 lines
                
                # Process the table if we have at least 2 lines
                if len(table_lines) >= 2:
                    # Convert table lines to HTML
                    html_table = convert_table_to_html(table_lines)
                    content_parts.append(('table', html_table))
                else:
                    # Not a valid table, treat as regular text
                    content_parts.append(('text', '\n'.join(table_lines)))
            else:
                # Regular line
                content_parts.append(('text', line))
                i += 1
        
        # Render all content parts
        current_text_block = []
        for content_type, content in content_parts:
            if content_type == 'text':
                current_text_block.append(content)
            elif content_type == 'table':
                # Render any accumulated text first
                if current_text_block:
                    st.markdown('\n'.join(current_text_block))
                    current_text_block = []
                # Render the table
                st.markdown(content, unsafe_allow_html=True)
        
        # Render any remaining text
        if current_text_block:
            st.markdown('\n'.join(current_text_block))
            
    except Exception as e:
        if st.session_state.get("debug_mode", False):
            st.error(f"Error rendering table: {str(e)}")
            st.code(message_text)
        # Fallback to regular markdown rendering
        st.markdown(message_text)

def extract_message_from_response(response_data):
    """Extract message text from LangFlow API response"""
    try:
        # Try to get message from the nested structure
        if "outputs" in response_data and isinstance(response_data["outputs"], list) and len(response_data["outputs"]) > 0:
            first_output = response_data["outputs"][0]
            if "outputs" in first_output and isinstance(first_output["outputs"], list) and len(first_output["outputs"]) > 0:
                inner_output = first_output["outputs"][0]
                
                # Try to get from messages array
                if "messages" in inner_output and isinstance(inner_output["messages"], list) and len(inner_output["messages"]) > 0:
                    return inner_output["messages"][0]["message"]
                
                # Try to get from results.message.text
                if "results" in inner_output and "message" in inner_output["results"]:
                    message_obj = inner_output["results"]["message"]
                    if "text" in message_obj:
                        return message_obj["text"]
                    elif "data" in message_obj and "text" in message_obj["data"]:
                        return message_obj["data"]["text"]
        
        # Fallback to string representation
        return json.dumps(response_data, indent=2)
    except Exception as e:
        return f"Error extracting message: {str(e)}\nRaw response: {str(response_data)[:200]}..."

def query_langflow_api(user_input, endpoint):
    """Query the LangFlow API with user input"""
    payload = {
        "input_value": user_input,
        "output_type": "chat",
        "input_type": "chat"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Host": "web-server-5a231649.fctl.app",
        "Connection": "keep-alive"
    }
    
    try:
        response = requests.post(
            endpoint, 
            json=payload, 
            headers=headers, 
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=False
        )
        
        # Handle redirects
        if response.status_code in (301, 302, 303, 307, 308):
            response = requests.post(
                endpoint, 
                json=payload, 
                headers=headers, 
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
        
        response.raise_for_status()
        full_response = response.json()
        
        if "error" in full_response:
            return {"error": full_response["error"]}
        
        return full_response
            
    except requests.exceptions.Timeout as e:
        return {"error": f"API Request Timeout: The server is taking too long to respond. This might be due to a complex query or server load. Details: {e}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API Request Error: {e}"}
    except ValueError as e:
        return {"error": f"Response Parsing Error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected Error: {e}"}

# Sidebar for navigation
with st.sidebar:
    # Display branded logo
    try:
        st.image("https://github.com/RobRead84/blank-app/blob/main/Firehills-logo-h-dark-yellowdoctor.png?raw=true", width=250)
    except:
        st.markdown("# 🌿 Furze")
    
    # Navigation
    st.title("Navigation")
    for page in ["Home", "Furze AI", "Eco System Identification", "Eco System + SWOT", "Eco System + SWOT + Scenarios"]:
        if st.button(page, key=f"nav_{page}"):
            st.session_state["page"] = page
    
    # About section
    st.title("About")
    st.info(
        "This is the interface for Furze AI. "
        "Select a page from the navigation above to get started."
    )
    
    # Developer options
    st.title("Developer Options")
    st.session_state["debug_mode"] = st.checkbox("Enable Debug Mode", value=st.session_state["debug_mode"])

# Main content area
if st.session_state["page"] == "Home":
    st.title("Furze from Firehills")
    st.write("""
    Growth and performance can no longer be driven out of classic approaches taken by executives. Simply doing more of what they are good at doesn't create top and bottom line impacts. The best organisations in the world form bridges with other parties in mutually beneficial ways. Which create ratcheting growth effects which competing organisations cannot easily create. 
    """)
    
    st.write("""
    Furze is your unfair advantage against your competition. It is trained to unpack your organisation based on system thinking IP from Firehills. You can explore the roles of the Ecosystem you operate in today, determine what you are good at and where you could improve. Plus creating simple maps of your strengths, weaknesses, opportunities and potential threats against your organisation.
    """)
    
    st.write("""
    The final piece is what could your organisation actually do today to create that growth leveraging systems thinking. Our trained scenario agent will explore growth using organic/in-organic and creative methods, plus you can throw new ideas at it and ask for rationale and evidence to support if this will work in the real world.

    Explore what your future strategy could be, in a way you've never done it before.
    """)

else:  # Chat pages
    current_page = st.session_state["page"]
    
    if current_page in API_ENDPOINTS:
        st.title(f"🌿 {current_page}")
        
        # Display page-specific descriptions
        descriptions = {
            "Furze AI": "Welcome to Furze. Furze is designed by Firehills as your AI assistant for Eco systems and trained on public organisational data and designed for exploring performance and growth. Explore and flourish!",
            "Eco System Identification": "Systems thinking needs complex technology to create simple strategies for growth. This AI agent has been trained on Firehills Eco system IP framework and will explore the roles organisation play today. And some they don't. **Ensure that organisational data has been uploaded in advance to get the best results.**",
            "Eco System + SWOT": "This AI Agent will build your Eco System mapping against roles, but go one step further and produce a SWOT related to their roles and them as an organisation. **Ensure that organisational data has been uploaded in advance to get the best results.**",
            "Eco System + SWOT + Scenarios": "This AI Agent will build your Eco System mapping against roles, SWOT and also create scenarios for growth. Scenarios are build out on an organic, in-organic and creative basis. **Ensure that organisational data has been uploaded in advance to get the best results.**"
        }
        
        st.write(descriptions[current_page])
        
        # Display chat history
        for message in st.session_state["messages"][current_page]:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    render_message_with_tables(message["content"])
                else:
                    st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("What would you like to ask?"):
            # Add user message to chat history
            st.session_state["messages"][current_page].append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response_data = query_langflow_api(prompt, API_ENDPOINTS[current_page])
                    
                    if "error" in response_data:
                        response_text = f"Sorry, I encountered an error: {response_data['error']}"
                    else:
                        response_text = extract_message_from_response(response_data)
                    
                    # Display the response with table handling
                    render_message_with_tables(response_text)
                    
                    # Add assistant response to chat history
                    st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})

# Debug section
if st.session_state["debug_mode"]:
    with st.expander("Debug Information"):
        st.write("Current Page:", st.session_state["page"])
        st.write("Session State Keys:", list(st.session_state.keys()))
        st.write("Messages Per Page:", {page: len(messages) for page, messages in st.session_state["messages"].items()})
        if st.session_state["page"] in API_ENDPOINTS:
            st.write("Current API Endpoint:", API_ENDPOINTS[st.session_state["page"]])
            st.write("Connect Timeout:", CONNECT_TIMEOUT)
            st.write("Read Timeout:", READ_TIMEOUT)
        
        # API connection test
        if st.button("Test API Connection"):
            endpoint = API_ENDPOINTS.get(st.session_state["page"], API_ENDPOINTS["Furze AI"])
            st.write(f"Testing connection to: {endpoint}")
            try:
                test_response = requests.get(
                    endpoint.split("/api")[0], 
                    timeout=5,
                    allow_redirects=True
                )
                st.write(f"Status Code: {test_response.status_code}")
                st.write(f"Response URL: {test_response.url}")
                if test_response.url != endpoint.split("/api")[0]:
                    st.warning(f"Redirect detected! Original URL redirected to {test_response.url}")
                else:
                    st.success("No redirects detected.")
            except Exception as e:
                st.error(f"Connection test failed: {str(e)}"), cell) for cell in cells):
            separator_idx = i
            break
    
    # Determine header and data rows
    if separator_idx > 0:
        header_cells = cleaned_lines[0]
        data_rows = cleaned_lines[separator_idx + 1:]
    else:
        # No separator found, first row is header
        header_cells = cleaned_lines[0]
        data_rows = cleaned_lines[1:]
    
    # Build HTML table
    html = '<table class="custom-table">\n'
    
    # Add header
    html += '<thead>\n<tr>\n'
    for cell in header_cells:
        # Handle markdown bold formatting
        cell_content = cell.replace('**', '<strong>').replace('**', '</strong>')
        html += f'<th>{cell_content}</th>\n'
    html += '</tr>\n</thead>\n'
    
    # Add data rows
    html += '<tbody>\n'
    for row_cells in data_rows:
        html += '<tr>\n'
        # Ensure we have the same number of cells as header
        for i in range(len(header_cells)):
            cell_content = row_cells[i] if i < len(row_cells) else ''
            # Handle markdown bold formatting
            cell_content = cell_content.replace('**', '<strong>').replace('**', '</strong>')
            html += f'<td>{cell_content}</td>\n'
        html += '</tr>\n'
    html += '</tbody>\n'
    
    html += '</table>'
    return html

def render_message_with_tables(message_text):
    """Render message text with proper table formatting"""
    # Add custom CSS for table styling that respects Streamlit's theme
    st.markdown("""
    <style>
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1em 0;
        font-family: inherit;
        font-size: inherit;
        color: inherit;
    }
    .custom-table th,
    .custom-table td {
        padding: 8px 12px;
        text-align: left;
        border: 1px solid rgba(128, 128, 128, 0.3);
        vertical-align: top;
    }
    .custom-table th {
        font-weight: bold;
        border-bottom: 2px solid rgba(128, 128, 128, 0.5);
        background-color: rgba(128, 128, 128, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # If there are no pipes, it's definitely not a table
    if '|' not in message_text:
        st.markdown(message_text)
        return
    
    try:
        # Split message into lines
        lines = message_text.split('\n')
        i = 0
        content_parts = []
        
        while i < len(lines):
            line = lines[i].strip()
            
            # More flexible table detection - look for lines with multiple pipes
            if '|' in line and line.count('|') >= 2:
                # Found potential table start
                table_lines = []
                table_start_idx = i
                
                # Collect all consecutive table lines
                while i < len(lines):
                    current_line = lines[i].strip()
                    # Accept any line with at least 2 pipes (allowing for various table formats)
                    if '|' in current_line and current_line.count('|') >= 2:
                        table_lines.append(current_line)
                        i += 1
                    elif current_line == '':  # Allow empty lines within table
                        i += 1
                        continue
                    else:
                        break
                
                # Debug output
                if st.session_state.get("debug_mode", False):
                    st.write(f"Found {len(table_lines)} potential table lines")
                    st.code('\n'.join(table_lines[:3]))  # Show first 3 lines
                
                # Process the table if we have at least 2 lines
                if len(table_lines) >= 2:
                    # Convert table lines to HTML
                    html_table = convert_table_to_html(table_lines)
                    content_parts.append(('table', html_table))
                else:
                    # Not a valid table, treat as regular text
                    content_parts.append(('text', '\n'.join(table_lines)))
            else:
                # Regular line
                content_parts.append(('text', line))
                i += 1
        
        # Render all content parts
        current_text_block = []
        for content_type, content in content_parts:
            if content_type == 'text':
                current_text_block.append(content)
            elif content_type == 'table':
                # Render any accumulated text first
                if current_text_block:
                    st.markdown('\n'.join(current_text_block))
                    current_text_block = []
                # Render the table
                st.markdown(content, unsafe_allow_html=True)
        
        # Render any remaining text
        if current_text_block:
            st.markdown('\n'.join(current_text_block))
            
    except Exception as e:
        if st.session_state.get("debug_mode", False):
            st.error(f"Error rendering table: {str(e)}")
            st.code(message_text)
        # Fallback to regular markdown rendering
        st.markdown(message_text)

def extract_message_from_response(response_data):
    """Extract message text from LangFlow API response"""
    try:
        # Try to get message from the nested structure
        if "outputs" in response_data and isinstance(response_data["outputs"], list) and len(response_data["outputs"]) > 0:
            first_output = response_data["outputs"][0]
            if "outputs" in first_output and isinstance(first_output["outputs"], list) and len(first_output["outputs"]) > 0:
                inner_output = first_output["outputs"][0]
                
                # Try to get from messages array
                if "messages" in inner_output and isinstance(inner_output["messages"], list) and len(inner_output["messages"]) > 0:
                    return inner_output["messages"][0]["message"]
                
                # Try to get from results.message.text
                if "results" in inner_output and "message" in inner_output["results"]:
                    message_obj = inner_output["results"]["message"]
                    if "text" in message_obj:
                        return message_obj["text"]
                    elif "data" in message_obj and "text" in message_obj["data"]:
                        return message_obj["data"]["text"]
        
        # Fallback to string representation
        return json.dumps(response_data, indent=2)
    except Exception as e:
        return f"Error extracting message: {str(e)}\nRaw response: {str(response_data)[:200]}..."

def query_langflow_api(user_input, endpoint):
    """Query the LangFlow API with user input"""
    payload = {
        "input_value": user_input,
        "output_type": "chat",
        "input_type": "chat"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Host": "web-server-5a231649.fctl.app",
        "Connection": "keep-alive"
    }
    
    try:
        response = requests.post(
            endpoint, 
            json=payload, 
            headers=headers, 
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=False
        )
        
        # Handle redirects
        if response.status_code in (301, 302, 303, 307, 308):
            response = requests.post(
                endpoint, 
                json=payload, 
                headers=headers, 
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
        
        response.raise_for_status()
        full_response = response.json()
        
        if "error" in full_response:
            return {"error": full_response["error"]}
        
        return full_response
            
    except requests.exceptions.Timeout as e:
        return {"error": f"API Request Timeout: The server is taking too long to respond. This might be due to a complex query or server load. Details: {e}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API Request Error: {e}"}
    except ValueError as e:
        return {"error": f"Response Parsing Error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected Error: {e}"}

# Sidebar for navigation
with st.sidebar:
    # Display branded logo
    try:
        st.image("https://github.com/RobRead84/blank-app/blob/main/Firehills-logo-h-dark-yellowdoctor.png?raw=true", width=250)
    except:
        st.markdown("# 🌿 Furze")
    
    # Navigation
    st.title("Navigation")
    for page in ["Home", "Furze AI", "Eco System Identification", "Eco System + SWOT", "Eco System + SWOT + Scenarios"]:
        if st.button(page, key=f"nav_{page}"):
            st.session_state["page"] = page
    
    # About section
    st.title("About")
    st.info(
        "This is the interface for Furze AI. "
        "Select a page from the navigation above to get started."
    )
    
    # Developer options
    st.title("Developer Options")
    st.session_state["debug_mode"] = st.checkbox("Enable Debug Mode", value=st.session_state["debug_mode"])

# Main content area
if st.session_state["page"] == "Home":
    st.title("Furze from Firehills")
    st.write("""
    Growth and performance can no longer be driven out of classic approaches taken by executives. Simply doing more of what they are good at doesn't create top and bottom line impacts. The best organisations in the world form bridges with other parties in mutually beneficial ways. Which create ratcheting growth effects which competing organisations cannot easily create. 
    """)
    
    st.write("""
    Furze is your unfair advantage against your competition. It is trained to unpack your organisation based on system thinking IP from Firehills. You can explore the roles of the Ecosystem you operate in today, determine what you are good at and where you could improve. Plus creating simple maps of your strengths, weaknesses, opportunities and potential threats against your organisation.
    """)
    
    st.write("""
    The final piece is what could your organisation actually do today to create that growth leveraging systems thinking. Our trained scenario agent will explore growth using organic/in-organic and creative methods, plus you can throw new ideas at it and ask for rationale and evidence to support if this will work in the real world.

    Explore what your future strategy could be, in a way you've never done it before.
    """)

else:  # Chat pages
    current_page = st.session_state["page"]
    
    if current_page in API_ENDPOINTS:
        st.title(f"🌿 {current_page}")
        
        # Display page-specific descriptions
        descriptions = {
            "Furze AI": "Welcome to Furze. Furze is designed by Firehills as your AI assistant for Eco systems and trained on public organisational data and designed for exploring performance and growth. Explore and flourish!",
            "Eco System Identification": "Systems thinking needs complex technology to create simple strategies for growth. This AI agent has been trained on Firehills Eco system IP framework and will explore the roles organisation play today. And some they don't. **Ensure that organisational data has been uploaded in advance to get the best results.**",
            "Eco System + SWOT": "This AI Agent will build your Eco System mapping against roles, but go one step further and produce a SWOT related to their roles and them as an organisation. **Ensure that organisational data has been uploaded in advance to get the best results.**",
            "Eco System + SWOT + Scenarios": "This AI Agent will build your Eco System mapping against roles, SWOT and also create scenarios for growth. Scenarios are build out on an organic, in-organic and creative basis. **Ensure that organisational data has been uploaded in advance to get the best results.**"
        }
        
        st.write(descriptions[current_page])
        
        # Display chat history
        for message in st.session_state["messages"][current_page]:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    render_message_with_tables(message["content"])
                else:
                    st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("What would you like to ask?"):
            # Add user message to chat history
            st.session_state["messages"][current_page].append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response_data = query_langflow_api(prompt, API_ENDPOINTS[current_page])
                    
                    if "error" in response_data:
                        response_text = f"Sorry, I encountered an error: {response_data['error']}"
                    else:
                        response_text = extract_message_from_response(response_data)
                    
                    # Display the response with table handling
                    render_message_with_tables(response_text)
                    
                    # Add assistant response to chat history
                    st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})

# Debug section
if st.session_state["debug_mode"]:
    with st.expander("Debug Information"):
        st.write("Current Page:", st.session_state["page"])
        st.write("Session State Keys:", list(st.session_state.keys()))
        st.write("Messages Per Page:", {page: len(messages) for page, messages in st.session_state["messages"].items()})
        if st.session_state["page"] in API_ENDPOINTS:
            st.write("Current API Endpoint:", API_ENDPOINTS[st.session_state["page"]])
            st.write("Connect Timeout:", CONNECT_TIMEOUT)
            st.write("Read Timeout:", READ_TIMEOUT)
        
        # API connection test
        if st.button("Test API Connection"):
            endpoint = API_ENDPOINTS.get(st.session_state["page"], API_ENDPOINTS["Furze AI"])
            st.write(f"Testing connection to: {endpoint}")
            try:
                test_response = requests.get(
                    endpoint.split("/api")[0], 
                    timeout=5,
                    allow_redirects=True
                )
                st.write(f"Status Code: {test_response.status_code}")
                st.write(f"Response URL: {test_response.url}")
                if test_response.url != endpoint.split("/api")[0]:
                    st.warning(f"Redirect detected! Original URL redirected to {test_response.url}")
                else:
                    st.success("No redirects detected.")
            except Exception as e:
                st.error(f"Connection test failed: {str(e)}")