import streamlit as st
import requests
import json
import pandas as pd
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

# Updated API endpoints for different chat modules with increased timeout parameters.
# Using the web-server urls instead of CloudFront URLs
API_ENDPOINTS = {
    "Furze AI": "https://web-server-5a231649.fctl.app/api/v1/run/55de672f-c877-4541-8890-2554b2e810a8",
    "Eco System Identification": "https://web-server-5a231649.fctl.app/api/v1/run/9da63433-bb7b-4f41-a5e5-89d025345030",
    "Eco System + SWOT": "https://web-server-5a231649.fctl.app/api/v1/run/11c72c82-1c0f-44fa-b4a9-a6ac8d8d6d9c",
    "Eco System + SWOT + Scenarios": "https://web-server-5a231649.fctl.app/api/v1/run/b362ee31-f35a-4f72-8751-7c38dad04625"
}

# Request timeout settings (in seconds)
# Increase these values to prevent timeouts with long-running API calls
CONNECT_TIMEOUT = 10.0  # Connection timeout
READ_TIMEOUT = 300.0    # Read timeout - increased to 5 minutes

# Debug function to analyze table detection issues
def debug_table_detection(message_text):
    st.write("### Debug: Table Detection")
    
    # Count table-like markers
    pipe_count = message_text.count('|')
    newline_pipe_count = message_text.count('\n|')
    
    st.write(f"Pipe symbols: {pipe_count}")
    st.write(f"Newline+pipe: {newline_pipe_count}")
    
    # Show a sample of the message for inspection
    st.write("### First 500 chars of message:")
    st.code(message_text[:500])
    
    # If we have a table, show its raw form
    if '|' in message_text and '\n|' in message_text:
        start_idx = message_text.find('\n|')
        end_idx = message_text.find('\n\n', start_idx)
        if end_idx == -1:
            end_idx = min(start_idx + 500, len(message_text))
        
        st.write("### Raw table sample:")
        st.code(message_text[start_idx:end_idx])

# Improved rendering function that preserves all text and formats tables correctly
def render_message_with_tables(message_text):
    # If there are no pipes, it's definitely not a table
    if '|' not in message_text:
        st.markdown(message_text)
        return
    
    try:
        # Look for tables with a specific pattern
        table_pattern = r'(\*\*.*?\*\*\s*\n)?\s*(\|.*?\|.*?\n\|[-:\s|]+\|.*?\n(?:\|.*?\|.*?\n)+)'
        
        # Find all matches
        matches = re.finditer(table_pattern, message_text, flags=re.DOTALL)
        
        # Keep track of the last position we processed
        last_end = 0
        
        # Process each table found
        for match in matches:
            start, end = match.span()
            table_text = match.group(0)
            
            # Display any text before the table
            if start > last_end:
                st.markdown(message_text[last_end:start])
            
            # Check if there's a title in the table
            title_match = re.search(r'\*\*(.*?)\*\*', table_text)
            if title_match:
                title = title_match.group(1)
                st.markdown(f"**{title}**")
                # Remove the title from table_text to avoid duplicating it
                table_text = re.sub(r'\*\*.*?\*\*\s*\n', '', table_text, count=1)
            
            # Process the table rows
            rows = [row.strip() for row in table_text.split('\n') if row.strip().startswith('|') and row.strip().endswith('|')]
            
            if len(rows) >= 2:  # Need at least header and separator row
                # Extract header cells
                header_cells = [cell.strip() for cell in rows[0].split('|') if cell.strip()]
                
                # Extract data rows (skip header and separator)
                data_rows = []
                for row in rows[2:]:  # Skip header and separator
                    cells = [cell.strip() for cell in row.split('|') if cell.strip()]
                    if cells:
                        data_rows.append(cells)
                
                # Create HTML table with better styling
                html_table = """
                <style>
                table.furze-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                    font-size: 0.9em;
                    border-radius: 5px;
                    overflow: hidden;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
                }
                table.furze-table thead tr {
                    background-color: #009879;
                    color: #ffffff;
                    text-align: left;
                    font-weight: bold;
                }
                table.furze-table th,
                table.furze-table td {
                    padding: 12px 15px;
                    border: 1px solid #dddddd;
                }
                table.furze-table tbody tr {
                    border-bottom: 1px solid #dddddd;
                }
                table.furze-table tbody tr:nth-of-type(even) {
                    background-color: #f3f3f3;
                }
                table.furze-table tbody tr:last-of-type {
                    border-bottom: 2px solid #009879;
                }
                </style>
                <table class="furze-table">
                """
                
                # Add header
                html_table += "<thead>\n<tr>\n"
                for cell in header_cells:
                    html_table += f"<th>{cell}</th>\n"
                html_table += "</tr>\n</thead>\n"
                
                # Add body
                html_table += "<tbody>\n"
                for row in data_rows:
                    html_table += "<tr>\n"
                    # Make sure we don't exceed the number of header cells
                    for i, cell in enumerate(row):
                        if i < len(header_cells):
                            html_table += f"<td>{cell}</td>\n"
                    html_table += "</tr>\n"
                html_table += "</tbody>\n"
                
                html_table += "</table>"
                
                # Display the HTML table
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                # Not enough rows for a valid table, just display as markdown
                st.markdown(table_text)
            
            # Update the last_end position for the next iteration
            last_end = end
        
        # Display any remaining text after the last table
        if last_end < len(message_text):
            st.markdown(message_text[last_end:])
    
    except Exception as e:
        if st.session_state["debug_mode"]:
            st.error(f"Error rendering table: {str(e)}")
        # Fallback to regular markdown rendering
        st.markdown(message_text)

# Function to extract message from LangFlow response
def extract_message_from_response(response_data):
    try:
        # Path 1: Try to get message from the nested structure based on the example
        if "outputs" in response_data and isinstance(response_data["outputs"], list) and len(response_data["outputs"]) > 0:
            first_output = response_data["outputs"][0]
            if "outputs" in first_output and isinstance(first_output["outputs"], list) and len(first_output["outputs"]) > 0:
                inner_output = first_output["outputs"][0]
                
                # Path 1a: Try to get from messages array
                if "messages" in inner_output and isinstance(inner_output["messages"], list) and len(inner_output["messages"]) > 0:
                    return inner_output["messages"][0]["message"]
                
                # Path 1b: Try to get from results.message.text
                if "results" in inner_output and "message" in inner_output["results"]:
                    message_obj = inner_output["results"]["message"]
                    if "text" in message_obj:
                        return message_obj["text"]
                    elif "data" in message_obj and "text" in message_obj["data"]:
                        return message_obj["data"]["text"]
        
        # Fallback to string representation if we can't find the message
        return json.dumps(response_data, indent=2)
    except Exception as e:
        return f"Error extracting message: {str(e)}\nRaw response: {str(response_data)[:200]}..."

# Function to query LangFlow API and return full response
def query_langflow_api(user_input, endpoint):
    payload = {
        "input_value": user_input,
        "output_type": "chat",
        "input_type": "chat"
    }
    
    headers = {
        "Content-Type": "application/json",
        # Adding additional headers to ensure direct connection and prevent redirects
        "Host": "web-server-5a231649.fctl.app",
        "Connection": "keep-alive"
    }
    
    try:
        # Make the request with explicit timeouts to prevent 504 errors
        response = requests.post(
            endpoint, 
            json=payload, 
            headers=headers, 
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),  # (connect timeout, read timeout)
            allow_redirects=False  # Try to prevent redirects to CloudFront
        )
        
        # Check for redirect - if redirected, we'll use the direct URL we want
        if response.status_code in (301, 302, 303, 307, 308):
            # Get the real URL from our mapping - use the original endpoint
            response = requests.post(
                endpoint, 
                json=payload, 
                headers=headers, 
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
        
        response.raise_for_status()
        
        # Get the full response
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
        # Fallback to text if logo fails to load
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

# Content for each page
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

else:  # For all chat pages, use the same template with different endpoints
    current_page = st.session_state["page"]
    
    # Check if the current page is a valid chat page
    if current_page in API_ENDPOINTS:
        st.title(f"🌿 {current_page}")
        
        # Display appropriate description based on the page
        if current_page == "Furze AI":
            st.write("""
            Welcome to Furze. Furze is designed by Firehills as your AI assistant for Eco systems and trained on 
            public organisational data and designed for exploring performance and growth. Explore and flourish!
            """)
        elif current_page == "Eco System Identification":
            st.write("""
            Systems thinking needs complex technology to create simple strategies for growth. 
            This AI agent has been trained on Firehills Eco system IP framework and will explore the roles 
            organisation play today. And some they don't. **Ensure that organisational data has been 
            uploaded in advance to get the best results.**
            """)
        elif current_page == "Eco System + SWOT":
            st.write("""
            This AI Agent will build your Eco System mapping against roles, but go one step further and 
            produce a SWOT related to their roles and them as an organisation. **Ensure that organisational 
            data has been uploaded in advance to get the best results.**
            """)
        elif current_page == "Eco System + SWOT + Scenarios":
            st.write("""
            This AI Agent will build your Eco System mapping against roles, SWOT and also create scenarios for growth. 
            Scenarios are build out on an organic, in-organic and creative basis. **Ensure that organisational 
            data has been uploaded in advance to get the best results.**
            """)
        
        # Get the appropriate endpoint
        endpoint = API_ENDPOINTS[current_page]
        
        # Display chat messages from history
        for message in st.session_state["messages"][current_page]:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    if st.session_state["debug_mode"] and "|" in message["content"]:
                        debug_table_detection(message["content"])
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
                # Use spinner while waiting for the response
                with st.spinner("Thinking..."):
                    response_data = query_langflow_api(prompt, endpoint)
                    
                    if "error" in response_data:
                        response_text = f"Sorry, I encountered an error: {response_data['error']}"
                    else:
                        # Extract the message using our function
                        response_text = extract_message_from_response(response_data)
                    
                    # Show debug info if enabled
                    if st.session_state["debug_mode"] and "|" in response_text:
                        debug_table_detection(response_text)
                    
                    # Display the response with proper table handling
                    render_message_with_tables(response_text)
                    
                    # Add assistant response to chat history
                    st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})

# Add debug section to help troubleshoot
with st.expander("Debug Information (Expand to see)"):
    st.write("Current Page:", st.session_state["page"])
    st.write("Session State Keys:", list(st.session_state.keys()))
    st.write("Messages Per Page:", {page: len(messages) for page, messages in st.session_state["messages"].items()})
    if st.session_state["page"] in API_ENDPOINTS:
        st.write("Current API Endpoint:", API_ENDPOINTS[st.session_state["page"]])
        st.write("Connect Timeout:", CONNECT_TIMEOUT)
        st.write("Read Timeout:", READ_TIMEOUT)
    
    # Add network troubleshooting button
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