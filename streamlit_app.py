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

# Updated API endpoints for different chat modules based on the provided code
API_ENDPOINTS = {
    "Furze AI": "https://web-server-5a231649.fctl.app/api/v1/run/955fa9ff-6d55-4e7a-9eeb-ec15ef656fab",
    "Eco System Identification": "https://web-server-5a231649.fctl.app/api/v1/run/c8744f17-0887-4980-a5a2-ceca69ce552d",
    "Eco System + SWOT": "https://web-server-5a231649.fctl.app/api/v1/run/82dbd031-ae3b-46fb-b6d0-82fec50ac844",
    "Eco System + SWOT + Scenarios": "https://web-server-5a231649.fctl.app/api/v1/run/b362ee31-f35a-4f72-8751-7c38dad04625"
}

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
        "Content-Type": "application/json"
    }
    
    try:
        # Make the request
        with requests.post(endpoint, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()
            
            # Since we might not have actual streaming from the API,
            # we'll get the full response and then simulate streaming
            full_response = response.json()
            
            if "error" in full_response:
                message_placeholder.markdown(f"Sorry, I encountered an error: {full_response['error']}")
                return full_response
            
            # Extract the message
            response_text = extract_message_from_response(full_response)
            
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
            
            return full_response
            
    except requests.exceptions.RequestException as e:
        error_message = f"API Request Error: {e}"
        message_placeholder.markdown(error_message)
        return {"error": str(e)}
    except ValueError as e:
        error_message = f"Response Parsing Error: {e}"
        message_placeholder.markdown(error_message)
        return {"error": str(e)}

# Content for each page
if st.session_state["page"] == "Home":
    st.title("Furze from Firehills")
    st.write("""
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. 
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
    """)
    
    st.write("""
    Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. 
    Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
    """)
    
    st.write("""
    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. 
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
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