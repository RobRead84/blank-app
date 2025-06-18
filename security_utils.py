import re
import html
import time
import hashlib
import hmac
import uuid
import secrets
import threading
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional, Set
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
        r'confirm\s*\(',
        r'exec\s*\(',
        r'system\s*\(',
        r'shell\s*\(',
        r'import\s+os',
        r'__import__',
        r'subprocess',
        r'pickle\.loads',
        r'marshal\.loads',
        r'base64\.decode'
    ]
    
    # Additional patterns for SQL injection detection
    SQL_INJECTION_PATTERNS = [
        r'union\s+select',
        r'drop\s+table',
        r'delete\s+from',
        r'insert\s+into',
        r'update\s+set',
        r'alter\s+table',
        r'create\s+table',
        r'exec\s*\(',
        r'sp_executesql',
        r'xp_cmdshell',
        r'--\s*$',
        r'/\*.*?\*/',
        r';\s*drop',
        r';\s*delete',
        r';\s*update'
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
        
        # Check for XSS injection patterns
        for pattern in InputValidator.INJECTION_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                SecurityLogger.log_security_event("xss_attempt", pattern[:50])
                return False, "Invalid input detected. Please remove any code or scripts."
        
        # Check for SQL injection patterns
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                SecurityLogger.log_security_event("sql_injection_attempt", pattern[:50])
                return False, "Invalid input detected. Please remove any SQL commands."
        
        # Check for excessive special characters (potential obfuscation)
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s\-.,!?\'\"()]', user_input)) / len(user_input)
        if special_char_ratio > 0.3:  # More than 30% special characters
            return False, "Input contains too many special characters"
        
        # Check for null bytes and other control characters
        if any(ord(char) < 32 and char not in '\t\n\r' for char in user_input):
            return False, "Invalid input detected"
        
        # Check for extremely long words (potential buffer overflow attempts)
        words = user_input.split()
        if any(len(word) > 100 for word in words):
            return False, "Input contains excessively long words"
        
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
        
        # Remove any null bytes and control characters
        cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\t\n\r')
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Ensure length limit
        cleaned = cleaned[:InputValidator.MAX_INPUT_LENGTH]
        
        return cleaned
    
    @staticmethod
    def validate_file_input(filename: str, allowed_extensions: Set[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validates file uploads for security.
        """
        if not filename:
            return False, "Filename cannot be empty"
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False, "Invalid filename detected"
        
        # Check file extension if restrictions apply
        if allowed_extensions:
            file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
            if file_ext not in allowed_extensions:
                return False, f"File type .{file_ext} not allowed"
        
        # Check for executable extensions
        dangerous_extensions = {'exe', 'bat', 'cmd', 'com', 'scr', 'pif', 'jar', 'app', 'deb', 'pkg', 'dmg'}
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        if file_ext in dangerous_extensions:
            return False, "Executable files are not allowed"
        
        return True, None


class RateLimiter:
    """Implements rate limiting to prevent DoS attacks with improved user identification"""
    
    def __init__(self, max_requests: int = 20, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window = timedelta(minutes=window_minutes)
        self.requests: Dict[str, list] = {}
        self._lock = threading.Lock()  # Thread safety for concurrent requests
    
    def _get_user_id(self) -> str:
        """Get a unique identifier for the current user/session"""
        if "user_id" not in st.session_state:
            # Create a unique ID with multiple entropy sources
            entropy_sources = [
                str(time.time_ns()),              # Nanosecond precision timestamp
                secrets.token_hex(16),            # Cryptographically secure random bytes
                str(uuid.uuid4()),                # UUID4 for additional uniqueness
                str(hash(id(st.session_state))),  # Memory address hash
                secrets.token_urlsafe(8)          # Additional URL-safe random token
            ]
            
            # Combine all entropy sources
            combined_entropy = ''.join(entropy_sources)
            
            # Create hash and return first 16 characters
            st.session_state["user_id"] = hashlib.sha256(combined_entropy.encode()).hexdigest()[:16]
        
        return st.session_state["user_id"]
    
    def _clean_old_requests(self):
        """Remove expired request timestamps"""
        now = datetime.now()
        with self._lock:
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
        
        with self._lock:
            # Get user's recent requests
            user_requests = self.requests.get(user_id, [])
            
            # Check if limit exceeded
            if len(user_requests) >= self.max_requests:
                SecurityLogger.log_security_event("rate_limit_exceeded", user_id[:8])
                return False
            
            # Record this request
            if user_id not in self.requests:
                self.requests[user_id] = []
            self.requests[user_id].append(now)
        
        return True
    
    def get_wait_time(self, identifier: Optional[str] = None) -> int:
        """Get seconds until the user can make another request"""
        user_id = identifier or self._get_user_id()
        
        with self._lock:
            user_requests = self.requests.get(user_id, [])
            
            if len(user_requests) < self.max_requests:
                return 0
            
            # Find the oldest request in the window
            oldest_request = min(user_requests)
            wait_until = oldest_request + self.window
            wait_seconds = (wait_until - datetime.now()).total_seconds()
        
        return max(0, int(wait_seconds))
    
    def get_request_count(self, identifier: Optional[str] = None) -> int:
        """Get current request count for user"""
        user_id = identifier or self._get_user_id()
        self._clean_old_requests()
        
        with self._lock:
            return len(self.requests.get(user_id, []))


class SessionManager:
    """Enhanced session security and lifecycle management"""
    
    # Session timeout in minutes
    SESSION_TIMEOUT_MINUTES = 60
    
    # Maximum sessions per IP (if we could track it)
    MAX_SESSIONS_PER_USER = 5
    
    @staticmethod
    def initialize_session():
        """Initialize session with enhanced security parameters"""
        if "session_start" not in st.session_state:
            st.session_state["session_start"] = time.time()
            st.session_state["last_activity"] = time.time()
            st.session_state["session_token"] = SessionManager._generate_session_token()
            st.session_state["session_id"] = SessionManager._generate_session_id()
            st.session_state["session_integrity_hash"] = SessionManager._generate_integrity_hash()
            
            # Log session creation
            SecurityLogger.log_security_event("session_created", st.session_state["session_id"][:8])
    
    @staticmethod
    def _generate_session_token() -> str:
        """Generate a cryptographically secure session token using UUID4"""
        return str(uuid.uuid4())
    
    @staticmethod
    def _generate_session_id() -> str:
        """Generate a shorter session ID for logging purposes"""
        return secrets.token_urlsafe(12)  # 96 bits of entropy
    
    @staticmethod
    def _generate_integrity_hash() -> str:
        """Generate hash to verify session integrity"""
        session_data = {
            'start_time': st.session_state.get("session_start"),
            'token': st.session_state.get("session_token"),
            'id': st.session_state.get("session_id")
        }
        
        # Create HMAC for integrity verification
        secret_key = secrets.token_bytes(32)  # In production, use a fixed secret
        message = str(session_data).encode()
        return hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    
    @staticmethod
    def check_session_timeout() -> bool:
        """Check if session has timed out"""
        if "last_activity" not in st.session_state:
            return True
        
        timeout_seconds = SessionManager.SESSION_TIMEOUT_MINUTES * 60
        elapsed = time.time() - st.session_state["last_activity"]
        
        if elapsed > timeout_seconds:
            SecurityLogger.log_security_event("session_timeout", 
                                             st.session_state.get("session_id", "unknown")[:8])
            return True
        
        return False
    
    @staticmethod
    def check_session_integrity() -> bool:
        """Verify session hasn't been tampered with"""
        try:
            required_fields = ["session_start", "session_token", "session_id", "session_integrity_hash"]
            if not all(field in st.session_state for field in required_fields):
                return False
            
            # In a full implementation, you'd verify the HMAC here
            # For now, just check that critical fields exist and are reasonable
            
            session_age = time.time() - st.session_state["session_start"]
            if session_age < 0 or session_age > (24 * 60 * 60):  # Max 24 hours
                return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def update_activity():
        """Update last activity timestamp"""
        st.session_state["last_activity"] = time.time()
    
    @staticmethod
    def clear_session():
        """Clear all session data securely"""
        # Log session destruction
        session_id = st.session_state.get("session_id", "unknown")
        SecurityLogger.log_security_event("session_destroyed", session_id[:8])
        
        # Preserve only essential state
        page = st.session_state.get("page", "Home")
        debug_mode = st.session_state.get("debug_mode", False)
        
        # Clear everything
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        # Restore essential state
        st.session_state["page"] = page
        st.session_state["debug_mode"] = debug_mode
        
        # Reinitialize with new session
        SessionManager.initialize_session()
    
    @staticmethod
    def get_session_info() -> Dict:
        """Get safe session information for debugging"""
        return {
            "session_id": st.session_state.get("session_id", "unknown")[:8] + "...",
            "session_age_minutes": round((time.time() - st.session_state.get("session_start", time.time())) / 60, 2),
            "last_activity_minutes_ago": round((time.time() - st.session_state.get("last_activity", time.time())) / 60, 2),
            "session_valid": SessionManager.check_session_integrity(),
            "timeout_minutes": SessionManager.SESSION_TIMEOUT_MINUTES
        }


class SecurityLogger:
    """Enhanced security logging without exposing sensitive information"""
    
    # Maximum log entries to keep in memory
    MAX_LOG_ENTRIES = 100
    
    @staticmethod
    def log_security_event(event_type: str, details: str = None, severity: str = "INFO"):
        """Log security event with enhanced categorization"""
        # Initialize logs if not present
        if "security_logs" not in st.session_state:
            st.session_state["security_logs"] = []
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "severity": severity,
            "session_id": st.session_state.get("session_id", "unknown")[:8],
            "user_id": st.session_state.get("user_id", "unknown")[:8]
        }
        
        # Only add details in debug mode and limit length
        if st.session_state.get("debug_mode", False) and details:
            log_entry["details"] = str(details)[:100]
        
        st.session_state["security_logs"].append(log_entry)
        
        # Keep only recent logs
        st.session_state["security_logs"] = st.session_state["security_logs"][-SecurityLogger.MAX_LOG_ENTRIES:]
        
        # In production, also log to external system here
        SecurityLogger._log_to_external_system(log_entry)
    
    @staticmethod
    def _log_to_external_system(log_entry: Dict):
        """Log to external system (placeholder for production implementation)"""
        # In production, this would send logs to:
        # - CloudWatch, Datadog, Splunk, etc.
        # - Security Information and Event Management (SIEM) systems
        # - Internal logging infrastructure
        pass
    
    @staticmethod
    def log_error(error_type: str, details: str = None):
        """Log error without exposing system details (legacy compatibility)"""
        SecurityLogger.log_security_event(error_type, details, "ERROR")
    
    @staticmethod
    def get_safe_error_message(error: Exception) -> str:
        """Convert exception to user-safe error message"""
        error_str = str(error).lower()
        
        # Map common errors to user-friendly messages
        error_mappings = {
            "timeout": "The request took too long. Please try again.",
            "connection": "Connection error. Please check your internet connection.",
            "network": "Network error. Please check your internet connection.",
            "unauthorized": "Access denied. Please check your permissions.",
            "forbidden": "Access denied. Please check your permissions.",
            "not found": "The requested resource was not found.",
            "rate limit": "Too many requests. Please wait a moment before trying again.",
            "invalid input": "Invalid input provided. Please check your data.",
            "file not found": "The requested file was not found.",
            "permission denied": "Permission denied. Please check your access rights.",
            "service unavailable": "Service temporarily unavailable. Please try again later."
        }
        
        for keyword, message in error_mappings.items():
            if keyword in error_str:
                return message
        
        # Default safe message
        return "An error occurred. Please try again later."
    
    @staticmethod
    def get_security_summary() -> Dict:
        """Get summary of security events"""
        logs = st.session_state.get("security_logs", [])
        
        if not logs:
            return {"total_events": 0, "recent_events": 0, "event_types": {}}
        
        # Count events by type
        event_types = {}
        recent_events = 0
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        for log in logs:
            event_type = log.get("type", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1
            
            # Count recent events
            try:
                event_time = datetime.fromisoformat(log["timestamp"])
                if event_time > one_hour_ago:
                    recent_events += 1
            except (ValueError, KeyError):
                pass
        
        return {
            "total_events": len(logs),
            "recent_events": recent_events,
            "event_types": event_types,
            "session_age_minutes": round((time.time() - st.session_state.get("session_start", time.time())) / 60, 2)
        }


class SecurityValidator:
    """Additional security validation utilities"""
    
    @staticmethod
    def validate_api_response(response_data: any) -> bool:
        """Validate API response for security issues"""
        try:
            # Check if response is reasonable size (prevent memory exhaustion)
            response_str = str(response_data)
            if len(response_str) > 1_000_000:  # 1MB limit
                SecurityLogger.log_security_event("oversized_response", f"Size: {len(response_str)}", "WARNING")
                return False
            
            # Check for suspicious patterns in response
            suspicious_patterns = [
                r'<script.*?>',
                r'javascript:',
                r'data:.*base64',
                r'file://',
                r'ftp://'
            ]
            
            for pattern in suspicious_patterns:
                if re.search(pattern, response_str, re.IGNORECASE):
                    SecurityLogger.log_security_event("suspicious_response_content", pattern[:30], "WARNING")
                    return False
            
            return True
            
        except Exception as e:
            SecurityLogger.log_security_event("response_validation_error", str(e)[:50], "ERROR")
            return False
    
    @staticmethod
    def sanitize_api_response(response_data: str) -> str:
        """Sanitize API response content"""
        if not isinstance(response_data, str):
            return str(response_data)
        
        # Remove any script tags
        sanitized = re.sub(r'<script.*?</script>', '', response_data, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove javascript: URLs
        sanitized = re.sub(r'javascript:[^"\']*', '', sanitized, flags=re.IGNORECASE)
        
        # Limit length
        if len(sanitized) > 500_000:  # 500KB limit for display
            sanitized = sanitized[:500_000] + "\n\n[Content truncated for security]"
        
        return sanitized