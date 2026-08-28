"""
Timezone detection and configuration utilities.
Implements automatic timezone detection using IP geolocation with fallback strategies.
"""

import subprocess
import os
from ..logger import get_logger

logger = get_logger('timezone')


def auto_detect_timezone():
    """
    Auto-detect timezone using multi-layer fallback strategy.
    
    Priority:
    1. IP geolocation (most accurate for most users)
    2. systemd timezone recommendation
    3. Default to UTC
    
    Returns:
        str: Detected timezone (e.g., 'Asia/Shanghai', 'America/New_York')
    """
    logger.info("Starting timezone auto-detection...")
    
    # Method 1: IP geolocation (recommended)
    timezone = _detect_by_ip_geolocation()
    if timezone:
        logger.info(f"✓ Timezone detected via IP geolocation: {timezone}")
        return timezone
    
    # Method 2: systemd timezone guess
    timezone = _detect_by_systemd()
    if timezone:
        logger.info(f"✓ Timezone detected via systemd: {timezone}")
        return timezone
    
    # Method 3: Default fallback
    logger.warning("Could not detect timezone, using UTC")
    return 'UTC'


def _detect_by_ip_geolocation():
    """
    Detect timezone using IP geolocation APIs.
    
    Accuracy: 85-95% for most users
    - Very accurate for countries with single timezone (China, Japan, Korea, etc.)
    - Less accurate for countries with multiple timezones (US, Russia, etc.)
    - Inaccurate for VPN/proxy users
    
    Priority: China domestic services > International services
    
    Returns:
        str or None: Detected timezone, or None if detection failed
    """
    # Try China-specific detection first (avoids proxy issues for Chinese users)
    china_timezone = _detect_china_timezone()
    if china_timezone:
        return china_timezone
    
    # Use multiple free APIs as backup
    apis = [
        # API 1: ipapi.co (1000 requests/day free, HTTPS)
        {
            'url': 'https://ipapi.co/json/',
            'timezone_key': 'timezone',
            'timeout': 3
        },
        # API 2: ip-api.com (unlimited, but HTTP only)
        {
            'url': 'http://ip-api.com/json/',
            'timezone_key': 'timezone',
            'timeout': 3
        },
        # API 3: worldtimeapi.org (IP-based timezone)
        {
            'url': 'https://worldtimeapi.org/api/ip',
            'timezone_key': 'timezone',
            'timeout': 3
        }
    ]
    
    for api in apis:
        try:
            # Try to import requests (should be available in live environment)
            try:
                import requests
            except ImportError:
                logger.debug("requests module not available, trying urllib")
                # Fallback to urllib
                timezone = _detect_with_urllib(api)
                if timezone:
                    return timezone
                continue
            
            response = requests.get(api['url'], timeout=api['timeout'])
            if response.status_code == 200:
                data = response.json()
                timezone = data.get(api['timezone_key'])
                
                # Validate timezone
                if timezone and _is_valid_timezone(timezone):
                    logger.info(f"Timezone detected: {timezone} (via {api['url']})")
                    return timezone
                else:
                    logger.debug(f"Invalid timezone from {api['url']}: {timezone}")
        except Exception as e:
            logger.debug(f"API {api['url']} failed: {e}")
            continue
    
    return None


def _detect_china_timezone():
    """
    Detect if user is in China using Chinese domestic IP services.
    
    This method uses actual Chinese domestic services that are more reliable
    for users in mainland China (not affected by proxies to international sites).
    Since mainland China uses a single timezone (Asia/Shanghai), we can return
    it directly if we detect a Chinese IP.
    
    Returns:
        str or None: 'Asia/Shanghai' if in China, None otherwise
    """
    # Try multiple Chinese domestic IP detection services
    china_services = [
        # Service 1: 太平洋电脑网 IP 查询（中国服务）
        {
            'url': 'http://whois.pconline.com.cn/ipJson.jsp',
            'type': 'jsonp',  # Returns JSONP format
            'timeout': 2
        },
        # Service 2: ip.useragentinfo.com（中国服务）
        {
            'url': 'http://ip.useragentinfo.com/json',
            'type': 'json',
            'country_key': 'country',
            'timeout': 2
        },
        # Service 3: cip.cc（中国服务，简单文本输出）
        {
            'url': 'http://cip.cc/',
            'type': 'text',
            'timeout': 2
        }
    ]
    
    for service in china_services:
        try:
            # Try requests first
            try:
                import requests
                response = requests.get(service['url'], timeout=service['timeout'])
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Parse based on service type
                    if service['type'] == 'jsonp':
                        # Handle JSONP format (e.g., IPCallback({...}))
                        import json
                        import re
                        match = re.search(r'\{.*\}', content)
                        if match:
                            data = json.loads(match.group())
                            # pconline returns 'pro' field with province name
                            # If 'pro' exists and not empty, user is in China
                            if data.get('pro') or '中国' in content or 'China' in content:
                                logger.info(f"Detected China IP, using Asia/Shanghai (via {service['url']})")
                                return 'Asia/Shanghai'
                    
                    elif service['type'] == 'json':
                        import json
                        data = json.loads(content)
                        country = data.get(service.get('country_key', 'country'), '')
                        
                        # Check if country contains China
                        if '中国' in country or 'China' in country.upper() or 'CN' in country.upper():
                            logger.info(f"Detected China IP, using Asia/Shanghai (via {service['url']})")
                            return 'Asia/Shanghai'
                    
                    elif service['type'] == 'text':
                        # cip.cc returns multi-line text with country info
                        if '中国' in content or 'China' in content:
                            logger.info(f"Detected China IP, using Asia/Shanghai (via {service['url']})")
                            return 'Asia/Shanghai'
                        
            except ImportError:
                # Fallback to urllib
                import urllib.request
                import json
                import re
                
                with urllib.request.urlopen(service['url'], timeout=service['timeout']) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    
                    # Parse based on service type
                    if service['type'] == 'jsonp':
                        match = re.search(r'\{.*\}', content)
                        if match:
                            data = json.loads(match.group())
                            if data.get('pro') or '中国' in content or 'China' in content:
                                logger.info(f"Detected China IP, using Asia/Shanghai (via {service['url']})")
                                return 'Asia/Shanghai'
                    
                    elif service['type'] == 'json':
                        data = json.loads(content)
                        country = data.get(service.get('country_key', 'country'), '')
                        if '中国' in country or 'China' in country.upper() or 'CN' in country.upper():
                            logger.info(f"Detected China IP, using Asia/Shanghai (via {service['url']})")
                            return 'Asia/Shanghai'
                    
                    elif service['type'] == 'text':
                        if '中国' in content or 'China' in content:
                            logger.info(f"Detected China IP, using Asia/Shanghai (via {service['url']})")
                            return 'Asia/Shanghai'
                        
        except Exception as e:
            logger.debug(f"China service {service['url']} failed: {e}")
            continue
    
    # Could not detect country, return None to try international services
    return None


def _detect_with_urllib(api):
    """Fallback method using urllib instead of requests."""
    try:
        import urllib.request
        import json
        
        with urllib.request.urlopen(api['url'], timeout=api['timeout']) as response:
            data = json.loads(response.read().decode())
            timezone = data.get(api['timezone_key'])
            
            if timezone and _is_valid_timezone(timezone):
                logger.info(f"Timezone detected: {timezone} (via {api['url']} with urllib)")
                return timezone
    except Exception as e:
        logger.debug(f"urllib fallback failed for {api['url']}: {e}")
    
    return None


def _detect_by_systemd():
    """
    Use systemd's timezone recommendation as fallback.
    
    Returns:
        str or None: Detected timezone, or None if detection failed
    """
    try:
        result = subprocess.run(
            ['timedatectl', 'show', '--property=Timezone', '--value'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            timezone = result.stdout.strip()
            if timezone and timezone != 'n/a' and _is_valid_timezone(timezone):
                return timezone
    except Exception as e:
        logger.debug(f"systemd timezone detection failed: {e}")
    
    return None


def _is_valid_timezone(timezone):
    """
    Validate timezone string by checking if corresponding zoneinfo file exists.
    
    Args:
        timezone: Timezone string (e.g., 'Asia/Shanghai')
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not timezone or not isinstance(timezone, str):
        return False
    
    zoneinfo_path = f'/usr/share/zoneinfo/{timezone}'
    return os.path.exists(zoneinfo_path)


def apply_timezone_to_live(timezone):
    """
    Apply timezone to the live environment.
    
    Args:
        timezone: Timezone string (e.g., 'Asia/Shanghai')
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Validate timezone first
        if not _is_valid_timezone(timezone):
            logger.error(f"Invalid timezone: {timezone}")
            return False

        from ..flow.env import simulation

        if simulation():
            os.environ["TZ"] = timezone
            try:
                import time
                time.tzset()
            except Exception:
                pass
            logger.info(f"Timezone recorded (sim, skipped timedatectl): {timezone}")
            return True
        
        # Apply using timedatectl
        result = subprocess.run(
            ['timedatectl', 'set-timezone', timezone],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to set timezone: {result.stderr}")
            return False
        
        logger.info(f"✓ Timezone set to: {timezone}")
        
        # Refresh Python's timezone cache
        os.environ['TZ'] = timezone
        try:
            import time
            time.tzset()
            logger.debug("Python timezone cache refreshed")
        except Exception as e:
            logger.debug(f"Could not refresh timezone cache: {e}")
        
        return True
        
    except Exception as e:
        logger.exception(f"Error applying timezone to live environment: {e}")
        return False


def get_current_timezone():
    """
    Get current system timezone.
    
    Returns:
        str: Current timezone (e.g., 'Asia/Shanghai'), or 'UTC' if detection fails
    """
    try:
        result = subprocess.run(
            ['timedatectl', 'show', '--property=Timezone', '--value'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            timezone = result.stdout.strip()
            if timezone and timezone != 'n/a':
                return timezone
    except Exception as e:
        logger.debug(f"Could not get current timezone: {e}")
    
    return 'UTC'

