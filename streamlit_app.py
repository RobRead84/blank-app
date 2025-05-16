import streamlit as st
import requests
import json

# Set page config and title
st.set_page_config(page_title="Furze AI", page_icon="🤖")
st.title("🤖 Furze AI")

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state["messages"] = []  # Use dictionary syntax for safety

# LangFlow API endpoint
API_URL = "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/c1dc8c3e-aa3e-483c-889a-c6b4e689c8dd"

# Display chat messages from history
for message in st.session_state["messages"]:  # Use dictionary syntax
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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

# Function to call LangFlow API
def query_langflow(user_input):
    payload = {
        "input_value": user_input,
        "output_type": "chat",
        "input_type": "chat"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Request Error: {e}")
        return {"error": str(e)}
    except ValueError as e:
        st.error(f"Response Parsing Error: {e}")
        return {"error": str(e)}

# Chat input
if prompt := st.chat_input("What would you like to ask?"):
    # Add user message to chat history - use dictionary syntax for safety
    st.session_state["messages"].append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Display assistant response with a spinner while processing
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("Thinking..."):
            response_data = query_langflow(prompt)
            
            if "error" in response_data:
                response_text = f"Sorry, I encountered an error: {response_data['error']}"
            else:
                # Extract the message using our new function
                response_text = extract_message_from_response(response_data)
            
            message_placeholder.markdown(response_text)
            
            # Add assistant response to chat history - use dictionary syntax
            st.session_state["messages"].append({"role": "assistant", "content": response_text})

# Add some helpful information at the bottom
st.sidebar.title("About")
st.sidebar.info(
    "This is a chat interface for Furze AI. "
    "Enter your questions or prompts in the chat input below."
)

# Add debug section to help troubleshoot
with st.expander("Debug Information (Expand to see)"):
    st.write("Session State Keys:", list(st.session_state.keys()))
    st.write("Messages Count:", len(st.session_state["messages"]) if "messages" in st.session_state else 0)
    st.write("API URL:", API_URL)