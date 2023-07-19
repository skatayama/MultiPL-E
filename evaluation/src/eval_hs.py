from pathlib import Path
from safe_subprocess import run

def eval_script(path: Path):
    r = run(["runhaskell", path])
    
    if r.timeout:
        status = "Timeout"
    elif r.exit_code != 0:
        status = "Exception"
    elif "error" in r.stdout or "error" in r.stderr:
        status = "Exception"
    else:
        status = "OK"
    return {
        "status": status,
        "exit_code": r.exit_code,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }
