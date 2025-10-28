"""
Installation utility functions for the graphical installer.
Implements core installation logic from the original install.sh script.
"""

import subprocess
import os
import shutil
import re
import tempfile


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
        # Check if source directory exists and has files
        if not os.path.isdir(sys_conn_dir):
            print("Source network config directory does not exist")
            return True  # Not an error, just no config to copy
        
        files = os.listdir(sys_conn_dir)
        if not files:
            print("No network config files to copy")
            return True
        
        # Create target directory
        os.makedirs(target_dir, exist_ok=True)
        os.chmod(target_dir, 0o700)
        
        # Copy all files
        for file in files:
            src = os.path.join(sys_conn_dir, file)
            dst = os.path.join(target_dir, file)
            shutil.copy2(src, dst)
            print(f"Copied network config: {file}")
        
        print(f"Successfully copied {len(files)} network config files")
        return True
        
    except Exception as e:
        print(f"Error copying network config: {e}")
        return False


def grab_steam_bootstrap(mount_path):
    """
    Grab Steam bootstrap file for first boot.
    Priority: local /root/packages/ > download from Steam servers
    
    Args:
        mount_path: Mount path of the installed system
    
    Returns:
        bool: True if successful, False otherwise
    """
    destination = f"{mount_path}/etc/first-boot/"
    os.makedirs(destination, exist_ok=True)
    
    bootstrap_filename = "bootstraplinux_ubuntu12_32.tar.xz"
    bootstrap_pkg = f"/root/packages/{bootstrap_filename}"
    stm_pkg = "/root/packages/steam-jupiter-stable.pkg.tar.zst"
    
    try:
        # Check if bootstrap file already exists locally
        if os.path.exists(bootstrap_pkg):
            print(f"Found local bootstrap file: {bootstrap_pkg}")
            # Verify xz format
            result = subprocess.run(['xz', '-t', bootstrap_pkg], capture_output=True)
            if result.returncode == 0:
                shutil.copy2(bootstrap_pkg, destination)
                print(f"Copied bootstrap file to {destination}")
                return True
            else:
                print("Local bootstrap file format is invalid")
        
        # Check if Steam package exists
        if os.path.exists(stm_pkg):
            print(f"Extracting bootstrap from Steam package: {stm_pkg}")
            return _extract_bootstrap_from_steam_pkg(stm_pkg, destination)
        
        # Download Steam package
        print("Downloading Steam package...")
        steam_url = "https://steamdeck-packages.steamos.cloud/archlinux-mirror/jupiter-main/os/x86_64/steam-jupiter-stable-1.0.0.81-2.6-x86_64.pkg.tar.zst"
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            steam_tmp_pkg = os.path.join(tmp_dir, "steam-jupiter-stable.pkg.tar.zst")
            
            # Download with curl
            result = subprocess.run(
                ['curl', '--http1.1', '-L', '-o', steam_tmp_pkg, '-C', '-', steam_url],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Failed to download Steam package: {result.stderr}")
                return False
            
            # Extract bootstrap from downloaded package
            success = _extract_bootstrap_from_steam_pkg(steam_tmp_pkg, destination)
            
            # Optionally save the package for future use
            if success:
                os.makedirs('/root/packages', exist_ok=True)
                try:
                    shutil.copy2(steam_tmp_pkg, stm_pkg)
                    print(f"Saved Steam package to {stm_pkg}")
                except:
                    pass  # Not critical
            
            return success
        
    except Exception as e:
        print(f"Error grabbing Steam bootstrap: {e}")
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
        # Verify file exists in package
        result = subprocess.run(
            ['tar', '-I', 'zstd', '-tf', pkg_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Cannot read Steam package: {result.stderr}")
            return False
        
        if 'usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz' not in result.stdout:
            print("Bootstrap file not found in Steam package")
            return False
        
        # Extract to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.xz') as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            result = subprocess.run(
                ['tar', '-I', 'zstd', '-xf', pkg_path,
                 'usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz', '-O'],
                stdout=open(tmp_path, 'wb'),
                stderr=subprocess.PIPE
            )
            
            if result.returncode != 0:
                print(f"Failed to extract bootstrap: {result.stderr.decode()}")
                return False
            
            # Verify extracted file
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                print("Extracted file is empty")
                return False
            
            result = subprocess.run(['xz', '-t', tmp_path], capture_output=True)
            if result.returncode != 0:
                print("Extracted file format is invalid")
                return False
            
            # Copy to destination
            dest_file = os.path.join(destination, 'bootstraplinux_ubuntu12_32.tar.xz')
            shutil.copy2(tmp_path, dest_file)
            print(f"Successfully extracted bootstrap to {dest_file}")
            return True
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except Exception as e:
        print(f"Error extracting bootstrap from Steam package: {e}")
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
        # List btrfs subvolumes
        result = subprocess.run(
            ['btrfs', 'subvolume', 'list', mount_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Failed to list btrfs subvolumes: {result.stderr}")
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
        
        if not deployments:
            print("No deployment subvolumes found")
            return True
        
        print(f"Found {len(deployments)} deployment(s)")
        
        # Process each deployment
        for deploy_subvol in deployments:
            print(f"Processing deployment: {deploy_subvol}")
            deploy_path = os.path.join(mount_path, deploy_subvol)
            
            # Set read-write
            subprocess.run(
                ['btrfs', 'property', 'set', '-fts', deploy_path, 'ro', 'false'],
                check=False
            )
            
            # Modify Steam session file
            _modify_steam_session(deploy_path)
            
            # Modify steamos-update script
            _modify_steamos_update(deploy_path)
            
            # Set read-only
            subprocess.run(
                ['btrfs', 'property', 'set', '-fts', deploy_path, 'ro', 'true'],
                check=False
            )
        
        # Process /source file
        source_file = os.path.join(mount_path, 'source')
        if os.path.exists(source_file):
            try:
                with open(source_file, 'r') as f:
                    content = f.read().strip()
                
                # Remove file extension (e.g., .img)
                content = re.sub(r'\.[^:]*$', '', content)
                
                with open(source_file, 'w') as f:
                    f.write(content)
                
                print(f"Processed /source file: {content}")
            except Exception as e:
                print(f"Error processing /source file: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error in post_install: {e}")
        return False


def _modify_steam_session(deploy_path):
    """Modify Steam session file to add -nobootstrapupdate flag."""
    steam_sessions = os.path.join(
        deploy_path,
        'usr/share/gamescope-session-plus/sessions.d/steam'
    )
    
    if not os.path.exists(steam_sessions):
        print(f"Steam session file not found: {steam_sessions}")
        return
    
    try:
        with open(steam_sessions, 'r') as f:
            content = f.read()
        
        modified = False
        
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
        
        if modified:
            with open(steam_sessions, 'w') as f:
                f.write(content)
            print(f"Modified Steam session file: {steam_sessions}")
    
    except Exception as e:
        print(f"Error modifying Steam session file: {e}")


def _modify_steamos_update(deploy_path):
    """Modify steamos-update script to prevent updates while Steam is running."""
    steamos_update = os.path.join(deploy_path, 'usr/bin/steamos-update')
    
    if not os.path.exists(steamos_update):
        print(f"steamos-update script not found: {steamos_update}")
        return
    
    try:
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
                print(f"Modified steamos-update script: {steamos_update}")
    
    except Exception as e:
        print(f"Error modifying steamos-update script: {e}")


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

