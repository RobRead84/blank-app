import streamlit as st
import requests
import json
import re
import pandas as pd
from io import StringIO

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

# Updated API endpoints for different chat modules with increased timeout parameters.
# Using the web-server urls instead of CloudFront URLs
API_ENDPOINTS = {
    "Furze": "https://web-server-5a231649.fctl.app/api/v1/run/55de672f-c877-4541-8890-2554b2e810a8",
    "Eco System Identification": "https://web-server-5a231649.fctl.app/api/v1/run/9da63433-bb7b-4f41-a5e5-89d025345030",
    "SWOT Generation": "https://web-server-5a231649.fctl.app/api/v1/run/11c72c82-1c0f-44fa-b4a9-a6ac8d8d6d9c",
    "Growth Scenarios": "https://web-server-5a231649.fctl.app/api/v1/run/5c8064c7-a886-48e2-b914-3a1f5603ed6f"
}

# Request timeout settings (in seconds)
# Increase these values to prevent timeouts with long-running API calls
CONNECT_TIMEOUT = 10.0  # Connection timeout
READ_TIMEOUT = 300.0    # Read timeout - increased to 5 minutes

def display_message_with_tables(content):
    """
    Display content with proper table rendering - multiple fallback approaches
    """
    # Method 1: Try unsafe_allow_html first
    try:
        if "|" in content and ("---" in content or "--|" in content):
            st.markdown(content, unsafe_allow_html=True)
            return
    except Exception as e:
        pass
    
    # Method 2: Manual parsing approach
    if "|" in content and ("---" in content or "--|" in content):
        try:
            # Split content by lines
            lines = content.split('\n')
            current_text = []
            table_lines = []
            in_table = False
            
            for line in lines:
                line = line.strip()
                
                # Check if this line looks like a table row
                if line.startswith('|') and line.endswith('|') and line.count('|') >= 3:
                    if not in_table:
                        # Render any accumulated text first
                        if current_text:
                            st.markdown('\n'.join(current_text))
                            current_text = []
                        in_table = True
                    table_lines.append(line)
                elif line.startswith('|') and ('---' in line or '--|' in line):
                    # This is a table separator line
                    table_lines.append(line)
                else:
                    if in_table:
                        # End of table, render it
                        render_table_from_lines(table_lines)
                        table_lines = []
                        in_table = False
                    
                    if line:  # Only add non-empty lines
                        current_text.append(line)
            
            # Handle any remaining content
            if table_lines and in_table:
                render_table_from_lines(table_lines)
            elif current_text:
                st.markdown('\n'.join(current_text))
            return
        except Exception as e:
            pass
    
    # Method 3: Fallback to regular markdown
    st.markdown(content)

def render_table_from_lines(table_lines):
    """
    Convert table lines to a proper Streamlit table
    """
    try:
        if len(table_lines) < 3:  # Need at least header, separator, and one data row
            st.markdown('\n'.join(table_lines))
            return
        
        # Extract header
        header_line = table_lines[0]
        headers = [col.strip() for col in header_line.split('|')[1:-1]]  # Remove first and last empty elements
        
        # Skip separator line (contains ---)
        data_lines = [line for line in table_lines[2:] if line and not '---' in line]
        
        # Extract data rows
        rows = []
        for line in data_lines:
            if '|' in line:
                row_data = [col.strip() for col in line.split('|')[1:-1]]  # Remove first and last empty elements
                if len(row_data) == len(headers):
                    rows.append(row_data)
        
        if rows:
            # Create DataFrame and display
            df = pd.DataFrame(rows, columns=headers)
            st.dataframe(df, use_container_width=True)
        else:
            # Fallback to markdown if parsing fails
            st.markdown('\n'.join(table_lines))
            
    except Exception as e:
        # If anything fails, just render as markdown
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
                        st.markdown(response_text)
                    else:
                        # Extract the message using our function
                        response_text = extract_message_from_response(response_data)
                        
                        # Use the new table rendering function
                        display_message_with_tables(response_text)
                    
                    # Add assistant response to chat history
                    st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})

# Add debug section only if debug mode is enabled
if st.session_state["debug_mode"]:
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
            endpoint = API_ENDPOINTS.get(st.session_state["page"], API_ENDPOINTS["Furze"])
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
        
        # Add table parsing test button - THIS IS THE MISSING BUTTON
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