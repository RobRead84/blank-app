import streamlit as st
import requests
import json

# Set page config and title
st.set_page_config(page_title="LangFlow Chat", page_icon="🤖")
st.title("🤖 LangFlow Chat Interface")

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# LangFlow API endpoint
API_URL = "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/c1dc8c3e-aa3e-483c-889a-c6b4e689c8dd"

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Display assistant response with a spinner while processing
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_data = query_langflow(prompt)
            
            if "error" in response_data:
                response_text = f"Sorry, I encountered an error: {response_data['error']}"
            else:
                # Extract the assistant's message from the response
                # Adjust this based on the actual structure of your LangFlow API response
                try:
                    # This assumes the response contains a field like 'response', 'answer', or 'text'
                    # You may need to modify this based on the actual structure
                    if isinstance(response_data, dict):
                        if "response" in response_data:
                            response_text = response_data["response"]
                        elif "answer" in response_data:
                            response_text = response_data["answer"]
                        elif "text" in response_data:
                            response_text = response_data["text"]
                        elif "output" in response_data:
                            response_text = response_data["output"]
                        else:
                            # Fallback: display the full response as text
                            response_text = json.dumps(response_data, indent=2)
                    elif isinstance(response_data, str):
                        response_text = response_data
                    else:
                        response_text = str(response_data)
                except Exception as e:
                    response_text = f"Error formatting response: {str(e)}\nRaw response: {str(response_data)}"
            
            st.markdown(response_text)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response_text})

# Add some helpful information at the bottom
st.sidebar.title("About")
st.sidebar.info(
    "This is a chat interface for your LangFlow model. "
    "Enter your questions or prompts in the chat input below."
)