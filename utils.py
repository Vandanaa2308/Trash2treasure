import os
from werkzeug.utils import secure_filename
from config import Config

def allowed_file(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS

def save_upload(file_storage, upload_folder):
    filename = secure_filename(file_storage.filename)
    # Ensure unique name by prefixing timestamp
    import time
    fname = f"{int(time.time())}_{filename}"
    dest = os.path.join(upload_folder, fname)
    file_storage.save(dest)
    return fname