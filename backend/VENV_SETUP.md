# Virtual Environment Setup Guide

## Problem Solved
The original issue was **Windows path length limitation** - file paths exceeded the 260-character limit when torch was installed in the deeply nested project directory. 

**Error:** `[WinError 206] The filename or extension is too long`

## Solution
Virtual environment created at a shorter path to bypass Windows file length limitations.

---

## Virtual Environment Location
```
C:\dev\jamsheer-venv
```

### Shorter Path Benefits
- Avoids Windows 260-character path limit
- Allows all packages including PyTorch to install correctly
- Works without admin rights

---

## How to Use

### 1. Activate the Virtual Environment (PowerShell)
```powershell
& "C:\dev\jamsheer-venv\Scripts\Activate.ps1"
```

### 2. Verify Activation
When activated, your PowerShell prompt should show:
```
(jamsheer-venv) PS C:\...>
```

### 3. Run Your Project
```powershell
# Navigate to backend directory
cd "C:\Users\U10871\Documents\Ferguson\Internal-Projects\jamsheer-KA\knowedge-assitant-jamsheer\backend"

# Run FastAPI app
python main.py

# Or use uvicorn directly
uvicorn main:app --reload
```

### 4. Deactivate (when done)
```powershell
deactivate
```

---

## Windows Command Prompt (CMD) Users
```cmd
C:\dev\jamsheer-venv\Scripts\activate.bat
```

---

## Installed Packages

### Core Framework
- **FastAPI 0.115.6** - Modern web framework
- **Uvicorn 0.34.0** - ASGI server
- **Pydantic 2.10.5** - Data validation

### Data Processing & Vision
- **NumPy 2.2.1** - Numerical computing
- **Pillow 11.1.0** - Image processing
- **OpenCV 4.10.0** - Computer vision
- **PyTesseract 0.3.13** - OCR support
- **PyTorch 2.13.0** - Deep learning

### AI & APIs
- **OpenAI 3.5.0** - OpenAI API client
- **OpenAI Whisper 20250625** - Speech recognition
- **Elasticsearch 9.5.0** - Search & indexing

### Testing
- **Pytest 8.3.4** - Testing framework
- **Pytest-asyncio 0.25.2** - Async testing support

---

## Troubleshooting

### Issue: "Script cannot be loaded"
**Solution:** If you get an execution policy error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: Python not found
**Solution:** Use full path:
```powershell
& "C:\dev\jamsheer-venv\Scripts\python.exe" your_script.py
```

### Issue: Package import errors
**Solution:** Verify the venv is activated:
```powershell
python -c "import sys; print(sys.prefix)"
# Should show: C:\dev\jamsheer-venv
```

---

## IDE Configuration

### VS Code
Create `.vscode/settings.json` in your project:
```json
{
  "python.defaultInterpreterPath": "C:\\dev\\jamsheer-venv\\Scripts\\python.exe",
  "python.linting.enabled": true
}
```

### PyCharm
1. Go to **Settings → Project → Python Interpreter**
2. Click **Add Interpreter → Add Local Interpreter**
3. Select **Existing Environment**
4. Browse to: `C:\dev\jamsheer-venv\Scripts\python.exe`

---

## Requirements Management

To update requirements:
```powershell
# After activating venv, upgrade a package
pip install --upgrade package_name

# Update requirements.txt
pip freeze > requirements.txt
```

---

## Notes
- Virtual environment is isolated and won't affect system Python
- Each project can have its own venv if needed
- All packages are from requirements.txt in the backend directory
- PyTorch CPU version is installed (no CUDA dependency)
