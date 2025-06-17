import requests


class AuthClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def ping(self):
        url = f'{self.base_url}/ping'
        response = requests.get(url)
        response.raise_for_status()
        return response.text
