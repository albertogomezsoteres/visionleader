"""Stop the API if it is running on port 8000."""

import subprocess


def find_process_on_port(port):
    """Find the PID of the process using the port."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True
        )

        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    return pid
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def kill_process(pid):
    """Kill a process by its PID."""
    try:
        subprocess.run(["taskkill", "/F", "/PID", pid], check=True)
        return True
    except Exception as e:
        print(f"Error stopping process: {e}")
        return False


if __name__ == "__main__":
    port = 8000
    print(f"Looking for a process on port {port}...")

    pid = find_process_on_port(port)

    if pid:
        print(f"Process found: PID {pid}")
        answer = input("Stop this process? (y/n): ")
        if answer.lower() == 'y':
            if kill_process(pid):
                print(f"[OK] Process {pid} stopped")
            else:
                print("[ERROR] Could not stop the process")
        else:
            print("Cancelled")
    else:
        print(f"No process found using port {port}")
