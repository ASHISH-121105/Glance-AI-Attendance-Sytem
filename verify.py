import sys

print("Checking package imports...\n")

packages = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scikit-learn": "sklearn",
    "dlib-bin": "dlib",
    "face_recognition_models": "face_recognition_models",
    "supabase": "supabase",
    "bcrypt": "bcrypt",
    "segno": "segno",
    "pillow": "PIL",
    "streamlit": "streamlit"
}

failed = []

for pip_name, import_name in packages.items():
    try:
        __import__(import_name)
        print(f"✅ {pip_name:<25} -> Import Successful")
    except ImportError as e:
        print(f"❌ {pip_name:<25} -> IMPORT FAILED ({e})")
        failed.append(pip_name)

print("\n" + "="*40)
if not failed:
    print("🎉 All systems go! Everything is installed and working perfectly.")
else:
    print(f"⚠️ Verification failed for: {', '.join(failed)}")
    print("Please reinstall the failed packages using 'pip install <package_name>'.")