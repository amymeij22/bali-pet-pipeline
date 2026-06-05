import sys
import os

print("--- Running Smoke Test ---")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

# 1. Verifikasi import biometeo & pemanggilan fungsi intinya
try:
    import biometeo
    print("SUCCESS: biometeo imported successfully.")
    
    # Panggil fungsi inti Tmrt_calc
    tmrt = biometeo.Tmrt_calc(Ta=25.0, RH=50.0, v=1.0, longitude=115.0, latitude=-8.0, sea_level_height=50.0)
    print(f"SUCCESS: biometeo.Tmrt_calc call OK (result: {tmrt})")
    
    # Panggil fungsi inti mPET
    mpet = biometeo.mPET(Ta=25.0, VP=15.0, Tmrt=30.0, v=1.0)
    print(f"SUCCESS: biometeo.mPET call OK (result: {mpet})")
except Exception as e:
    print(f"FAILED: biometeo package verification failed: {e}")
    sys.exit(1)

# 2. Verifikasi struktur package biometeo_worker
try:
    # Memastikan path src terdaftar jika script dijalankan langsung
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        
    from biometeo_worker.main import BIOMETEO_VERSION
    from biometeo_worker.config import Settings
    
    print(f"SUCCESS: biometeo_worker structure imported successfully. Version: {BIOMETEO_VERSION}")
except Exception as e:
    print(f"FAILED: biometeo_worker package structure import failed: {e}")
    sys.exit(1)

print("--- Smoke Test Passed Successfully ---")
sys.exit(0)
