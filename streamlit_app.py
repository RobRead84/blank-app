import streamlit as st
import requests
import json
import time

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

# Updated API endpoints for different chat modules with increased timeout parameters
# Using the web-server urls instead of CloudFront URLs
API_ENDPOINTS = {
    "Furze AI": "https://web-server-5a231649.fctl.app/api/v1/run/955fa9ff-6d55-4e7a-9eeb-ec15ef656fab",
    "Eco System Identification": "https://web-server-5a231649.fctl.app/api/v1/run/c8744f17-0887-4980-a5a2-ceca69ce552d",
    "Eco System + SWOT": "https://web-server-5a231649.fctl.app/api/v1/run/82dbd031-ae3b-46fb-b6d0-82fec50ac844",
    "Eco System + SWOT + Scenarios": "https://web-server-5a231649.fctl.app/api/v1/run/b362ee31-f35a-4f72-8751-7c38dad04625"
}

# Request timeout settings (in seconds)
# Increase these values to prevent timeouts with long-running API calls
CONNECT_TIMEOUT = 10.0  # Connection timeout
READ_TIMEOUT = 300.0    # Read timeout - increased to 5 minutes

# Sidebar for navigation
with st.sidebar:
    # Use a simple icon for Furze
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

# Function to stream response from LangFlow API (using simulated streaming since the API might not support real streaming)
def query_langflow_streaming(user_input, endpoint, message_placeholder):
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
        # Add progress indicator for user awareness
        progress_bar = st.progress(0)
        message_placeholder.markdown("Initializing request...")
        
        # Make the request with explicit timeouts to prevent 504 errors
        # First update to show request is being made
        message_placeholder.markdown("Sending request to API... This may take a minute or two for complex queries.")
        progress_bar.progress(10)
        
        # Make the actual request with extended timeouts
        response = requests.post(
            endpoint, 
            json=payload, 
            headers=headers, 
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),  # (connect timeout, read timeout)
            allow_redirects=False  # Try to prevent redirects to CloudFront
        )
        
        progress_bar.progress(50)
        message_placeholder.markdown("Processing response...")
        
        # Check for redirect - if redirected, we'll use the direct URL we want
        if response.status_code in (301, 302, 303, 307, 308):
            message_placeholder.markdown("Redirect detected. Trying direct connection...")
            # Get the real URL from our mapping - use the original endpoint
            response = requests.post(
                endpoint, 
                json=payload, 
                headers=headers, 
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
        
        response.raise_for_status()
        progress_bar.progress(75)
        
        # Since we might not have actual streaming from the API,
        # we'll get the full response and then simulate streaming
        full_response = response.json()
        
        if "error" in full_response:
            message_placeholder.markdown(f"Sorry, I encountered an error: {full_response['error']}")
            progress_bar.progress(100)
            return full_response
        
        # Extract the message
        response_text = extract_message_from_response(full_response)
        progress_bar.progress(90)
        
        # Simulate streaming by displaying the response word by word
        # This gives a better user experience while we wait for the response
        words = response_text.split()
        displayed_text = ""
        
        for i, word in enumerate(words):
            displayed_text += word + " "
            # Update every few words to give a streaming effect
            if i % 3 == 0 or i == len(words) - 1:
                message_placeholder.markdown(displayed_text)
                time.sleep(0.05)  # Small delay to simulate typing
        
        progress_bar.progress(100)
        # Remove the progress bar after completion
        progress_bar.empty()
        
        return full_response
            
    except requests.exceptions.Timeout as e:
        error_message = f"API Request Timeout: The server is taking too long to respond. This might be due to a complex query or server load. Details: {e}"
        message_placeholder.markdown(error_message)
        if 'progress_bar' in locals():
            progress_bar.empty()
        return {"error": str(e)}
    except requests.exceptions.RequestException as e:
        error_message = f"API Request Error: {e}"
        message_placeholder.markdown(error_message)
        if 'progress_bar' in locals():
            progress_bar.empty()
        return {"error": str(e)}
    except ValueError as e:
        error_message = f"Response Parsing Error: {e}"
        message_placeholder.markdown(error_message)
        if 'progress_bar' in locals():
            progress_bar.empty()
        return {"error": str(e)}
    except Exception as e:
        error_message = f"Unexpected Error: {e}"
        message_placeholder.markdown(error_message)
        if 'progress_bar' in locals():
            progress_bar.empty()
        return {"error": str(e)}

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
        
        # Add information about potential processing time
        st.info("Note: Complex queries may take several minutes to process. Please be patient while the AI generates a response.")
        
        # Get the appropriate endpoint
        endpoint = API_ENDPOINTS[current_page]
        
        # Display chat messages from history
        for message in st.session_state["messages"][current_page]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("What would you like to ask?"):
            # Add user message to chat history
            st.session_state["messages"][current_page].append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response with a spinner while processing
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                # Use the streaming function instead
                with st.spinner("Thinking..."):
                    response_data = query_langflow_streaming(prompt, endpoint, message_placeholder)
                    
                    if "error" in response_data:
                        response_text = f"Sorry, I encountered an error: {response_data['error']}"
                    else:
                        # Extract the message using our function
                        response_text = extract_message_from_response(response_data)
                    
                    # The message has already been displayed by the streaming function,
                    # but we'll make sure it's the complete message
                    message_placeholder.markdown(response_text)
                    
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