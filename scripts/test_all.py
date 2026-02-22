import subprocess
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def run_command(cmd, env=None):
    print(f"\n================================================")
    print(f"🚀 Running: {' '.join(cmd)}")
    print(f"================================================\n")
    
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
        
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=run_env)
    
    if result.returncode != 0:
        print(f"\n❌ FAILED: {' '.join(cmd)}")
        return False
    
    print(f"\n✅ PASSED: {' '.join(cmd)}")
    return True

def main():
    print("Beginning Master Verification Suite...")
    
    all_passed = True
    
    # 1. Run the unified pytest suite
    print("\n--- 1. Pytest API & Integration Suite ---")
    if not run_command([sys.executable, "-m", "pytest", "tests/", "-v"]):
        all_passed = False
        
    # 2. Run standalone scripts that use custom execution loops
    standalone_scripts = [
        "tests/test_memory_phase3.py",
        "tests/test_memory_phase4.py",
        "tests/test_memory_script.py", 
        "tests/test_stress_db.py"
    ]
    
    print("\n--- 2. Standalone Application & DB Scripts ---")
    for script in standalone_scripts:
        if not run_command([sys.executable, script]):
            all_passed = False
            
    if all_passed:
        print("\n🎉 SUMMARY: ALL TEST PHASES PASSED SUCCESSFULLY! 🎉")
        sys.exit(0)
    else:
        print("\n💥 SUMMARY: ONE OR MORE TEST PHASES FAILED! 💥")
        sys.exit(1)

if __name__ == "__main__":
    main()
