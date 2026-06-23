import os
import sys
import zipfile
import subprocess

def main():
    print("📦 Bat dau tien trinh dong goi (Safe Zipper)...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, "frontend")
    
    # 1. Build frontend neu co node
    try:
        if sys.platform == "win32":
            subprocess.run(["npm.cmd", "run", "build"], cwd=frontend_dir, check=True)
        else:
            subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
        print("✅ Da build Frontend thanh cong.")
    except Exception as e:
        print(f"⚠️ Khong the build Frontend tu dong (Thieu npm hoac loi): {e}")
        
    # 2. Tao file Zip
    zip_name = "NotebookLM_Mini_Release.zip"
    zip_path = os.path.join(os.path.dirname(base_dir), zip_name)
    
    excludes = [
        ".venv", "node_modules", ".git", "__pycache__", 
        "models", "storage", "uploads", ".DS_Store", "bin"
    ]
    
    print(f"🗜 Dang nen file va loai bo rac... (Luu tai {zip_path})")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            # Loc thu muc exclude
            dirs[:] = [d for d in dirs if d not in excludes]
            
            for file in files:
                if file in excludes:
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, base_dir)
                zipf.write(file_path, arcname)
                
    print(f"✅ Hoan tat! File dong goi tinh khiet nam o: {zip_path}")

if __name__ == "__main__":
    main()
