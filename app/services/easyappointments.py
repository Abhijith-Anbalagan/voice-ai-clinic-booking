import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

EA_BASE_URL = os.getenv("EA_BASE_URL", "").rstrip("/")
EA_USERNAME = os.getenv("EA_USERNAME", "")
EA_PASSWORD = os.getenv("EA_PASSWORD", "")
EA_API_KEY = os.getenv("EA_API_KEY", "")


class EasyAppointmentsClient:
    def __init__(self):
        self.base = EA_BASE_URL

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if EA_API_KEY:
            headers["Authorization"] = f"Bearer {EA_API_KEY}"
        return headers

    def _auth(self):
        if EA_USERNAME and EA_PASSWORD and not EA_API_KEY:
            return HTTPBasicAuth(EA_USERNAME, EA_PASSWORD)
        return None

    def get_availabilities(self, provider_id: int, service_id: int, date_str: str):
        url = f"{self.base}/index.php/api/v1/availabilities"
        r = requests.get(
            url,
            params={"providerId": provider_id, "serviceId": service_id, "date": date_str},
            headers=self._headers(),
            auth=self._auth(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def list_appointments(self):
        url = f"{self.base}/index.php/api/v1/appointments"
        r = requests.get(url, headers=self._headers(), auth=self._auth(), timeout=30)
        r.raise_for_status()
        return r.json()

    def create_customer(self, customer: dict):
        url = f"{self.base}/index.php/api/v1/customers"
        r = requests.post(url, json=customer, headers=self._headers(), auth=self._auth(), timeout=30)
        r.raise_for_status()
        return r.json()

    def create_appointment(self, appointment: dict):
        url = f"{self.base}/index.php/api/v1/appointments"
        r = requests.post(url, json=appointment, headers=self._headers(), auth=self._auth(), timeout=30)
        r.raise_for_status()
        return r.json()