import streamlit as st
import requests
import json
import time
import threading
import os
import uuid

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

# Create a place to store background job results
if "background_jobs" not in st.session_state:
    st.session_state["background_jobs"] = {}

# API endpoints for different chat modules
API_ENDPOINTS = {
    "Furze AI": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/c1dc8c3e-aa3e-483c-889a-c6b4e689c8dd",
    "Eco System Identification": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/3d9f75a3-78fd-4614-b950-fa62a036bedb",
    "Eco System + SWOT": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/243de91a-eeb9-4bec-85b6-2d6f0aa2a673",
    "Eco System + SWOT + Scenarios": "https://d186xcf3hom0xy.cloudfront.net/api/v1/run/bc6c6e43-e0d2-47c2-8cc0-82c7a606afa2"
}

# Determine which endpoints require chunking
CHUNKED_ENDPOINTS = {
    "Eco System + SWOT": True,
    "Eco System + SWOT + Scenarios": True
}

# Create a temporary directory for request chunks if it doesn't exist
TEMP_DIR = ".temp_requests"
os.makedirs(TEMP_DIR, exist_ok=True)

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

# Split long text into chunks
def chunk_text(text, max_tokens=50):
    words = text.split()
    chunks = []
    current_chunk = []
    
    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
    
    # Add any remaining words
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

# Function to make API request for a single chunk
def process_chunk(chunk, endpoint, job_id, chunk_index, total_chunks):
    # Modify the prompt to indicate it's part of a larger query
    modified_prompt = f"[PART {chunk_index+1}/{total_chunks}] {chunk}"
    
    payload = {
        "input_value": modified_prompt,
        "output_type": "chat",
        "input_type": "chat"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Use a shorter timeout to avoid gateway timeouts
        response = requests.post(endpoint, json=payload, headers=headers, timeout=60)
        response_data = response.json()
        
        # Extract the message and save it to a temporary file
        message = extract_message_from_response(response_data)
        
        # Save this chunk's result to a file
        with open(f"{TEMP_DIR}/{job_id}_{chunk_index}.json", "w") as f:
            json.dump({"chunk_index": chunk_index, "message": message}, f)
        
        return True
    except Exception as e:
        # If there's an error, save the error message
        with open(f"{TEMP_DIR}/{job_id}_{chunk_index}.error", "w") as f:
            json.dump({"chunk_index": chunk_index, "error": str(e)}, f)
        
        return False

# Background job to process all chunks
def process_all_chunks(prompt, endpoint, job_id, current_page):
    try:
        # Check if this is a chunked endpoint
        if current_page in CHUNKED_ENDPOINTS and CHUNKED_ENDPOINTS[current_page]:
            # Split the prompt into smaller chunks
            chunks = chunk_text(prompt, max_tokens=50)
            
            # Process each chunk in a separate request
            results = []
            for i, chunk in enumerate(chunks):
                # Update job status to show progress
                st.session_state["background_jobs"][job_id]["status"] = "processing"
                st.session_state["background_jobs"][job_id]["progress"] = (i / len(chunks)) * 100
                
                # Process this chunk
                success = process_chunk(chunk, endpoint, job_id, i, len(chunks))
                results.append(success)
            
            # Combine all chunk results
            combined_message = ""
            for i in range(len(chunks)):
                chunk_file = f"{TEMP_DIR}/{job_id}_{i}.json"
                if os.path.exists(chunk_file):
                    with open(chunk_file, "r") as f:
                        chunk_data = json.load(f)
                        combined_message += chunk_data["message"] + "\n\n"
            
            # Clean up temporary files
            for i in range(len(chunks)):
                if os.path.exists(f"{TEMP_DIR}/{job_id}_{i}.json"):
                    os.remove(f"{TEMP_DIR}/{job_id}_{i}.json")
                if os.path.exists(f"{TEMP_DIR}/{job_id}_{i}.error"):
                    os.remove(f"{TEMP_DIR}/{job_id}_{i}.error")
            
            # Update job status to complete
            st.session_state["background_jobs"][job_id]["status"] = "complete"
            st.session_state["background_jobs"][job_id]["message"] = combined_message
        else:
            # For non-chunked endpoints, make a regular request
            payload = {
                "input_value": prompt,
                "output_type": "chat",
                "input_type": "chat"
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Use a longer timeout for non-chunked requests
            response = requests.post(endpoint, json=payload, headers=headers, timeout=120)
            response_data = response.json()
            
            # Extract the message
            message = extract_message_from_response(response_data)
            
            # Update job status to complete
            st.session_state["background_jobs"][job_id]["status"] = "complete"
            st.session_state["background_jobs"][job_id]["message"] = message
    
    except Exception as e:
        # Update job status to error
        st.session_state["background_jobs"][job_id]["status"] = "error"
        st.session_state["background_jobs"][job_id]["error"] = str(e)

# Function to start a background job
def start_background_job(prompt, endpoint, current_page):
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Create a job entry in the session state
    st.session_state["background_jobs"][job_id] = {
        "status": "starting",
        "progress": 0,
        "prompt": prompt,
        "page": current_page,
        "start_time": time.time()
    }
    
    # Start a background thread to process the job
    thread = threading.Thread(
        target=process_all_chunks,
        args=(prompt, endpoint, job_id, current_page)
    )
    thread.start()
    
    return job_id

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

elif st.session_state["page"] in ["Furze AI", "Eco System Identification", "Eco System + SWOT", "Eco System + SWOT + Scenarios"]:
    current_page = st.session_state["page"]
    endpoint = API_ENDPOINTS[current_page]
    
    # Page specific headers
    if current_page == "Furze AI":
        st.title("🌿 Furze AI")
        st.write("""
        Welcome to Furze. Furze is designed by Firehills as your AI assistant for Eco systems and trained on 
        public organisational data and designed for exploring performance and growth. Explore and flourish!
        """)
    
    elif current_page == "Eco System Identification":
        st.title("🌿 Eco System Identification")
        st.write("""
        Systems thinking needs complex technology to create simple strategies for growth. 
        This AI agent has been trained on Firehills Eco system IP framework and will explore the roles 
        organisation play today. And some they don't. **Ensure that organisational data has been 
        uploaded in advance to get the best results.**
        """)
    
    elif current_page == "Eco System + SWOT":
        st.title("🌿 Eco System + SWOT")
        st.write("""
        This AI Agent will build your Eco System mapping against roles, but go one step further and 
        produce a SWOT related to their roles and them as an organisation. **Ensure that organisational 
        data has been uploaded in advance to get the best results.**
        """)
        
        # Show processing time warning for SWOT pages
        st.warning("⚠️ This analysis can take up to 10 minutes to complete due to its complexity. The system will break it into smaller parts to avoid timeout errors.")
    
    elif current_page == "Eco System + SWOT + Scenarios":
        st.title("🌿 Eco System + SWOT + Scenarios")
        st.write("""
        This AI Agent will build your Eco System mapping against roles, SWOT and also create scenarios for growth. 
        Scenarios are build out on an organic, in-organic and creative basis. **Ensure that organisational 
        data has been uploaded in advance to get the best results.**
        """)
        
        # Show processing time warning for SWOT + Scenarios page
        st.warning("⚠️ This comprehensive analysis can take up to 10 minutes to complete. The system will break it into smaller parts to avoid timeout errors.")
    
    # Display chat messages from history
    for message in st.session_state["messages"][current_page]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Check for any pending jobs for this page
    active_jobs = [job_id for job_id, job in st.session_state["background_jobs"].items() 
                   if job["page"] == current_page and job["status"] in ["starting", "processing"]]
    
    # If there's an active job, show its progress
    if active_jobs:
        job_id = active_jobs[0]
        job = st.session_state["background_jobs"][job_id]
        
        with st.chat_message("assistant"):
            # Show a progress indicator
            if job["status"] == "starting":
                st.info("Starting your request...")
                st.progress(0.1)
            elif job["status"] == "processing":
                progress = job["progress"] / 100
                st.progress(max(0.1, progress))
                st.info(f"Processing your request... {int(job['progress'])}% complete")
            
            # Auto-refresh the page to check progress
            time.sleep(1)  # Small delay to prevent too rapid refreshes
            st.rerun()  # Using st.rerun() instead of st.experimental_rerun()
    
    # Check for any completed jobs for this page
    completed_jobs = [job_id for job_id, job in st.session_state["background_jobs"].items() 
                      if job["page"] == current_page and job["status"] == "complete"]
    
    # If there's a completed job, display its result
    if completed_jobs:
        job_id = completed_jobs[0]
        job = st.session_state["background_jobs"][job_id]
        
        # Add the response to chat history
        st.session_state["messages"][current_page].append({"role": "assistant", "content": job["message"]})
        
        # Remove the job from session state
        del st.session_state["background_jobs"][job_id]
        
        # Rerun to update the UI
        st.rerun()  # Using st.rerun() instead of st.experimental_rerun()
    
    # Check for any error jobs for this page
    error_jobs = [job_id for job_id, job in st.session_state["background_jobs"].items() 
                 if job["page"] == current_page and job["status"] == "error"]
    
    # If there's an error job, display the error
    if error_jobs:
        job_id = error_jobs[0]
        job = st.session_state["background_jobs"][job_id]
        
        # Add the error to chat history
        error_message = f"Sorry, I encountered an error: {job.get('error', 'Unknown error')}"
        st.session_state["messages"][current_page].append({"role": "assistant", "content": error_message})
        
        # Remove the job from session state
        del st.session_state["background_jobs"][job_id]
        
        # Rerun to update the UI
        st.rerun()  # Using st.rerun() instead of st.experimental_rerun()
    
    # Chat input
    if prompt := st.chat_input("What would you like to ask?"):
        # Add user message to chat history
        st.session_state["messages"][current_page].append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Start a background job to process the user input
        job_id = start_background_job(prompt, endpoint, current_page)
        
        # Display a progress indicator
        with st.chat_message("assistant"):
            st.info("Processing your request...")
            st.progress(0.05)
        
        # Rerun to start the progress updates
        st.rerun()  # Using st.rerun() instead of st.experimental_rerun()

# Add debug section to help troubleshoot
with st.expander("Debug Information (Expand to see)"):
    st.write("Current Page:", st.session_state["page"])
    st.write("Session State Keys:", list(st.session_state.keys()))
    st.write("Messages Per Page:", {page: len(messages) for page, messages in st.session_state["messages"].items()})
    st.write("Active Background Jobs:", len(st.session_state["background_jobs"]))
    
    # Show details of active jobs
    if st.session_state["background_jobs"]:
        st.write("Background Jobs:")
        for job_id, job in st.session_state["background_jobs"].items():
            st.write(f"  - Job {job_id}: {job['status']} ({job['page']})")
            if "progress" in job:
                st.write(f"    Progress: {job['progress']}%")
            if "error" in job:
                st.write(f"    Error: {job['error']}")