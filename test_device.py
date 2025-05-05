import sounddevice as sd

def get_device_info(device_id=None):
    """Prints the device information, including the number of channels."""
    # Get the list of available devices
    devices = sd.query_devices()
    
    if device_id is None:
        device_id = sd.default.device  # Default device if none is provided
    
    # Correct access to the device by index and extract relevant information
    device_info = devices[7]
    print(device_info)
    
    print(f"Device: {device_info['name']}")
    print(f"Channels supported: {device_info['max_output_channels']}")
    print(f"Default Sample Rate: {device_info['default_samplerate']}")
    
    return device_info

def check_device_channels():
    """Check the channels of the default audio device and print out its capability."""
    device_info = get_device_info()
    channels = device_info['max_output_channels']
    
    if channels == 2:
        print("This device supports 2.0 (Stereo) output.")
    elif channels == 6:
        print("This device supports 5.1 (Surround) output.")
    elif channels == 8:
        print("This device supports 7.1 (Surround) output.")
    elif channels == 5:
        print("This device supports 5.0 (Surround) output.")
    else:
        print(f"This device supports {channels} channels.")
    
if __name__ == "__main__":
    check_device_channels()
