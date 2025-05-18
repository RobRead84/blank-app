import streamlit as st
import requests
import json
import base64
from io import BytesIO

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

# API endpoints for different chat modules
API_ENDPOINTS = {
    "Furze AI": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/c1dc8c3e-aa3e-483c-889a-c6b4e689c8dd",
    "Eco System Identification": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/c1dc8c3e-aa3e-483c-889a-c6b4e689c8dd", # Replace with actual endpoint
    "Eco System + SWOT": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/c1dc8c3e-aa3e-483c-889a-c6b4e689c8dd", # Replace with actual endpoint
    "Eco System + SWOT + Scenarios": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/c1dc8c3e-aa3e-483c-889a-c6b4e689c8dd" # Replace with actual endpoint
}

# Document upload endpoints
VECTOR_STORE_API = "https://your-vector-store-api-endpoint.com" # Replace with actual endpoint

# Function to get base64 encoded image
def get_furze_image():
    # Using a placeholder furze image URL
    response = requests.get("https://www.irishtimes.com/resizer/eZ0qeT3pBX2ZA42LkflAXl18tXc=/1600x0/filters:format(jpg):quality(70)/cloudfront-eu-central-1.images.arcpublishing.com/irishtimes/BBQE6Q5IXJQJNXGN5NXPOGRZOA.jpg")
    img = BytesIO(response.content)
    encoded = base64.b64encode(img.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"

# Sidebar for navigation
with st.sidebar:
    # Add Furze image as icon
    st.image(get_furze_image(), width=100)
    
    # Navigation
    st.title("Navigation")
    for page in ["Home", "Furze AI", "Eco System Identification", "Eco System + SWOT", "Eco System + SWOT + Scenarios"]:
        if st.button(page, key=f"nav_{page}"):
            st.session_state["page"] = page
    
    # Upload section
    st.title("Upload Documents")
    uploaded_file = st.file_uploader("Upload documents for vector store", type=["pdf", "txt", "docx"])
    
    if uploaded_file is not None:
        with st.spinner("Uploading document to vector store..."):
            # Save the uploaded file to vector store
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                response = requests.post(f"{VECTOR_STORE_API}/upload", files=files)
                if response.status_code == 200:
                    st.success("Document uploaded successfully!")
                else:
                    st.error(f"Failed to upload document: {response.text}")
            except Exception as e:
                st.error(f"Error uploading document: {str(e)}")
    
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

# Function to call LangFlow API
def query_langflow(user_input, endpoint):
    payload = {
        "input_value": user_input,
        "output_type": "chat",
        "input_type": "chat"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Request Error: {e}")
        return {"error": str(e)}
    except ValueError as e:
        st.error(f"Response Parsing Error: {e}")
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

elif st.session_state["page"] == "Furze AI":
    st.title("🌿 Furze AI")
    st.write("""
    Welcome to Furze. Furze is designed by Firehills as your AI assistant for Eco systems and trained on 
    public organisational data and designed for exploring performance and growth. Explore and flourish!
    """)
    
    # Chat functionality
    current_page = st.session_state["page"]
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
            with st.spinner("Thinking..."):
                response_data = query_langflow(prompt, endpoint)
                
                if "error" in response_data:
                    response_text = f"Sorry, I encountered an error: {response_data['error']}"
                else:
                    # Extract the message using our function
                    response_text = extract_message_from_response(response_data)
                
                message_placeholder.markdown(response_text)
                
                # Add assistant response to chat history
                st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})

elif st.session_state["page"] == "Eco System Identification":
    st.title("🌿 Eco System Identification")
    st.write("""
    Systems thinking needs complex technology to create simple strategies for growth. 
    This AI agent has been trained on Firehills Eco system IP framework and will explore the roles 
    organisation play today. And some they don't. **Ensure that organisational data has been 
    uploaded in advance to get the best results.**
    """)
    
    # Chat functionality
    current_page = st.session_state["page"]
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
            with st.spinner("Thinking..."):
                response_data = query_langflow(prompt, endpoint)
                
                if "error" in response_data:
                    response_text = f"Sorry, I encountered an error: {response_data['error']}"
                else:
                    # Extract the message using our function
                    response_text = extract_message_from_response(response_data)
                
                message_placeholder.markdown(response_text)
                
                # Add assistant response to chat history
                st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})

elif st.session_state["page"] == "Eco System + SWOT":
    st.title("🌿 Eco System + SWOT")
    st.write("""
    This AI Agent will build your Eco System mapping against roles, but go one step further and 
    produce a SWOT related to their roles and them as an organisation. **Ensure that organisational 
    data has been uploaded in advance to get the best results.**
    """)
    
    # Chat functionality
    current_page = st.session_state["page"]
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
            with st.spinner("Thinking..."):
                response_data = query_langflow(prompt, endpoint)
                
                if "error" in response_data:
                    response_text = f"Sorry, I encountered an error: {response_data['error']}"
                else:
                    # Extract the message using our function
                    response_text = extract_message_from_response(response_data)
                
                message_placeholder.markdown(response_text)
                
                # Add assistant response to chat history
                st.session_state["messages"][current_page].append({"role": "assistant", "content": response_text})

elif st.session_state["page"] == "Eco System + SWOT + Scenarios":
    st.title("🌿 Eco System + SWOT + Scenarios")
    st.write("""
    This AI Agent will build your Eco System mapping against roles, SWOT and also create scenarios for growth. 
    Scenarios are build out on an organic, in-organic and creative basis. **Ensure that organisational 
    data has been uploaded in advance to get the best results.**
    """)
    
    # Chat functionality
    current_page = st.session_state["page"]
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
            with st.spinner("Thinking..."):
                response_data = query_langflow(prompt, endpoint)
                
                if "error" in response_data:
                    response_text = f"Sorry, I encountered an error: {response_data['error']}"
                else:
                    # Extract the message using our function
                    response_text = extract_message_from_response(response_data)
                
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