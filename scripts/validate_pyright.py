import subprocess
import json
import sys
import os

def run_pyright():
    """
    Run Pyright type checking and validate against standards.
    
    Returns:
        bool: True if validation passes, False otherwise
    """
    
    # Run Pyright with JSON output
    result = subprocess.run(['pyright', '--outputjson'], 
                          capture_output=True, text=True)
    
    # Parse the JSON output
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Error: Pyright output is not valid JSON")
        return False
    
    # Check for errors and warnings
    error_count = report['summary']['errorCount']
    warning_count = report['summary']['warningCount']
    
    print(f"Pyright analysis complete:")
    print(f"  Errors: {error_count}")
    print(f"  Warnings: {warning_count}")
    print(f"  Files analyzed: {report['summary']['filesAnalyzed']}")
    
    # For production, we want zero errors and minimal warnings
    if error_count > 0:
        print(f"ERROR: {error_count} type errors found. Fix these before proceeding.")
        return False
    
    if warning_count > 0:
        print(f"WARNING: {warning_count} type warnings found. Consider addressing these.")
        # In production, we might want to fail on warnings too
        # return False
    
    print("Pyright validation passed successfully")
    return True


def main():
    """
    Main entry point for the validation script.
    """
    # Check if we're in the correct directory
    if not os.path.exists("pyrightconfig.json"):
        print("Error: pyrightconfig.json not found in current directory")
        sys.exit(1)
    
    # Run Pyright validation
    if not run_pyright():
        sys.exit(1)
    
    # If we get here, validation passed
    sys.exit(0)


if __name__ == "__main__":
    main()

