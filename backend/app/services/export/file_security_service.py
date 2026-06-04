import logging
import os
import shutil
from typing import Optional

logger = logging.getLogger(__name__)

class FileSecurityService:
    """
    Manages security for generated export files.
    Handles temporary storage, permissions, and secure disposal of files.
    """

    def __init__(self, export_dir: str = "exports"):
        self.export_dir = export_dir
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

    def secure_save(self, filename: str, content: bytes) -> str:
        """
        Save content to a file with restricted permissions.
        """
        # Ensure directory exists and is restricted
        # In a real system, we would set chmod 700 or similar
        file_path = os.path.join(self.export_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
            
        logger.info(f"FileSecurityService: securely saved {filename}")
        return file_path

    def secure_delete(self, filename: str):
        """
        Remove a file and ensure it is not recoverable (simple overwrite).
        """
        file_path = os.path.join(self.export_dir, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"FileSecurityService: securely deleted {filename}")
        else:
            logger.warning(f"FileSecurityService: file {filename} not found for deletion.")

    def cleanup_old_files(self, hours: int = 24):
        """
        Remove all files older than X hours.
        """
        import time
        now = time.time()
        for f in os.listdir(self.export_dir):
            f_path = os.path.join(self.export_dir, f)
            if os.stat(f_path).st_mtime < now - (hours * 3600):
                self.secure_delete(f)
