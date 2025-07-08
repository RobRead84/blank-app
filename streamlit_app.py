import streamlit as st
import requests
import json
import re
import pandas as pd
from io import StringIO
import logging
import time
import uuid
from security_utils import InputValidator, RateLimiter, SessionManager, SecurityLogger

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page config and title
st.set_page_config(page_title="Furze from Firehills", page_icon="🌿")

# Initialize session security
SessionManager.initialize_session()

# Check session timeout
if SessionManager.check_session_timeout():
    st.warning("Your session has expired. Please refresh the page to continue.")
    SessionManager.clear_session()
    st.stop()

# Update activity timestamp
SessionManager.update_activity()

# Initialize rate limiter
if "rate_limiter" not in st.session_state:
    # Configure rate limiting based on environment
    max_requests = st.secrets.get("security", {}).get("max_requests_per_minute", 20)
    st.session_state["rate_limiter"] = RateLimiter(max_requests=max_requests, window_minutes=1)

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

# Helper functions for session testing and debugging
def get_session_aware_payload(user_input, session_approach="comprehensive"):
    """Generate session-aware payload for different LangFlow configurations"""
    sanitized_input = InputValidator.sanitize_input(user_input)
    session_id = st.session_state.get("session_id", "")
    user_id = st.session_state.get("user_id", "")
    
    if session_approach == "simple":
        return {
            "input_value": sanitized_input,
            "session_id": session_id
        }
    elif session_approach == "langchain":
        return {
            "input_value": sanitized_input,
            "session_id": session_id,
            "config": {
                "configurable": {
                    "session_id": session_id,
                    "user_id": user_id
                }
            }
        }
    else:  # comprehensive (default)
        return {
            "input_value": sanitized_input,
            "output_type": "chat",
            "input_type": "chat",
            "session_id": session_id,
            "session_token": st.session_state.get("session_token", ""),
            "user_id": user_id,
            "client_id": session_id,
            "conversation_id": session_id,
            "session_metadata": {
                "session_id": session_id,
                "user_id": user_id,
                "timestamp": time.time(),
                "page": st.session_state.get("page", "Unknown")
            }
        }

def test_session_isolation():
    """Test function to verify that sessions are properly isolated"""
    st.write("### 🧪 Session Isolation Test")
    
    current_session = st.session_state.get("session_id", "")
    st.write(f"**Current Session ID:** `{current_session}`")
    
    if st.button("🔄 Generate New Session ID (Simulate New User)", key="new_session_test"):
        # Force generate a new session ID to simulate a new user
        old_session = st.session_state.get("session_id", "unknown")
        SessionManager.clear_session()
        new_session = st.session_state.get("session_id", "unknown")
        
        st.success(f"Session changed: `{old_session[:8]}...` → `{new_session[:8]}...`")
        st.info("This simulates what happens when a new user visits your app. Each should get a completely separate conversation history.")
    
    # Show current session state
    st.write("**Current Session State:**")
    safe_session_info = {
        "session_id": st.session_state.get("session_id", "")[:8] + "...",
        "user_id": st.session_state.get("user_id", "")[:8] + "...",
        "page": st.session_state.get("page", "Unknown"),
        "messages_count": len(st.session_state.get("messages", {}).get(st.session_state.get("page", "Home"), []))
    }
    st.json(safe_session_info)

def debug_session_transmission():
    """Debug function to verify session IDs are being properly transmitted"""
    st.write("### 🔍 Session ID Transmission Debug")
    
    # Current session info
    session_info = SessionManager.get_session_info()
    st.write("**Current Session Information:**")
    for key, value in session_info.items():
        st.write(f"- {key}: {value}")
    
    # Test payload that would be sent
    session_token = st.session_state.get("session_token", "")
    session_id = st.session_state.get("session_id", "")
    user_id = st.session_state.get("user_id", "")
    
    test_payload = {
        "input_value": "[TEST MESSAGE]",
        "output_type": "chat",
        "input_type": "chat",
        "session_id": session_id,
        "session_token": session_token,
        "user_id": user_id,
        "client_id": session_id,
        "conversation_id": session_id,
        "session_metadata": {
            "session_id": session_id,
            "user_id": user_id,
            "session_token": session_token[:16] + "...",
            "timestamp": time.time(),
            "page": st.session_state.get("page", "Unknown")
        }
    }
    
    st.write("**Test Payload (what gets sent to LangFlow):**")
    st.json(test_payload)
    
    # Test headers
    test_headers = {
        "Content-Type": "application/json",
        "X-Session-ID": session_id,
        "X-Session-Token": session_token[:16] + "..." if session_token else "",
        "X-User-ID": user_id,
        "X-Client-ID": session_id,
        "X-Conversation-ID": session_id,
        "X-Request-ID": str(uuid.uuid4()),
        "X-Timestamp": str(int(time.time())),
        "X-Page-Context": st.session_state.get("page", "Unknown")
    }
    
    st.write("**Test Headers (what gets sent to LangFlow):**")
    st.json(test_headers)
    
    # Recommendations
    st.write("**🔧 LangFlow Configuration Recommendations:**")
    st.info("""
    **In your LangFlow application, you should configure it to:**
    
    1. **Check for session ID in multiple places:**
       - `request.json.get('session_id')`
       - `request.headers.get('X-Session-ID')`
       - `request.json.get('session_metadata', {}).get('session_id')`
    
    2. **Use the session ID to:**
       - Isolate conversation history per user
       - Maintain separate memory/context per session
       - Prevent data bleeding between users
    
    3. **Common LangFlow session patterns:**
       - Set up a ConversationBufferWindowMemory with session_id
       - Use session_id as a key for any persistent storage
       - Configure your chat memory to use the session_id
    """)

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

# ENHANCED Function to query LangFlow API with proper session handling
def query_langflow_api(user_input, endpoint):
    """
    Enhanced API function with proper session ID handling for LangFlow
    """
    # Check rate limiting
    if not st.session_state["rate_limiter"].is_allowed():
        wait_time = st.session_state["rate_limiter"].get_wait_time()
        SecurityLogger.log_security_event("rate_limit_exceeded")
        return {"error": f"Too many requests. Please wait {wait_time} seconds before trying again."}
    
    # Validate input
    is_valid, error_msg = InputValidator.validate_input(user_input)
    if not is_valid:
        SecurityLogger.log_security_event("input_validation_failed", error_msg)
        return {"error": error_msg}
    
    # Sanitize input
    sanitized_input = InputValidator.sanitize_input(user_input)
    
    # Get session identifiers
    session_token = st.session_state.get("session_token", "")
    session_id = st.session_state.get("session_id", "")
    user_id = st.session_state.get("user_id", "")
    
    # LangFlow payload with multiple session ID approaches
    payload = {
        "input_value": sanitized_input,
        "output_type": "chat", 
        "input_type": "chat",
        # Try multiple session field names (LangFlow might expect different field names)
        "session_id": session_id,           # Primary session ID
        "session_token": session_token,     # Full session token
        "user_id": user_id,                 # User identifier
        "client_id": session_id,            # Alternative field name
        "conversation_id": session_id,      # Another common field name
        # Additional session context
        "session_metadata": {
            "session_id": session_id,
            "user_id": user_id,
            "session_token": session_token[:16] + "...",  # Truncated for logging
            "timestamp": time.time(),
            "page": st.session_state.get("page", "Unknown")
        }
    }
    
    # Headers with session information
    headers = {
        "Content-Type": "application/json",
        "Host": "web-server-5a231649.fctl.app",
        "Connection": "keep-alive",
        # Session ID in headers (multiple approaches)
        "X-Session-ID": session_id,                    # Primary header
        "X-Session-Token": session_token,              # Alternative header
        "X-User-ID": user_id,                          # User ID header
        "X-Client-ID": session_id,                     # Client ID header
        "X-Conversation-ID": session_id,               # Conversation ID header
        # Additional context headers
        "X-Request-ID": str(uuid.uuid4()),             # Unique request ID
        "X-Timestamp": str(int(time.time())),          # Request timestamp
        "X-Page-Context": st.session_state.get("page", "Unknown")  # Current page
    }
    
    # Add API key if available
    if API_KEY:
        headers["x-api-key"] = API_KEY
        headers["Authorization"] = f"Bearer {API_KEY}"  # Alternative auth format
    
    # Log the request details in debug mode
    if st.session_state.get("debug_mode", False):
        SecurityLogger.log_security_event("api_request_details", 
            f"Session: {session_id}, User: {user_id}, Page: {st.session_state.get('page')}")
    
    try:
        # Make the request with session information
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
        
        # Get the full response
        full_response = response.json()
        
        # Log successful API call
        SecurityLogger.log_security_event("api_call_success", 
            f"Session: {session_id}, Status: {response.status_code}")
        
        if "error" in full_response:
            return {"error": full_response["error"]}
        
        return full_response
            
    except requests.exceptions.Timeout as e:
        SecurityLogger.log_security_event("api_timeout", f"Session: {session_id}, Error: {str(e)[:50]}", "ERROR")
        return {"error": SecurityLogger.get_safe_error_message(e)}
    except requests.exceptions.RequestException as e:
        SecurityLogger.log_security_event("api_request_error", f"Session: {session_id}, Error: {str(e)[:50]}", "ERROR")
        return {"error": SecurityLogger.get_safe_error_message(e)}
    except ValueError as e:
        SecurityLogger.log_security_event("response_parsing_error", f"Session: {session_id}, Error: {str(e)[:50]}", "ERROR")
        return {"error": "Invalid response from server. Please try again."}
    except Exception as e:
        SecurityLogger.log_security_event("unexpected_error", f"Session: {session_id}, Error: {str(e)[:50]}", "ERROR")
        return {"error": "An unexpected error occurred. Please try again."}

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

# ENHANCED DEBUG SECTION with session management capabilities
if st.session_state["debug_mode"]:
    with st.expander("Debug Information (Expand to see)"):
        # Existing debug info
        st.write("Current Page:", st.session_state["page"])
        st.write("Session State Keys:", list(st.session_state.keys()))
        st.write("Messages Per Page:", {page: len(messages) for page, messages in st.session_state["messages"].items()})
        st.write("Processing Flag:", st.session_state.get("processing", False))
        
        # Enhanced Session Debug Section
        st.write("---")
        st.write("### 🔐 Session Management Debug")
        
        # Current session information
        session_info = SessionManager.get_session_info()
        st.write("**Session Information:**")
        for key, value in session_info.items():
            st.write(f"- {key}: {value}")
        
        # Session IDs that will be sent to LangFlow
        st.write("**Session IDs sent to LangFlow:**")
        st.write(f"- session_id: `{st.session_state.get('session_id', 'Not set')}`")
        st.write(f"- user_id: `{st.session_state.get('user_id', 'Not set')}`")
        st.write(f"- session_token: `{st.session_state.get('session_token', 'Not set')[:16]}...`")
        
        # Test session isolation
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧪 Test Session Isolation"):
                test_session_isolation()
        
        with col2:
            if st.button("🔍 Debug Session Transmission"):
                debug_session_transmission()
        
        # Show configuration status
        st.write("---")
        st.write("### ⚙️ Configuration Status")
        if api_config:
            st.success("✅ API configuration loaded successfully")
            st.write(f"- Endpoints configured: {len(API_ENDPOINTS)}")
            st.write(f"- Connect timeout: {CONNECT_TIMEOUT}s")
            st.write(f"- Read timeout: {READ_TIMEOUT}s")
            st.write(f"- API Key configured: {'Yes' if API_KEY else 'No'}")
            st.write(f"- Rate limit: {st.session_state['rate_limiter'].max_requests} requests/minute")
        else:
            st.error("❌ API configuration not loaded")
        
        # Enhanced Security Logs
        st.write("---")
        st.write("### 🛡️ Security Events")
        
        if st.button("Show Security Summary"):
            summary = SecurityLogger.get_security_summary()
            st.write("**Security Summary:**")
            st.json(summary)
        
        if st.button("Show Recent Security Logs"):
            logs = st.session_state.get("security_logs", [])
            if logs:
                st.write("**Recent Security Events:**")
                for log in logs[-10:]:  # Show last 10
                    severity_emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(log.get("severity", "INFO"), "ℹ️")
                    st.write(f"{severity_emoji} {log['timestamp']}: {log['type']} ({log.get('severity', 'INFO')})")
                    if st.session_state.get("debug_mode") and log.get("details"):
                        st.write(f"   Details: {log['details']}")
            else:
                st.write("No security events logged")
        
        # API Connection Testing
        st.write("---")
        st.write("### 🌐 API Connection Testing")
        
        if st.session_state["page"] in API_ENDPOINTS:
            st.write(f"Current endpoint configured: ✅ Yes")
            
            if st.button("Test API Connection"):
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
            
            # Test actual API call with session info
            if st.button("🧪 Test API Call with Session Info"):
                st.write("Testing actual API call with current session information...")
                
                # Show what would be sent
                test_payload = get_session_aware_payload("Test message from debug", "comprehensive")
                st.write("**Payload that would be sent:**")
                st.json(test_payload)
                
                # Show headers
                session_id = st.session_state.get("session_id", "")
                session_token = st.session_state.get("session_token", "")
                user_id = st.session_state.get("user_id", "")
                
                test_headers = {
                    "Content-Type": "application/json",
                    "X-Session-ID": session_id,
                    "X-User-ID": user_id,
                    "X-Session-Token": session_token[:16] + "..." if session_token else "",
                    "X-Page-Context": st.session_state.get("page", "Unknown")
                }
                
                st.write("**Headers that would be sent:**")
                st.json(test_headers)
                
                st.info("💡 **Check your LangFlow logs** to see if these session identifiers are being received correctly.")
        else:
            st.warning("No endpoint configured for current page")
        
        # Table Parsing Test
        st.write("---")
        st.write("### 📊 Table Parsing Test")
        
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
        
        # Environment Information
        st.write("---")
        st.write("### 🖥️ Environment Information")
        st.write(f"Streamlit version: {st.__version__}")
        st.write(f"Pandas version: {pd.__version__}")
        st.write(f"Requests version: {requests.__version__}")
        
        # Last API Response Debug
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