import requests # network requests

class Vmix_controller(): # I didn't need to have this as a seperate file, oh well.
    def __init__(self, url: str, input_channel: int, enabled: bool = True):
        self.set_url(url)
        self.input_channel = input_channel
        self.enabled = enabled
    
    def set_url(self, url: str):
        if not url.startswith("http://"): self.url = "http://" + url
        else: self.url = url
    
    def send_request(self, title: str, value: str):
        requests.post(f"{self.url}/API/?Function=SetText&Input={self.input_channel}&SelectedName={title}&Value={value}")
