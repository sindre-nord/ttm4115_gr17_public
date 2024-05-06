import platform

# Check if the script is running on a Raspberry Pi
# returns True if it is, False otherwise
def script_is_running_on_pi() -> bool:
    if platform.system() == "Linux":
        try:
            # This should be present on a by
            with open("/proc/cpuinfo") as f:
                if "Raspberry Pi" in f.read():
                    if __name__ == "__main__":
                        print("Running on a Raspberry Pi")
                    return True
        except FileNotFoundError:
            if __name__ == "__main__":
                print("Not running on a Raspberry Pi")
            else:
                pass
    if __name__ == "__main__":
        print("Not running on a Raspberry Pi")
    return False