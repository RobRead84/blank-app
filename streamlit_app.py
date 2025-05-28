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
    
    # Parse first line as header
    header_line = table_lines[0].strip()
    header_cells = [cell.strip() for cell in header_line.split('|')[1:-1]]
    
    # Check if second line is a separator (contains only -, :, |, and spaces)
    data_start = 1
    if len(table_lines) > 1:
        separator_line = table_lines[1].strip()
        if re.match(r'^\|[\s\-:|\s]*\|$', separator_line):
            data_start = 2
    
    # Build HTML table
    html = '<table class="custom-table">\n'
    
    # Add header
    html += '<thead>\n<tr>\n'
    for cell in header_cells:
        html += f'<th>{cell}</th>\n'
    html += '</tr>\n</thead>\n'
    
    # Add data rows
    html += '<tbody>\n'
    for line in table_lines[data_start:]:
        line = line.strip()
        if line:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            html += '<tr>\n'
            for cell in cells:
                html += f'<td>{cell}</td>\n'
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
        border: 1px solid var(--text-color, #262730);
        opacity: 0.3;
    }
    .custom-table th {
        font-weight: bold;
        border-bottom: 2px solid var(--text-color, #262730);
    }
    .custom-table tr:nth-child(even) {
        background-color: transparent;
    }
    .custom-table tr:nth-child(odd) {
        background-color: transparent;
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
        processed_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if this line looks like a table row (contains |)
            if '|' in line and line.startswith('|') and line.endswith('|'):
                # Found potential table start
                table_lines = []
                
                # Collect all consecutive table lines
                while i < len(lines):
                    current_line = lines[i].strip()
                    if '|' in current_line and current_line.startswith('|') and current_line.endswith('|'):
                        table_lines.append(current_line)
                        i += 1
                    else:
                        break
                
                # Process the table if we have at least 2 lines (header + data)
                if len(table_lines) >= 2:
                    # Render any text before the table
                    if processed_lines:
                        st.markdown('\n'.join(processed_lines))
                        processed_lines = []
                    
                    # Convert table lines to HTML
                    html_table = convert_table_to_html(table_lines)
                    st.markdown(html_table, unsafe_allow_html=True)
                else:
                    # Not a valid table, add lines back to processed_lines
                    processed_lines.extend(table_lines)
            else:
                # Regular line, add to processed_lines
                processed_lines.append(lines[i])
                i += 1
        
        # Render any remaining text
        if processed_lines:
            st.markdown('\n'.join(processed_lines))
            
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