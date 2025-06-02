import re
import html
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional
import streamlit as st

class InputValidator:
    """Validates and sanitizes user input to prevent injection attacks"""
    
    # Maximum input length to prevent DoS
    MAX_INPUT_LENGTH = 5000
    
    # Patterns that might indicate injection attempts
    INJECTION_PATTERNS = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'eval\s*\(',
        r'expression\s*\(',
        r'vbscript:',
        r'onload\s*=',
        r'onerror\s*=',
        r'onclick\s*=',
        r'<iframe.*?>',
        r'<object.*?>',
        r'<embed.*?>',
        r'<form.*?>',
        r'document\.',
        r'window\.',
        r'alert\s*\(',
        r'prompt\s*\(',
        r'confirm\s*\('
    ]
    
    @staticmethod
    def validate_input(user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Validates user input for security issues.
        Returns: (is_valid, error_message)
        """
        # Check if input is empty
        if not user_input or len(user_input.strip()) == 0:
            return False, "Input cannot be empty"
        
        # Check input length
        if len(user_input) > InputValidator.MAX_INPUT_LENGTH:
            return False, f"Input exceeds maximum length of {InputValidator.MAX_INPUT_LENGTH} characters"
        
        # Check for injection patterns
        for pattern in InputValidator.INJECTION_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                return False, "Invalid input detected. Please remove any code or scripts."
        
        # Check for excessive special characters (potential obfuscation)
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s\-.,!?\'\"()]', user_input)) / len(user_input)
        if special_char_ratio > 0.3:  # More than 30% special characters
            return False, "Input contains too many special characters"
        
        # Check for null bytes
        if '\x00' in user_input:
            return False, "Invalid input detected"
        
        return True, None
    
    @staticmethod
    def sanitize_input(user_input: str) -> str:
        """
        Sanitizes user input by removing potentially harmful content.
        This is applied after validation passes.
        """
        # Remove any HTML tags
        cleaned = re.sub('<.*?>', '', user_input)
        
        # Escape HTML special characters
        cleaned = html.escape(cleaned)
        
        # Remove any null bytes
        cleaned = cleaned.replace('\x00', '')
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Ensure length limit
        cleaned = cleaned[:InputValidator.MAX_INPUT_LENGTH]
        
        return cleaned


class RateLimiter:
    """Implements rate limiting to prevent DoS attacks"""
    
    def __init__(self, max_requests: int = 20, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window = timedelta(minutes=window_minutes)
        self.requests: Dict[str, list] = {}
    
    def _get_user_id(self) -> str:
        """Get a unique identifier for the current user/session"""
        # Use session ID if available, otherwise use a hash of session data
        if "user_id" not in st.session_state:
            # Create a unique ID based on session start time
            session_data = f"{st.session_state.get('session_start', time.time())}"
            st.session_state["user_id"] = hashlib.sha256(session_data.encode()).hexdigest()[:16]
        return st.session_state["user_id"]
    
    def _clean_old_requests(self):
        """Remove expired request timestamps"""
        now = datetime.now()
        for user_id in list(self.requests.keys()):
            self.requests[user_id] = [
                req_time for req_time in self.requests.get(user_id, [])
                if now - req_time < self.window
            ]
            # Remove user if no recent requests
            if not self.requests[user_id]:
                del self.requests[user_id]
    
    def is_allowed(self, identifier: Optional[str] = None) -> bool:
        """Check if a request is allowed under rate limiting rules"""
        user_id = identifier or self._get_user_id()
        now = datetime.now()
        
        # Clean old requests
        self._clean_old_requests()
        
        # Get user's recent requests
        user_requests = self.requests.get(user_id, [])
        
        # Check if limit exceeded
        if len(user_requests) >= self.max_requests:
            return False
        
        # Record this request
        if user_id not in self.requests:
            self.requests[user_id] = []
        self.requests[user_id].append(now)
        
        return True
    
    def get_wait_time(self, identifier: Optional[str] = None) -> int:
        """Get seconds until the user can make another request"""
        user_id = identifier or self._get_user_id()
        user_requests = self.requests.get(user_id, [])
        
        if len(user_requests) < self.max_requests:
            return 0
        
        # Find the oldest request in the window
        oldest_request = min(user_requests)
        wait_until = oldest_request + self.window
        wait_seconds = (wait_until - datetime.now()).total_seconds()
        
        return max(0, int(wait_seconds))


class SessionManager:
    """Manages session security and lifecycle"""
    
    # Session timeout in minutes
    SESSION_TIMEOUT_MINUTES = 60
    
    @staticmethod
    def initialize_session():
        """Initialize session with security parameters"""
        if "session_start" not in st.session_state:
            st.session_state["session_start"] = time.time()
            st.session_state["last_activity"] = time.time()
            st.session_state["session_token"] = SessionManager._generate_session_token()
    
    @staticmethod
    def _generate_session_token() -> str:
        """Generate a secure session token"""
        # Combine timestamp with random data
        token_data = f"{time.time()}{hash(time.time())}"
        return hashlib.sha256(token_data.encode()).hexdigest()
    
    @staticmethod
    def check_session_timeout() -> bool:
        """Check if session has timed out"""
        if "last_activity" not in st.session_state:
            return True
        
        timeout_seconds = SessionManager.SESSION_TIMEOUT_MINUTES * 60
        elapsed = time.time() - st.session_state["last_activity"]
        
        return elapsed > timeout_seconds
    
    @staticmethod
    def update_activity():
        """Update last activity timestamp"""
        st.session_state["last_activity"] = time.time()
    
    @staticmethod
    def clear_session():
        """Clear all session data"""
        # Preserve only essential state
        page = st.session_state.get("page", "Home")
        debug_mode = st.session_state.get("debug_mode", False)
        
        # Clear everything
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        # Restore essential state
        st.session_state["page"] = page
        st.session_state["debug_mode"] = debug_mode
        
        # Reinitialize
        SessionManager.initialize_session()


class SecurityLogger:
    """Logs security events without exposing sensitive information"""
    
    @staticmethod
    def log_error(error_type: str, details: str = None):
        """Log error without exposing system details"""
        # In production, this would log to a secure logging service
        # For now, we'll just track in session state for debugging
        if "security_logs" not in st.session_state:
            st.session_state["security_logs"] = []
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "session_id": st.session_state.get("session_token", "unknown")[:8]  # Only first 8 chars
        }
        
        # Only add details in debug mode
        if st.session_state.get("debug_mode", False) and details:
            log_entry["details"] = details[:100]  # Limit detail length
        
        st.session_state["security_logs"].append(log_entry)
        
        # Keep only last 50 logs
        st.session_state["security_logs"] = st.session_state["security_logs"][-50:]
    
    @staticmethod
    def get_safe_error_message(error: Exception) -> str:
        """Convert exception to user-safe error message"""
        error_str = str(error).lower()
        
        # Map common errors to user-friendly messages
        if "timeout" in error_str:
            return "The request took too long. Please try again."
        elif "connection" in error_str or "network" in error_str:
            return "Connection error. Please check your internet connection."
        elif "unauthorized" in error_str or "forbidden" in error_str:
            return "Access denied. Please check your permissions."
        elif "not found" in error_str:
            return "The requested resource was not found."
        elif "rate limit" in error_str:
            return "Too many requests. Please wait a moment before trying again."
        else:
            return "An error occurred. Please try again later."