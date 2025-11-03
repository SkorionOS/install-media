"""
Installation utility functions for the graphical installer.
Implements core installation logic from the original install.sh script.
"""

import subprocess
import os
import shutil
import re
import tempfile
import urllib.request
import urllib.error
from ..logger import get_logger
from ..config import config

logger = get_logger('install')


def copy_network_config(mount_path):
    """
    Copy NetworkManager connection files from live environment to installed system.
    
    Args:
        mount_path: Mount path of the installed system (e.g., /tmp/frzr_root)
    
    Returns:
        bool: True if successful, False otherwise
    """
    sys_conn_dir = "/etc/NetworkManager/system-connections"
    target_dir = f"{mount_path}{sys_conn_dir}"
    
    try:
        logger.info("Starting network configuration copy")
        
        # Check if source directory exists and has files
        if not os.path.isdir(sys_conn_dir):
            logger.info(f"Source network config directory does not exist: {sys_conn_dir}")
            print("  没有网络配置需要复制")
            return True  # Not an error, just no config to copy
        
        files = os.listdir(sys_conn_dir)
        if not files:
            logger.info("Network config directory is empty")
            print("  没有网络配置需要复制")
            return True
        
        logger.info(f"Found {len(files)} network configuration file(s)")
        print(f"  发现 {len(files)} 个网络配置文件")
        
        # Create target directory
        logger.debug(f"Creating target directory: {target_dir}")
        os.makedirs(target_dir, exist_ok=True)
        os.chmod(target_dir, 0o700)
        
        # Copy all files
        copied_count = 0
        for file in files:
            src = os.path.join(sys_conn_dir, file)
            dst = os.path.join(target_dir, file)
            try:
                shutil.copy2(src, dst)
                logger.debug(f"Copied: {file}")
                copied_count += 1
            except Exception as e:
                logger.warning(f"Failed to copy {file}: {e}")
                print(f"  [警告] 无法复制配置文件: {file}")
        
        logger.info(f"Successfully copied {copied_count}/{len(files)} network config files")
        print(f"  ✓ 已复制 {copied_count} 个网络配置文件")
        return True
        
    except Exception as e:
        logger.exception(f"Error copying network config: {e}")
        print(f"  [错误] 复制网络配置失败: {e}")
        return False


def copy_timezone_config(mount_path, timezone=None):
    """
    Copy timezone configuration from live environment to installed system.
    
    Args:
        mount_path: Mount path of the installed system (e.g., /tmp/frzr_root)
        timezone: Timezone name (e.g., 'Asia/Shanghai'). If None, use current system timezone.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Starting timezone configuration copy")
        
        # Get current timezone if not specified
        if not timezone:
            logger.debug("Detecting current system timezone")
            result = subprocess.run(
                ['timedatectl', 'show', '--property=Timezone', '--value'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                timezone = result.stdout.strip()
                logger.debug(f"Detected timezone: {timezone}")
            else:
                timezone = 'UTC'  # Fallback to UTC
                logger.warning(f"Failed to detect timezone, using fallback: UTC")
        
        logger.info(f"Configuring timezone: {timezone}")
        print(f"  配置时区: {timezone}")
        
        # Method 1: Create symlink (recommended, follows system standard)
        zoneinfo_source = f'/usr/share/zoneinfo/{timezone}'
        localtime_target = os.path.join(mount_path, 'etc/localtime')
        
        # Check if timezone file exists
        if not os.path.exists(zoneinfo_source):
            logger.error(f"Timezone file does not exist: {zoneinfo_source}")
            print(f"  [错误] 时区文件不存在: {zoneinfo_source}")
            return False
        
        # Remove old localtime (may be file or symlink)
        if os.path.exists(localtime_target) or os.path.islink(localtime_target):
            logger.debug(f"Removing old localtime: {localtime_target}")
            os.remove(localtime_target)
        
        # Create symlink
        logger.debug(f"Creating symlink: {localtime_target} -> /usr/share/zoneinfo/{timezone}")
        os.symlink(f'/usr/share/zoneinfo/{timezone}', localtime_target)
        print(f"  ✓ 设置 /etc/localtime 符号链接")
        
        # Method 2: Write /etc/timezone (some distros need this)
        timezone_file = os.path.join(mount_path, 'etc/timezone')
        logger.debug(f"Writing timezone file: {timezone_file}")
        with open(timezone_file, 'w') as f:
            f.write(f"{timezone}\n")
        print(f"  ✓ 写入 /etc/timezone 文件")
        
        logger.info(f"Successfully configured timezone: {timezone}")
        return True
        
    except Exception as e:
        logger.exception(f"Error copying timezone config: {e}")
        print(f"  [错误] 复制时区配置失败: {e}")
        return False


def grab_steam_bootstrap(mount_path):
    """
    Grab Steam bootstrap file for first boot (without progress reporting).
    Priority: local /root/packages/ > download from Steam servers
    
    Args:
        mount_path: Mount path of the installed system
    
    Returns:
        bool: True if successful, False otherwise
    """
    return grab_steam_bootstrap_with_progress(mount_path, progress_callback=None)


def grab_steam_bootstrap_with_progress(mount_path, progress_callback=None, max_retries=3):
    """
    Grab Steam bootstrap file for first boot with progress reporting.
    Priority: local /root/packages/ > download from Steam servers
    Uses Python urllib for better progress tracking and error handling.
    Automatically retries on corrupted downloads.
    
    Args:
        mount_path: Mount path of the installed system
        progress_callback: Optional callback function(message, progress_fraction)
                          Called with progress updates. progress_fraction is 0.0-1.0 or None
        max_retries: Maximum retry attempts on file corruption (default: 3)
    
    Returns:
        bool: True if successful, False otherwise
    """
    destination = f"{mount_path}/etc/first-boot/"
    os.makedirs(destination, exist_ok=True)
    
    bootstrap_pkg = os.path.join(config.steam_packages_dir, config.steam_bootstrap_filename)
    stm_pkg = os.path.join(config.steam_packages_dir, config.steam_package_filename)
    
    def report(msg, progress=None):
        """Report progress if callback is provided."""
        print(msg)  # Always print to console
        if progress_callback:
            progress_callback(msg, progress)
    
    try:
        # Check if bootstrap file already exists locally
        if os.path.exists(bootstrap_pkg):
            report("发现本地 Steam 引导文件", 0.3)
            # Verify xz format
            result = subprocess.run(['xz', '-t', bootstrap_pkg], capture_output=True)
            if result.returncode == 0:
                report("正在复制本地引导文件...", 0.7)
                shutil.copy2(bootstrap_pkg, destination)
                report("[成功] 已复制本地引导文件", 1.0)
                return True
            else:
                report("[警告] 本地引导文件格式无效，将删除", None)
                try:
                    os.remove(bootstrap_pkg)
                    logger.info(f"Deleted invalid bootstrap file: {bootstrap_pkg}")
                except Exception as e:
                    logger.warning(f"Could not delete invalid bootstrap: {e}")
        
        # Check if Steam package exists locally - with auto-retry on corruption
        if os.path.exists(stm_pkg):
            report("从本地 Steam 包提取引导文件...", 0.3)
            success = _extract_bootstrap_from_steam_pkg(stm_pkg, destination)
            if success:
                report("[成功] 已从本地包提取引导文件", 1.0)
                return True
            else:
                # Corrupted file was already deleted by _extract_bootstrap_from_steam_pkg
                report("[警告] 本地包已损坏，将重新下载", None)
                # Continue to download section
        
        # Download Steam package with retry logic
        for retry_count in range(max_retries):
            try:
                if retry_count > 0:
                    report(f"重试下载 ({retry_count + 1}/{max_retries})...", 0.05)
                    logger.info(f"Retry attempt {retry_count + 1}/{max_retries}")
                else:
                    report("准备下载 Steam 包...", 0.05)
                
                with tempfile.TemporaryDirectory() as tmp_dir:
                    steam_tmp_pkg = os.path.join(tmp_dir, config.steam_package_filename)
                    
                    # Download with progress reporting
                    success = _download_file_with_progress(
                        config.steam_package_url,
                        steam_tmp_pkg,
                        report,
                        progress_start=0.1,
                        progress_end=0.8
                    )
                    
                    if not success:
                        if retry_count < max_retries - 1:
                            report(f"[警告] 下载失败，2秒后重试...", None)
                            import time
                            time.sleep(2)
                            continue
                        else:
                            report("[失败] 下载失败，已达最大重试次数", None)
                            return False
                    
                    # Extract bootstrap
                    report("正在提取引导文件...", 0.85)
                    success = _extract_bootstrap_from_steam_pkg(steam_tmp_pkg, destination)
                    
                    if success:
                        report("[成功] Steam 引导文件准备完成", 1.0)
                        # Save package for future use
                        os.makedirs(config.steam_packages_dir, exist_ok=True)
                        try:
                            shutil.copy2(steam_tmp_pkg, stm_pkg)
                            logger.info(f"Saved Steam package to {stm_pkg}")
                        except Exception as e:
                            logger.debug(f"Could not save Steam package: {e}")  # Not critical
                        return True
                    else:
                        # Extraction failed - file may be corrupted
                        if retry_count < max_retries - 1:
                            report(f"[警告] 提取失败，文件可能损坏，2秒后重试 ({retry_count + 2}/{max_retries})", None)
                            import time
                            time.sleep(2)
                            continue
                        else:
                            report("[失败] 无法提取引导文件，已达最大重试次数", None)
                            return False
                            
            except Exception as e:
                logger.exception(f"Retry {retry_count + 1}/{max_retries} failed")
                if retry_count < max_retries - 1:
                    report(f"[错误] {str(e)}，2秒后重试...", None)
                    import time
                    time.sleep(2)
                    continue
                else:
                    report(f"[错误] {str(e)}，已达最大重试次数", None)
                    return False
        
        # Should not reach here
        return False
        
    except Exception as e:
        logger.exception("Fatal error in grab_steam_bootstrap_with_progress")
        report(f"[错误] {str(e)}", None)
        return False


def _download_file_with_progress(url, dest_path, report_callback, 
                                  progress_start=0.0, progress_end=1.0,
                                  chunk_size=8192):
    """
    Download file with progress reporting using Python urllib.
    Supports resume from partial downloads.
    
    Args:
        url: Download URL
        dest_path: Destination file path
        report_callback: Callback function(message, progress)
        progress_start: Starting progress value (0.0-1.0)
        progress_end: Ending progress value (0.0-1.0)
        chunk_size: Download chunk size in bytes (default: 8KB)
    
    Returns:
        bool: True if successful
    """
    try:
        # Check if partial file exists (for resume)
        downloaded_size = 0
        mode = 'wb'
        
        if os.path.exists(dest_path):
            downloaded_size = os.path.getsize(dest_path)
            mode = 'ab'  # Append mode for resume
        
        # Create request with resume support
        req = urllib.request.Request(url)
        if downloaded_size > 0:
            req.add_header('Range', f'bytes={downloaded_size}-')
        
        # Open connection
        with urllib.request.urlopen(req, timeout=30) as response:
            # Get total file size
            total_size = downloaded_size
            content_range = response.headers.get('Content-Range')
            if content_range:
                # Resuming download - parse "bytes start-end/total"
                total_size = int(content_range.split('/')[-1])
            else:
                # New download
                content_length = response.headers.get('Content-Length')
                if content_length:
                    total_size = int(content_length)
            
            # Calculate size in MB for display
            total_mb = total_size / (1024 * 1024)
            
            if downloaded_size > 0:
                downloaded_mb = downloaded_size / (1024 * 1024)
                report_callback(
                    f"继续下载 Steam 包 (已下载 {downloaded_mb:.1f}MB / {total_mb:.1f}MB)...",
                    progress_start
                )
            else:
                report_callback(f"正在下载 Steam 包 ({total_mb:.1f}MB)...", progress_start)
            
            # Download with progress
            last_reported_percent = -1
            with open(dest_path, mode) as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Calculate progress
                    if total_size > 0:
                        percent = (downloaded_size / total_size) * 100
                        
                        # Report every 5%
                        if int(percent / 5) > int(last_reported_percent / 5):
                            # Map to progress range
                            progress = progress_start + (percent / 100.0) * (progress_end - progress_start)
                            downloaded_mb = downloaded_size / (1024 * 1024)
                            report_callback(
                                f"下载中... {percent:.1f}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB)",
                                progress
                            )
                            last_reported_percent = percent
        
        # Verify download
        final_size = os.path.getsize(dest_path)
        if total_size > 0 and final_size != total_size:
            report_callback(
                f"[警告] 下载的文件大小不匹配 (期望: {total_size}, 实际: {final_size})",
                None
            )
            return False
        
        final_mb = final_size / (1024 * 1024)
        report_callback(f"下载完成 ({final_mb:.1f}MB)", progress_end)
        return True
        
    except urllib.error.HTTPError as e:
        report_callback(f"[错误] HTTP {e.code}: {e.reason}", None)
        return False
    except urllib.error.URLError as e:
        report_callback(f"[错误] 网络错误: {e.reason}", None)
        return False
    except TimeoutError:
        report_callback("[错误] 下载超时", None)
        return False
    except Exception as e:
        report_callback(f"[错误] {str(e)}", None)
        return False


def _extract_bootstrap_from_steam_pkg(pkg_path, destination):
    """
    Extract bootstraplinux_ubuntu12_32.tar.xz from Steam package.
    
    Args:
        pkg_path: Path to steam-jupiter-stable.pkg.tar.zst
        destination: Destination directory
    
    Returns:
        bool: True if successful
    """
    try:
        # Check if file exists and is not empty
        if not os.path.exists(pkg_path):
            logger.error(f"Steam package not found: {pkg_path}")
            return False
        
        file_size = os.path.getsize(pkg_path)
        if file_size == 0:
            logger.error(f"Steam package is empty: {pkg_path}")
            return False
        
        logger.info(f"Steam package size: {file_size / (1024*1024):.1f} MB")
        
        # Expected size range (280-300 MB for steam-jupiter-stable)
        expected_min_size = 250 * 1024 * 1024  # 250 MB
        if file_size < expected_min_size:
            logger.error(f"Steam package too small: {file_size / (1024*1024):.1f} MB (expected > 250 MB)")
            logger.error("File appears to be incomplete, deleting...")
            try:
                os.remove(pkg_path)
                logger.info(f"Deleted incomplete file: {pkg_path}")
            except Exception as e:
                logger.warning(f"Could not delete file: {e}")
            return False
        
        # Verify file exists in package
        logger.info("Verifying Steam package contents...")
        result = subprocess.run(
            ['tar', '-I', 'zstd', '-tf', pkg_path],
            capture_output=True,
            text=True,
            timeout=30  # Add timeout to prevent hanging
        )
        
        if result.returncode != 0:
            logger.error("Cannot read Steam package - file may be corrupted")
            if result.stderr:
                # Log the actual error for debugging
                logger.error(f"tar stderr: {result.stderr.strip()}")
            logger.error(f"Deleting corrupted file: {pkg_path}")
            # Delete corrupted file to force re-download
            try:
                os.remove(pkg_path)
                logger.info(f"Deleted corrupted file: {pkg_path}")
            except Exception as e:
                logger.warning(f"Could not delete corrupted file: {e}")
            return False
        
        if 'usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz' not in result.stdout:
            logger.error("Bootstrap file not found in Steam package")
            logger.error(f"Package contents preview: {result.stdout[:500]}")
            return False
        
        logger.info("Bootstrap file found in package")
        
        # Extract to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.xz') as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            logger.info("Extracting bootstrap file from package...")
            with open(tmp_path, 'wb') as out_file:
                result = subprocess.run(
                    ['tar', '-I', 'zstd', '-xf', pkg_path,
                     'usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz', '-O'],
                    stdout=out_file,
                    stderr=subprocess.PIPE
                )
            
            if result.returncode != 0:
                logger.error("Failed to extract bootstrap from Steam package")
                if result.stderr:
                    logger.error(f"tar stderr: {result.stderr.decode().strip()}")
                return False
            
            # Verify extracted file
            if not os.path.exists(tmp_path):
                logger.error("Extracted file does not exist")
                return False
            
            extracted_size = os.path.getsize(tmp_path)
            if extracted_size == 0:
                logger.error("Extracted file is empty")
                return False
            
            logger.info(f"Extracted file size: {extracted_size / (1024*1024):.1f} MB")
            
            # Verify xz format
            result = subprocess.run(['xz', '-t', tmp_path], 
                                   capture_output=True)
            if result.returncode != 0:
                logger.error("Extracted file format is invalid (xz test failed)")
                if result.stderr:
                    logger.error(f"xz stderr: {result.stderr.decode().strip()}")
                return False
            
            logger.info("Extracted file verified successfully")
            
            # Copy to destination
            dest_file = os.path.join(destination, 'bootstraplinux_ubuntu12_32.tar.xz')
            shutil.copy2(tmp_path, dest_file)
            logger.info(f"Successfully extracted bootstrap to {dest_file}")
            return True
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except subprocess.TimeoutExpired:
        logger.exception("Timeout while reading Steam package - file may be corrupted")
        # Try to delete corrupted file
        try:
            if os.path.exists(pkg_path):
                os.remove(pkg_path)
                logger.info(f"Deleted corrupted Steam package: {pkg_path}")
        except Exception:
            pass
        return False
    except Exception as e:
        logger.exception(f"Error extracting bootstrap from Steam package: {e}")
        return False


def post_install(mount_path):
    """
    Perform post-installation configuration.
    Modifies Steam session files and steamos-update script.
    
    Args:
        mount_path: Mount path of the installed system
    
    Returns:
        bool: True if successful
    """
    try:
        logger.info("=== Starting post-installation configuration ===")
        print("正在扫描系统部署...")
        
        # List btrfs subvolumes
        logger.info(f"Listing btrfs subvolumes in {mount_path}")
        result = subprocess.run(
            ['btrfs', 'subvolume', 'list', mount_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to list btrfs subvolumes: {result.stderr}")
            print(f"[错误] 无法列出 btrfs 子卷: {result.stderr}")
            return False
        
        # Find deployment subvolumes
        deployments = []
        for line in result.stdout.split('\n'):
            if 'deployments/chimeraos' in line or 'deployments/skorionos' in line:
                # Extract subvolume path (last column)
                parts = line.split()
                if parts:
                    deploy_path = parts[-1]
                    deployments.append(deploy_path)
                    logger.debug(f"Found deployment: {deploy_path}")
        
        if not deployments:
            logger.warning("No deployment subvolumes found")
            print("[警告] 未找到部署子卷")
            return True
        
        logger.info(f"Found {len(deployments)} deployment(s)")
        print(f"发现 {len(deployments)} 个系统部署")
        
        # Process each deployment
        for idx, deploy_subvol in enumerate(deployments, 1):
            logger.info(f"Processing deployment {idx}/{len(deployments)}: {deploy_subvol}")
            print(f"正在优化部署 [{idx}/{len(deployments)}]: {deploy_subvol}")
            deploy_path = os.path.join(mount_path, deploy_subvol)
            
            # Set read-write
            logger.debug(f"Setting deployment to read-write: {deploy_path}")
            result = subprocess.run(
                ['btrfs', 'property', 'set', '-fts', deploy_path, 'ro', 'false'],
                capture_output=True,
                check=False
            )
            if result.returncode == 0:
                logger.debug("Successfully set to read-write")
            else:
                logger.warning(f"Failed to set read-write: {result.stderr}")
            
            # Modify Steam session file
            logger.debug("Modifying Steam session file...")
            _modify_steam_session(deploy_path)
            
            # Modify steamos-update script
            logger.debug("Modifying steamos-update script...")
            _modify_steamos_update(deploy_path)
            
            # Set read-only
            logger.debug(f"Setting deployment back to read-only: {deploy_path}")
            result = subprocess.run(
                ['btrfs', 'property', 'set', '-fts', deploy_path, 'ro', 'true'],
                capture_output=True,
                check=False
            )
            if result.returncode == 0:
                logger.debug("Successfully set to read-only")
                print(f"  ✓ 部署优化完成: {deploy_subvol}")
            else:
                logger.warning(f"Failed to set read-only: {result.stderr}")
        
        # Process /source file
        source_file = os.path.join(mount_path, 'source')
        if os.path.exists(source_file):
            try:
                logger.info("Processing /source file")
                print("正在处理系统源文件...")
                
                with open(source_file, 'r') as f:
                    original_content = f.read().strip()
                
                logger.debug(f"Original source content: {original_content}")
                
                # Remove file extension (e.g., .img)
                new_content = re.sub(r'\.[^:]*$', '', original_content)
                
                with open(source_file, 'w') as f:
                    f.write(new_content)
                
                logger.info(f"Processed /source file: {original_content} -> {new_content}")
                print(f"  ✓ 源文件已更新: {new_content}")
            except Exception as e:
                logger.exception(f"Error processing /source file: {e}")
                print(f"[警告] 处理源文件失败: {e}")
        else:
            logger.debug(f"Source file not found: {source_file}")
        
        logger.info("=== Post-installation configuration completed successfully ===")
        print("系统优化配置完成")
        return True
        
    except Exception as e:
        logger.exception(f"Error in post_install: {e}")
        print(f"[错误] 系统优化失败: {e}")
        return False


def _modify_steam_session(deploy_path):
    """Modify Steam session file to add -nobootstrapupdate flag."""
    steam_sessions = os.path.join(
        deploy_path,
        'usr/share/gamescope-session-plus/sessions.d/steam'
    )
    
    if not os.path.exists(steam_sessions):
        logger.warning(f"Steam session file not found: {steam_sessions}")
        print(f"  [跳过] Steam 会话文件不存在")
        return
    
    try:
        logger.debug(f"Reading Steam session file: {steam_sessions}")
        with open(steam_sessions, 'r') as f:
            content = f.read()
        
        modified = False
        modifications = []
        
        # Add -nobootstrapupdate to CLIENTCMD if not already present
        if 'nobootstrapupdate' not in content:
            # Find line with 'echo "set_bootstrap=1"' and add after it
            add_line = '    export CLIENTCMD="steam -gamepadui -steamos3 -steampal -steamdeck -noverifyfiles -nobootstrapupdate -skipinitialbootstrap"'
            
            if 'echo "set_bootstrap=1"' in content:
                content = content.replace(
                    'echo "set_bootstrap=1" >>',
                    f'echo "set_bootstrap=1" >>\n{add_line}'
                )
                modified = True
                modifications.append("添加 nobootstrapupdate 标志")
                logger.debug("Added nobootstrapupdate flag to Steam session")
        else:
            logger.debug("nobootstrapupdate flag already present")
        
        # Add loginusers.vdf check if not present
        if 'loginusers' not in content:
            add_line_2 = '''if [[ ! -f "${HOME}/.steam/root/config/loginusers.vdf" ]] || ! grep -q "AccountName" "${HOME}/.steam/root/config/loginusers.vdf"; then
    export CLIENTCMD="steam -gamepadui -steamos3 -steampal -steamdeck -noverifyfiles -nobootstrapupdate -skipinitialbootstrap"
fi'''
            
            if 'if command -v steam_notif_daemon' in content:
                content = content.replace(
                    'if command -v steam_notif_daemon',
                    f'{add_line_2}\n\nif command -v steam_notif_daemon'
                )
                modified = True
                modifications.append("添加 loginusers.vdf 检查")
                logger.debug("Added loginusers.vdf check to Steam session")
        else:
            logger.debug("loginusers check already present")
        
        if modified:
            with open(steam_sessions, 'w') as f:
                f.write(content)
            logger.info(f"Modified Steam session file: {', '.join(modifications)}")
            print(f"    • Steam 会话配置: {', '.join(modifications)}")
        else:
            logger.debug("Steam session file already configured, no changes needed")
            print(f"    • Steam 会话配置: 已是最新")
    
    except Exception as e:
        logger.exception(f"Error modifying Steam session file: {e}")
        print(f"    [错误] 修改 Steam 会话文件失败: {e}")


def _modify_steamos_update(deploy_path):
    """Modify steamos-update script to prevent updates while Steam is running."""
    steamos_update = os.path.join(deploy_path, 'usr/bin/steamos-update')
    
    if not os.path.exists(steamos_update):
        logger.warning(f"steamos-update script not found: {steamos_update}")
        print(f"  [跳过] steamos-update 脚本不存在")
        return
    
    try:
        logger.debug(f"Reading steamos-update script: {steamos_update}")
        with open(steamos_update, 'r') as f:
            content = f.read()
        
        if 'nobootstrapupdate' not in content:
            # Add check before frzr-deploy
            add_line = 'ps -ef | grep -v grep | grep "steamdeck" | grep "steamos" | grep "nobootstrapupdate" >/dev/null && exit 0'
            
            if 'if command -v frzr-deploy' in content:
                content = content.replace(
                    'if command -v frzr-deploy',
                    f'{add_line}\nif command -v frzr-deploy'
                )
                
                with open(steamos_update, 'w') as f:
                    f.write(content)
                logger.info("Added Steam running check to steamos-update script")
                print(f"    • 系统更新脚本: 添加 Steam 运行检查")
            else:
                logger.warning("Target line 'if command -v frzr-deploy' not found in steamos-update")
                print(f"    [警告] 系统更新脚本: 未找到目标配置行")
        else:
            logger.debug("steamos-update script already configured")
            print(f"    • 系统更新脚本: 已是最新")
    
    except Exception as e:
        logger.exception(f"Error modifying steamos-update script: {e}")
        print(f"    [错误] 修改系统更新脚本失败: {e}")


def verify_boot_config(mount_path, result_code):
    """
    Verify boot configuration exists after installation.
    
    Args:
        mount_path: Mount path of the installed system
        result_code: Return code from frzr-deploy
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if result_code != 0:
        if result_code == 29:
            return False, "遇到 GitHub API 速率限制错误，请稍后重试"
        else:
            return False, f"安装失败，退出码: {result_code}"
    
    boot_cfg = os.path.join(mount_path, 'boot/loader/entries/frzr.conf')
    
    if not os.path.exists(boot_cfg):
        # TODO: Handle missing boot config by creating it from BOOT_CFG_PARA
        # For now, just return an error
        return False, "安装失败。未找到启动配置文件。"
    
    return True, "安装成功完成"

