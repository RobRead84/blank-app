import streamlit as st
import requests
import json
import re
import pandas as pd
from io import StringIO
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page config and title
st.set_page_config(page_title="Furze from Firehills", page_icon="🌿")

# Initialize session state for navigation
if "page" not in st.session_state:
    st.session_state["page"] = "Home"

# Initialize debug mode in session state
if "debug_mode" not in st.session_state:
    st.session_state["debug_mode"] = False

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state["messages"] = {}
    for page in ["Furze", "Eco System Identification", "SWOT Generation", "Growth Scenarios"]:
        st.session_state["messages"][page] = []

# Initialize processing flag to prevent multiple simultaneous requests
if "processing" not in st.session_state:
    st.session_state["processing"] = False

# Function to safely get API configuration
def get_api_config():
    """
    Safely retrieve API configuration from secrets or fallback to defaults.
    Returns None if configuration is missing.
    """
    try:
        # Try to get endpoints from secrets
        if "api" in st.secrets and "endpoints" in st.secrets["api"]:
            endpoints = dict(st.secrets["api"]["endpoints"])
            
            # Get timeouts from secrets or use defaults
            timeouts = {
                "connect": st.secrets.get("api", {}).get("timeouts", {}).get("connect", 10.0),
                "read": st.secrets.get("api", {}).get("timeouts", {}).get("read", 300.0)
            }
            
            # Get optional API key
            api_key = st.secrets.get("api", {}).get("auth", {}).get("key", None)
            
            return {
                "endpoints": endpoints,
                "timeouts": timeouts,
                "api_key": api_key
            }
        else:
            logger.error("API configuration not found in secrets")
            return None
            
    except Exception as e:
        logger.error(f"Error loading API configuration: {str(e)}")
        return None

# Load API configuration
api_config = get_api_config()

# Check if API configuration is available
if api_config is None:
    st.error("""
    ⚠️ **Configuration Error**
    
    The application is not properly configured. API endpoints are missing.
    
    If you're the application owner, please configure the API endpoints in the Streamlit secrets management.
    
    If you're a user, please contact the application administrator.
    """)
    st.stop()

# Extract configuration
API_ENDPOINTS = api_config["endpoints"]
CONNECT_TIMEOUT = api_config["timeouts"]["connect"]
READ_TIMEOUT = api_config["timeouts"]["read"]
API_KEY = api_config["api_key"]

# Validate that all required endpoints are present
required_pages = ["Furze", "Eco System Identification", "SWOT Generation", "Growth Scenarios"]
missing_endpoints = [page for page in required_pages if page not in API_ENDPOINTS]

if missing_endpoints:
    st.error(f"Missing API endpoints for: {', '.join(missing_endpoints)}")
    st.stop()

def display_message_with_tables(content):
    """
    Display content with proper table rendering - multiple fallback approaches
    """
    # Add debug info in debug mode
    if st.session_state.get("debug_mode", False):
        with st.expander("🔍 Table Debug Info", expanded=False):
            st.write(f"Content length: {len(content)}")
            st.write(f"Contains pipes: {'|' in content}")
            has_separator = any(pattern in content for pattern in ["---", "--|", "-|-", "|-|"])
            st.write(f"Has separator: {has_separator}")
            st.write("First 200 chars:")
            st.code(content[:200])
    
    # Manual parsing for any content with pipes
    if "|" in content:
        try:
            lines = content.split('\n')
            current_text = []
            table_lines = []
            in_table = False
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                # Check if this line looks like a table row
                is_table_row = (line_stripped.startswith('|') and 
                              line_stripped.endswith('|') and 
                              line_stripped.count('|') >= 3)
                
                is_separator = (line_stripped.startswith('|') and 
                              any(sep in line_stripped for sep in ["---", "--|", "-|-", "|-|"]))
                
                if is_table_row or is_separator:
                    if not in_table:
                        # Render any accumulated text first
                        if current_text:
                            st.markdown('\n'.join(current_text))
                            current_text = []
                        in_table = True
                    table_lines.append(line_stripped)
                else:
                    # Only end table if we hit a completely non-table line
                    # Empty lines or lines with just whitespace should not end the table
                    if in_table and line_stripped != "":
                        # This is a non-empty, non-table line - end the table
                        if st.session_state.get("debug_mode", False):
                            st.write(f"🔧 Rendering table with {len(table_lines)} lines")
                        render_table_from_lines(table_lines)
                        table_lines = []
                        in_table = False
                    
                    # Add this line to current text if it's not empty or if we're not in a table
                    if line_stripped != "" or not in_table:
                        current_text.append(line)
            
            # Handle any remaining content
            if table_lines and in_table:
                if st.session_state.get("debug_mode", False):
                    st.write(f"🔧 Rendering final table with {len(table_lines)} lines")
                render_table_from_lines(table_lines)
            elif current_text:
                st.markdown('\n'.join(current_text))
            return
        except Exception as e:
            if st.session_state.get("debug_mode", False):
                st.write(f"Manual parsing failed: {e}")
                st.write("Falling back to regular markdown")
    
    # Fallback to regular markdown
    st.markdown(content)

def render_table_from_lines(table_lines):
    """
    Convert table lines to a proper Streamlit table
    """
    try:
        if len(table_lines) < 2:  # Need at least header and one data row
            st.markdown('\n'.join(table_lines))
            return
        
        # Debug output
        if st.session_state.get("debug_mode", False):
            st.write(f"🔧 Processing {len(table_lines)} table lines:")
            for i, line in enumerate(table_lines):
                st.write(f"  Line {i}: {repr(line)}")
        
        # Find header line (first non-separator line)
        header_line = None
        header_idx = 0
        for i, line in enumerate(table_lines):
            if not any(sep in line for sep in ["---", "--|", "-|-", "|-|"]):
                header_line = line
                header_idx = i
                break
        
        if not header_line:
            st.markdown('\n'.join(table_lines))
            return
        
        # Extract headers
        headers = [col.strip() for col in header_line.split('|')[1:-1]]  # Remove first and last empty elements
        headers = [h for h in headers if h]  # Remove empty headers
        
        if not headers:
            st.markdown('\n'.join(table_lines))
            return
        
        # Find data lines (skip header and separator lines)
        data_lines = []
        for i, line in enumerate(table_lines):
            if i > header_idx and not any(sep in line for sep in ["---", "--|", "-|-", "|-|"]):
                data_lines.append(line)
        
        # Extract data rows
        rows = []
        for line in data_lines:
            if '|' in line:
                row_data = [col.strip() for col in line.split('|')[1:-1]]  # Remove first and last empty elements
                row_data = [cell for cell in row_data if cell or len(row_data) <= len(headers)]  # Keep empty cells if row length matches
                
                # Pad or trim row to match header length
                while len(row_data) < len(headers):
                    row_data.append("")
                if len(row_data) > len(headers):
                    row_data = row_data[:len(headers)]
                
                rows.append(row_data)
        
        if rows:
            # Create DataFrame and display
            df = pd.DataFrame(rows, columns=headers)
            if st.session_state.get("debug_mode", False):
                st.write(f"🔧 Created DataFrame with shape: {df.shape}")
                st.write("Headers:", headers)
                st.write("First row:", rows[0] if rows else "No rows")
            
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            # Fallback to markdown if no data rows found
            if st.session_state.get("debug_mode", False):
                st.write("🔧 No data rows found, falling back to markdown")
            st.markdown('\n'.join(table_lines))
            
    except Exception as e:
        # If anything fails, just render as markdown
        if st.session_state.get("debug_mode", False):
            st.write(f"🔧 Table rendering error: {e}")
        st.markdown('\n'.join(table_lines))

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
    for page in ["Home", "Furze", "Eco System Identification", "SWOT Generation", "Growth Scenarios"]:
        if st.button(page, key=f"nav_{page}"):
            st.session_state["page"] = page
            st.session_state["processing"] = False  # Reset processing flag when changing pages
    
    # Debug toggle button
    st.title("Settings")
    if st.button("Toggle Debug Mode"):
        st.session_state["debug_mode"] = not st.session_state["debug_mode"]
    
    debug_status = "Enabled" if st.session_state["debug_mode"] else "Disabled"
    st.write(f"Debug Mode: {debug_status}")
    
    # About section
    st.title("About")
    st.info(
        "This is the interface for Furze from Firehills. "
        "Select a page from the navigation above to get started."
    )

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
    
    # Add API key to headers if available
    if API_KEY:
        headers["X-API-Key"] = API_KEY
        headers["Authorization"] = f"Bearer {API_KEY}"
    
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
        logger.error(f"API timeout error: {e}")
        return {"error": f"API Request Timeout: The server is taking too long to respond. This might be due to a complex query or server load."}
    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {e}")
        return {"error": f"API Request Error: Unable to connect to the service. Please try again later."}
    except ValueError as e:
        logger.error(f"Response parsing error: {e}")
        return {"error": f"Response Parsing Error: Invalid response from server."}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"An unexpected error occurred. Please try again."}

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
        if current_page == "Furze":
            st.write("""
            Welcome to Furze. Furze is designed by Firehills as your Think Tech assistant for Eco systems, trained on 
            public organisational data and designed for exploring performance and growth. Explore and flourish!
            """)
        elif current_page == "Eco System Identification":
            st.write("""
            Systems thinking needs complex technology to create simple strategies for growth. 
            Furze has been trained on Firehills Eco system IP framework trained to explore the roles 
            organisation play today. And some they don't. **Ensure that organisational data has been 
            uploaded in advance to get the best results.**
            """)
        elif current_page == "SWOT Generation":
            st.write("""
            Furze will build out a SWOT analysis based on Eco system roles to support business strategy and modelling. **Ensure that organisational 
            data has been uploaded in advance to get the best results.**
            """)
        elif current_page == "Growth Scenarios":
            st.write("""
            This is where Furze gets interesting. Based on your eco system mapping and SWOT you can now explore current and new growth strategies. 
            This model will generate 50 growth strategies, evaluate them all and then present the most realistic 5 growth options.
            **Ensure that organisational data has been uploaded in advance to get the best results.**
            """)
        
        # Get the appropriate endpoint
        endpoint = API_ENDPOINTS[current_page]
        
        # Display chat messages from history
        for message in st.session_state["messages"][current_page]:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    # Use the new table rendering function for assistant messages
                    display_message_with_tables(message["content"])
                else:
                    # Regular markdown for user messages
                    st.markdown(message["content"])
        
        # Chat input - disable during processing
        chat_input_disabled = st.session_state.get("processing", False)
        if prompt := st.chat_input("What would you like to ask?", disabled=chat_input_disabled):
            # Set processing flag to prevent multiple simultaneous requests
            st.session_state["processing"] = True
            
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
                        st.markdown(response_text)
                        # Add error response to chat history
                        st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})
                    else:
                        # Extract the message using our function
                        response_text = extract_message_from_response(response_data)
                        
                        # Use the new table rendering function for immediate display
                        display_message_with_tables(response_text)
                        
                        # Add assistant response to chat history
                        st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})
            
            # Reset processing flag and rerun to scroll to top of new response
            st.session_state["processing"] = False
            st.rerun()

# Add debug section only if debug mode is enabled
if st.session_state["debug_mode"]:
    with st.expander("Debug Information (Expand to see)"):
        st.write("Current Page:", st.session_state["page"])
        st.write("Session State Keys:", list(st.session_state.keys()))
        st.write("Messages Per Page:", {page: len(messages) for page, messages in st.session_state["messages"].items()})
        st.write("Processing Flag:", st.session_state.get("processing", False))
        
        # Show configuration status
        st.write("**Configuration Status:**")
        if api_config:
            st.success("✅ API configuration loaded successfully")
            st.write(f"- Endpoints configured: {len(API_ENDPOINTS)}")
            st.write(f"- Connect timeout: {CONNECT_TIMEOUT}s")
            st.write(f"- Read timeout: {READ_TIMEOUT}s")
            st.write(f"- API Key configured: {'Yes' if API_KEY else 'No'}")
        else:
            st.error("❌ API configuration not loaded")
        
        if st.session_state["page"] in API_ENDPOINTS:
            # Don't show the actual endpoint in production
            st.write(f"Current endpoint configured: Yes")
        
        # Add network troubleshooting button
        if st.button("Test API Connection"):
            if st.session_state["page"] in API_ENDPOINTS:
                endpoint = API_ENDPOINTS[st.session_state["page"]]
                st.write(f"Testing connection to API...")
                try:
                    test_response = requests.get(
                        endpoint.split("/api")[0], 
                        timeout=5,
                        allow_redirects=True
                    )
                    st.write(f"Status Code: {test_response.status_code}")
                    if test_response.status_code == 200:
                        st.success("Connection successful!")
                    else:
                        st.warning(f"Unexpected status code: {test_response.status_code}")
                except Exception as e:
                    st.error(f"Connection test failed: {str(e)}")
            else:
                st.warning("No endpoint configured for current page")
        
        # Add table parsing test button
        if st.button("Test Table Parsing", key="test_table_parsing"):
            st.write("**Testing table parsing with sample data:**")
            test_table = """Here's some text before the table.

| Role Type | Activities & Evidence | Revenue Generated (FY24) |
|---------------------|--------------------------------------------------------------------------------------------------------|------------------------------------|
| Keystone | Orchestrates value chain, controls IP, invests in ecosystem health | £494.7m (total) |
| Licensor | Licenses IP for games, media, merchandise; strict brand control | £31.4m |
| Platform Provider | Retail/online/event platforms, digital tools, community engagement | Retail: £62.0m, Online: £43.0m, Trade: £169.2m |

And here's some text after the table."""
            
            st.write("**Raw input:**")
            st.code(test_table)
            st.write("**Rendered output:**")
            display_message_with_tables(test_table)
        
        # Add version and environment info
        st.write("**Environment Information:**")
        st.write(f"Streamlit version: {st.__version__}")
        st.write(f"Pandas version: {pd.__version__}")
        
        # Test actual API response format
        if st.button("Debug Last API Response", key="debug_api_response"):
            if st.session_state["messages"][st.session_state["page"]]:
                last_assistant_msg = None
                for msg in reversed(st.session_state["messages"][st.session_state["page"]]):
                    if msg["role"] == "assistant":
                        last_assistant_msg = msg["content"]
                        break
                
                if last_assistant_msg:
                    st.write("**Last API Response Content:**")
                    st.code(last_assistant_msg[:500] + "..." if len(last_assistant_msg) > 500 else last_assistant_msg)
                    
                    # Check if it contains table markers
                    has_pipes = "|" in last_assistant_msg
                    has_dashes = "---" in last_assistant_msg or "--|" in last_assistant_msg
                    st.write(f"Contains pipe characters: {has_pipes}")
                    st.write(f"Contains table separators: {has_dashes}")
                    
                    if has_pipes and has_dashes:
                        st.write("✅ Response appears to contain markdown table")
                    else:
                        st.write("❌ Response doesn't appear to contain markdown table format")
                else:
                    st.write("No assistant messages found")
            else:
                st.write("No messages in current chat")