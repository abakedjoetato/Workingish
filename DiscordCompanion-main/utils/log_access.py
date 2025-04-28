import os
import logging
import asyncssh
import aiofiles
import tempfile
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
        
        base_path = server.log_path
        
        # Determine remote file path
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
                # Try each possible file name
                for remote_file in remote_files:
                    remote_path = os.path.join(base_path, remote_file)
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
                
                # If we got here, none of the files were found
                logger.warning(f"No {log_type} files found in {base_path}")
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
    
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {e}")
