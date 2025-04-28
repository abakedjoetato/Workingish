import os
import glob
import logging
import asyncssh
import aiofiles
import tempfile
from datetime import datetime
from config import SSH_TIMEOUT, DEFAULT_PORT

logger = logging.getLogger('deadside_bot.utils.log_access')

async def get_log_file(server, log_type):
    """
    Get the path to a log file based on server configuration
    
    Args:
        server: Server object
        log_type: Type of log file ("csv" or "log")
        
    Returns:
        str: Path to the log file, or None if not available
    """
    access_method = server.access_method
    
    if access_method == "local":
        return await get_local_log_file(server, log_type)
    elif access_method == "sftp":
        return await get_sftp_log_file(server, log_type)
    else:
        logger.error(f"Unsupported access method: {access_method}")
        return None

async def get_local_log_file(server, log_type):
    """
    Get the path to a local log file
    
    Args:
        server: Server object
        log_type: Type of log file ("csv" or "log")
        
    Returns:
        str: Path to the log file, or None if not available
    """
    try:
        base_path = server.log_path
        
        if log_type == "csv":
            # Check for killfeed.csv
            log_path = os.path.join(base_path, "killfeed.csv")
            if os.path.exists(log_path):
                return log_path
                
            # Alternative names
            alternatives = ["kills.csv", "Kill_feed.csv", "kills_feed.csv"]
            for alt in alternatives:
                alt_path = os.path.join(base_path, alt)
                if os.path.exists(alt_path):
                    return alt_path
                    
        elif log_type == "log":
            # Check for deadside.log
            log_path = os.path.join(base_path, "deadside.log")
            if os.path.exists(log_path):
                return log_path
                
            # Alternative names
            alternatives = ["server.log", "game.log"]
            for alt in alternatives:
                alt_path = os.path.join(base_path, alt)
                if os.path.exists(alt_path):
                    return alt_path
        
        logger.warning(f"Log file of type {log_type} not found in {base_path}")
        return None
        
    except Exception as e:
        logger.error(f"Error accessing local log file: {e}")
        return None

async def get_sftp_log_file(server, log_type):
    """
    Get the path to an SFTP log file (downloads it to a temporary file)
    
    Args:
        server: Server object
        log_type: Type of log file ("csv" or "log")
        
    Returns:
        str: Path to the temporary log file, or None if not available
    """
    temp_file = None
    
    try:
        # Check credentials
        if not server.ssh_user:
            logger.error(f"SSH user not configured for server {server.name}")
            return None
            
        # Set up connection info
        port = DEFAULT_PORT
        if ":" in server.ip:
            parts = server.ip.split(":")
            host = parts[0]
            port = int(parts[1])
        else:
            host = server.ip
        
        # Authentication options
        auth_options = {}
        if server.ssh_password:
            auth_options["password"] = server.ssh_password
        if server.ssh_key_path:
            if os.path.exists(server.ssh_key_path):
                auth_options["client_keys"] = [server.ssh_key_path]
            else:
                logger.warning(f"SSH key file {server.ssh_key_path} does not exist")
        
        # In our structure, server.log_path is already formatted as "{host}_{server_id}"
        # This is the first directory we need to navigate to upon connecting via SFTP
        server_dir = server.log_path
        
        # Determine remote file path within server directory
        if log_type == "csv":
            remote_files = ["killfeed.csv", "kills.csv", "Kill_feed.csv", "kills_feed.csv"]
        elif log_type == "log":
            remote_files = ["deadside.log", "server.log", "game.log"]
        else:
            logger.error(f"Unsupported log type: {log_type}")
            return None
        
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix=f".{log_type}")
        os.close(temp_fd)  # Close the file descriptor
        temp_file = temp_path
        
        # Connect to server and download file
        async with asyncssh.connect(
            host=host,
            port=port,
            username=server.ssh_user,
            **auth_options,
            known_hosts=None,  # Don't verify host keys
            timeout=SSH_TIMEOUT
        ) as conn:
            async with conn.start_sftp_client() as sftp:
                try:
                    # First check if the server directory exists
                    try:
                        await sftp.stat(server_dir)
                        logger.debug(f"Found server directory: {server_dir}")
                    except asyncssh.SFTPError:
                        logger.error(f"Server directory {server_dir} not found on SFTP server")
                        return None
                    
                    # Try each possible file name within the server directory
                    for remote_file in remote_files:
                        remote_path = os.path.join(server_dir, remote_file)
                        try:
                            # Check if file exists
                            file_info = await sftp.stat(remote_path)
                            
                            # Download file
                            await sftp.get(remote_path, temp_path)
                            logger.debug(f"Downloaded {remote_path} to {temp_path}")
                            return temp_path
                            
                        except asyncssh.SFTPError:
                            # File doesn't exist or can't be accessed
                            continue
                    
                    # If we got here, none of the files were found in this directory
                    logger.warning(f"No {log_type} files found in {server_dir}")
                except Exception as e:
                    logger.error(f"Error accessing files in server directory: {e}")
                
                return None
                
    except asyncssh.Error as e:
        logger.error(f"SSH/SFTP error: {e}")
        return None
        
    except Exception as e:
        logger.error(f"Error in SFTP file access: {e}")
        return None
        
    finally:
        # Clean up temp file if download failed
        if temp_file and not os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass

async def get_all_csv_files(server):
    """
    Get all available CSV files for a server
    
    Args:
        server: Server object
        
    Returns:
        list: List of paths to CSV files, or empty list if none available
    """
    access_method = server.access_method
    
    if access_method == "local":
        return await get_local_all_csv_files(server)
    elif access_method == "sftp":
        return await get_sftp_all_csv_files(server)
    else:
        logger.error(f"Unsupported access method: {access_method}")
        return []

async def get_local_all_csv_files(server):
    """
    Get all available local CSV files for historical processing
    
    Args:
        server: Server object
        
    Returns:
        list: List of paths to CSV files, or empty list if none available
    """
    try:
        base_path = server.log_path
        csv_files = []
        
        # Look for all CSV files in the directory
        pattern = os.path.join(base_path, "*.csv")
        csv_files = glob.glob(pattern)
        
        if not csv_files:
            # Try alternative paths
            alt_patterns = [
                os.path.join(base_path, "logs", "*.csv"),
                os.path.join(base_path, "killfeed", "*.csv"),
                os.path.join(base_path, "kills", "*.csv")
            ]
            
            for alt_pattern in alt_patterns:
                alt_files = glob.glob(alt_pattern)
                if alt_files:
                    csv_files.extend(alt_files)
                    break
                    
        return sorted(csv_files)
        
    except Exception as e:
        logger.error(f"Error accessing local CSV files: {e}")
        return []

async def get_sftp_all_csv_files(server):
    """
    Get all available SFTP CSV files for historical processing
    
    Args:
        server: Server object
        
    Returns:
        list: List of paths to temporary local copies of CSV files, 
              or empty list if none available
    """
    try:
        # Check credentials
        if not server.ssh_user:
            logger.error(f"SSH user not configured for server {server.name}")
            return []
            
        # Set up connection info
        port = DEFAULT_PORT
        if ":" in server.ip:
            parts = server.ip.split(":")
            host = parts[0]
            port = int(parts[1])
        else:
            host = server.ip
        
        # Authentication options
        auth_options = {}
        if server.ssh_password:
            auth_options["password"] = server.ssh_password
        if server.ssh_key_path:
            if os.path.exists(server.ssh_key_path):
                auth_options["client_keys"] = [server.ssh_key_path]
            else:
                logger.warning(f"SSH key file {server.ssh_key_path} does not exist")
        
        # Server directory is the log_path
        server_dir = server.log_path
        
        # Create temporary directory for CSV files
        temp_dir = tempfile.mkdtemp(prefix="deadside_csv_")
        temp_files = []
        
        # Connect to server and download files
        async with asyncssh.connect(
            host=host,
            port=port,
            username=server.ssh_user,
            **auth_options,
            known_hosts=None,  # Don't verify host keys
            timeout=SSH_TIMEOUT
        ) as conn:
            async with conn.start_sftp_client() as sftp:
                try:
                    # Check if the server directory exists
                    try:
                        await sftp.stat(server_dir)
                        logger.debug(f"Found server directory: {server_dir}")
                    except asyncssh.SFTPError:
                        logger.error(f"Server directory {server_dir} not found on SFTP server")
                        return []
                    
                    # List all files in the server directory
                    files = await sftp.listdir(server_dir)
                    csv_files = [f for f in files if f.lower().endswith('.csv')]
                    
                    # If no CSV files found, try subdirectories
                    if not csv_files:
                        subdirs = ["logs", "killfeed", "kills"]
                        for subdir in subdirs:
                            try:
                                subdir_path = os.path.join(server_dir, subdir)
                                subdir_files = await sftp.listdir(subdir_path)
                                subdir_csv = [f for f in subdir_files if f.lower().endswith('.csv')]
                                
                                if subdir_csv:
                                    csv_files = [os.path.join(subdir, f) for f in subdir_csv]
                                    server_dir = server_dir  # Keep base dir the same
                                    break
                            except asyncssh.SFTPError:
                                continue
                    
                    # Download each CSV file
                    for i, csv_file in enumerate(csv_files):
                        remote_path = os.path.join(server_dir, csv_file)
                        local_path = os.path.join(temp_dir, f"{i:04d}_{os.path.basename(csv_file)}")
                        
                        try:
                            await sftp.get(remote_path, local_path)
                            temp_files.append(local_path)
                            logger.debug(f"Downloaded {remote_path} to {local_path}")
                        except asyncssh.SFTPError as e:
                            logger.warning(f"Failed to download {remote_path}: {e}")
                    
                    if not temp_files:
                        logger.warning(f"No CSV files found or downloaded for server {server.name}")
                        os.rmdir(temp_dir)  # Clean up empty dir
                        
                    return sorted(temp_files)
                    
                except Exception as e:
                    logger.error(f"Error listing or downloading CSV files: {e}")
                    # Clean up any temp files
                    for file in temp_files:
                        try:
                            os.unlink(file)
                        except:
                            pass
                    try:
                        os.rmdir(temp_dir)
                    except:
                        pass
                    return []
                    
    except Exception as e:
        logger.error(f"Error in SFTP batch file access: {e}")
        return []

async def get_newest_csv_file(server):
    """
    Get only the newest CSV file for a server
    
    Args:
        server: Server object
        
    Returns:
        str: Path to the newest CSV file, or None if not available
    """
    access_method = server.access_method
    
    if access_method == "local":
        files = await get_local_all_csv_files(server)
        if files:
            # Sort by modification time, newest first
            return sorted(files, key=os.path.getmtime, reverse=True)[0]
        return None
    elif access_method == "sftp":
        # For SFTP, we'll download all files and pick the newest
        files = await get_sftp_all_csv_files(server)
        if files:
            # For SFTP downloaded files, they're temp files named with index prefix
            # So we can just take the last one since they're sorted by name
            return files[-1]
        return None
    else:
        logger.error(f"Unsupported access method: {access_method}")
        return None

async def cleanup_temp_files():
    """Clean up any temporary files created for log parsing"""
    # This can be called periodically to clean up old temp files
    temp_dir = tempfile.gettempdir()
    try:
        for filename in os.listdir(temp_dir):
            if filename.endswith(".csv") or filename.endswith(".log"):
                file_path = os.path.join(temp_dir, filename)
                # Check file age
                if (os.path.getmtime(file_path) - os.path.getctime(file_path)) > 3600:  # 1 hour old
                    try:
                        os.unlink(file_path)
                        logger.debug(f"Cleaned up temporary file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up {file_path}: {e}")
            
            # Also clean up deadside_csv_ directories
            if os.path.isdir(os.path.join(temp_dir, filename)) and filename.startswith("deadside_csv_"):
                dir_path = os.path.join(temp_dir, filename)
                # Check directory age (1 day old)
                if (os.path.getmtime(dir_path) - os.path.getctime(dir_path)) > 86400:
                    try:
                        # Remove all files in directory
                        for subfile in os.listdir(dir_path):
                            os.unlink(os.path.join(dir_path, subfile))
                        # Remove directory
                        os.rmdir(dir_path)
                        logger.debug(f"Cleaned up temporary directory: {dir_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up directory {dir_path}: {e}")
    
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {e}")
