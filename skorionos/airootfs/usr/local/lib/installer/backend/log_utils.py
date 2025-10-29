"""
Log utilities for the installer.
"""
import os
import re
import subprocess
import threading
from typing import Optional, Callable
from ..logger import get_logger

logger = get_logger('logutils')


def cleanup_log(log_file: str) -> bool:
    """
    Clean up ANSI escape codes and formatting from log file.
    
    Args:
        log_file: Path to log file
    
    Returns:
        bool: True if successful
    """
    if not os.path.exists(log_file):
        return False
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        
        # Remove ANSI escape sequences
        # Pattern 1: CSI sequences (ESC[...m)
        content = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', content)
        # Pattern 2: Mode sequences
        content = re.sub(r'\x1b\[[?!][0-9;]*[hlH]', '', content)
        # Pattern 3: Charset sequences
        content = re.sub(r'\x1b\([0-9AB]', '', content)
        # Pattern 4: Other positioning
        content = re.sub(r'\x1b\[[\d;]*[XG]', '', content)
        
        # Remove script command markers
        content = re.sub(r'^Script started on.*\[COMMAND=.*$', '', content, flags=re.MULTILINE)
        
        # Remove empty lines
        content = '\n'.join(line for line in content.split('\n') if line.strip())
        
        # Limit consecutive spaces (more than 20 spaces -> 20 spaces)
        content = re.sub(r' {21,}', ' ' * 20, content)
        
        # Write back
        with open(log_file, 'w') as f:
            f.write(content)
        
        print(f"[LOG] Log cleaned: {log_file}", flush=True)
        return True
        
    except Exception as e:
        logger.exception(f"[LOG] Error cleaning log: {e}")
        return False


def upload_log_to_fpaste(log_file: str, timeout: int = 10) -> Optional[str]:
    """
    Upload log file to fpaste.
    
    Args:
        log_file: Path to log file
        timeout: Upload timeout in seconds
    
    Returns:
        Optional[str]: Fpaste URL if successful, None otherwise
    """
    if not os.path.exists(log_file):
        print(f"[LOG] Log file not found: {log_file}", flush=True)
        return None
    
    try:
        # Read log content
        with open(log_file, 'r') as f:
            log_content = f.read()
        
        # Upload to fpaste with timeout
        process = subprocess.Popen(
            ['fpaste'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(input=log_content, timeout=timeout)
            
            if process.returncode == 0 and stdout.strip():
                url = stdout.strip()
                print(f"[LOG] Log uploaded to: {url}", flush=True)
                return url
            else:
                print(f"[LOG] Fpaste failed: {stderr}", flush=True)
                return None
                
        except subprocess.TimeoutExpired:
            process.kill()
            logger.warning("[LOG] Fpaste upload timed out")
            return None
        
    except Exception as e:
        logger.exception(f"[LOG] Error uploading log: {e}")
        return None


class AsyncLogUploader:
    """
    Asynchronous log uploader with callback support.
    """
    
    def __init__(self, log_file: str, callback: Optional[Callable[[Optional[str]], None]] = None):
        """
        Initialize uploader.
        
        Args:
            log_file: Path to log file
            callback: Callback function(url: Optional[str]) called when upload completes
        """
        self.log_file = log_file
        self.callback = callback
        self.thread = None
        self.url = None
        self.is_uploading = False
    
    def start(self):
        """Start asynchronous upload."""
        if self.is_uploading:
            return
        
        self.is_uploading = True
        self.thread = threading.Thread(target=self._upload_thread, daemon=True)
        self.thread.start()
        print(f"[LOG] Started async upload for {self.log_file}", flush=True)
    
    def _upload_thread(self):
        """Upload thread function."""
        # Clean log first
        cleanup_log(self.log_file)
        
        # Upload
        self.url = upload_log_to_fpaste(self.log_file)
        
        # Call callback if provided
        if self.callback:
            self.callback(self.url)
        
        self.is_uploading = False
    
    def wait(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Wait for upload to complete.
        
        Args:
            timeout: Wait timeout in seconds
        
        Returns:
            Optional[str]: Fpaste URL if successful
        """
        if self.thread:
            self.thread.join(timeout=timeout)
        return self.url

