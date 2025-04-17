import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
import urllib
from urllib.parse import urlparse, parse_qs


class DocumentSource(str, Enum):
    """Document sources supported by Onyx"""
    INGESTION_API = "ingestion_api"
    SLACK = "slack"
    WEB = "web"
    GOOGLE_DRIVE = "google_drive"
    GMAIL = "gmail"
    # Add other sources as needed

class AccessType(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
    SYNC = "sync"

class OnyxIngestionException(Exception):
    """Custom exception for Onyx ingestion client errors"""
    pass

class OnyxIngestionClient:
    """Client for managing data source connections in Onyx"""
    
    def __init__(self, base_url: str, api_key: str | None = None):
        """Initialize the Onyx ingestion client
        
        Args:
            base_url: Base URL of your Onyx instance (e.g., "http://localhost:8080")
            api_key: Your Onyx API key for authentication (optional for local testing)
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
            
    def _handle_error(self, e: requests.exceptions.RequestException) -> None:
        """Helper method to handle request errors"""
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg = f"Status: {e.response.status_code}, Details: {json.dumps(error_detail)}"
            except:
                error_msg = f"Status: {e.response.status_code}, Response: {e.response.text}"
        
        print(f"DEBUG: Error response: {error_msg}")
        raise OnyxIngestionException(error_msg)

    def setup_google_app_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Set up Google app credentials (client ID, secret, etc.)"""
        try:
            response = requests.put(
                f"{self.base_url}/manage/admin/connector/google-drive/app-credential",
                headers=self.headers,
                json=credentials
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._handle_error(e)

    def create_gdrive_connector(self, name: str) -> Dict[str, Any]:
        """Create a new Google Drive connector"""
        try:
            response = requests.post(
                f"{self.base_url}/manage/admin/connector",
                headers=self.headers,
                json={
                    "name": name,
                    "source": DocumentSource.GOOGLE_DRIVE,
                    "input_type": "poll",
                    "connector_specific_config": {
                        # Use the correct key name based on the __init__ signature
                        "include_shared_drives": True, # <--- CORRECT KEY
                        # Explicitly set other desired options:
                        "include_my_drives": True,
                        "include_files_shared_with_me": True,
                        "shared_drive_urls": None,
                        "my_drive_emails": None,
                        "shared_folder_urls": None,
                    },
                    "refresh_freq": 3600,
                    "access_type": AccessType.PRIVATE,
                    "groups": []
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._handle_error(e)

    def get_gdrive_auth_url(self, credential_id: int) -> str:
        """Get Google Drive OAuth URL"""
        try:
            # 1. Get the initial auth URL from Onyx backend
            authorize_endpoint = f"{self.base_url}/manage/connector/google-drive/authorize/{credential_id}"
            print(f"DEBUG: Making initial auth request to: {authorize_endpoint}")
            print(f"DEBUG: Credential ID: {credential_id}")

            response = requests.get(authorize_endpoint, headers=self.headers)
            response.raise_for_status()
            auth_url = response.json()["auth_url"]
            print(f"DEBUG: Initial auth URL from backend: {auth_url}")

            # 2. Parse the initial URL to extract parameters
            parsed_initial_url = urlparse(auth_url)
            query_params = parse_qs(parsed_initial_url.query)

            print(f"DEBUG: Final modified auth URL for user: {auth_url}")
            state = query_params.get('state', [''])[0]
            print(f"DEBUG: State parameter being sent: {state}")

            return auth_url

        except requests.exceptions.RequestException as e:
            self._handle_error(e)

    def create_gdrive_credential(self, name: str) -> Dict[str, Any]:
        """Create a new Google Drive credential"""
        try:
            response = requests.post(
                f"{self.base_url}/manage/credential",
                headers=self.headers,
                json={
                    "credential_json": {},
                    "admin_public": True,
                    "source": DocumentSource.GOOGLE_DRIVE,
                    "name": name,
                    "curator_public": False,
                    "groups": []
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._handle_error(e)

    def create_ccpair(
        self, 
        connector_id: int,
        credential_id: int,
        name: str
    ) -> Dict[str, Any]:
        """Create connector-credential pair"""
        try:
            response = requests.put(
                f"{self.base_url}/manage/connector/{connector_id}/credential/{credential_id}",
                headers=self.headers,
                json={
                    "name": name,
                    "access_type": AccessType.PRIVATE,
                    "auto_sync_options": None,
                    "groups": []
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._handle_error(e)

    def trigger_indexing(self, connector_id: int, credential_ids: list[int], from_beginning: bool = True) -> Dict[str, Any]:
        """Trigger indexing for a connector"""
        try:
            response = requests.post(
                f"{self.base_url}/manage/admin/connector/run-once",
                headers=self.headers,
                json={
                    "connector_id": connector_id,
                    "credential_ids": credential_ids,
                    "from_beginning": from_beginning
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._handle_error(e)

    def check_endpoints(self) -> dict[str, bool]:
        """Check which key endpoints are available on your Onyx instance"""
        endpoints = {
            "admin_connector": f"{self.base_url}/manage/admin/connector",
            "admin_google_drive_app_credential": f"{self.base_url}/manage/admin/connector/google-drive/app-credential",
            "google_drive_authorize": f"{self.base_url}/manage/connector/google-drive/authorize",
            "oauth_authorize": f"{self.base_url}/connector/oauth/authorize/google_drive",
            "credentials": f"{self.base_url}/manage/credential",
            "cc_pair": f"{self.base_url}/manage/connector/{{}}/credential/{{}}"
        }
        
        results = {}
        for name, url in endpoints.items():
            try:
                # Format the cc_pair endpoint with placeholder values if needed
                actual_url = url
                if name == "cc_pair":
                    actual_url = url.format(1, 1)  # Example connector_id and credential_id
                elif name == "google_drive_authorize":
                    actual_url = f"{actual_url}/1"  # Add credential_id
                    
                response = requests.head(actual_url, headers=self.headers, timeout=10)
                # Consider 2xx and 3xx as available, 4xx might mean endpoint exists but requires auth
                results[name] = response.status_code < 400
            except requests.RequestException:
                results[name] = False
                
        print("Available endpoints:", {k: v for k, v in results.items() if v})
        print("Unavailable endpoints:", {k: v for k, v in results.items() if not v})
        return results
# Usage example with a more detailed workflow
if __name__ == "__main__":
    client = OnyxIngestionClient(base_url="http://localhost:8080")
    
    try:
        # 0. (Optional) Set up Google app credentials if not already done
        # This step needs to be done only once for your Onyx instance
        import os
        print(f"DEBUG: WEB_DOMAIN environment variable is: {os.environ.get('WEB_DOMAIN')}") 
        app_credentials = {}
        client.setup_google_app_credentials(app_credentials)
        
        # 1. Create credential first
        print("Creating Google Drive credential...")
        credential = client.create_gdrive_credential("My Google Drive Credential")
        print(f"Created credential with ID: {credential['id']}")
        credential_id = credential["id"]
        
        # 2. Get OAuth URL for this credential
        print("Getting OAuth URL...")
        auth_url = client.get_gdrive_auth_url(credential_id)
        print(f"\nIMPORTANT: User needs to visit this URL to authorize:\n{auth_url}")
        
        # 3. Wait for authorization callback
        # This would normally be handled by your web server callback route
        # For this example, we'll simulate it by asking for the code and state manually
        print("\nAfter authorization, you'll be redirected to your callback URL.")
        print("Please enter the 'code' parameter from the callback URL:")
        code = input("Code: ")
        print("Please enter the 'state' parameter from the callback URL:")
        state = input("State: ")
        
        # The callback should be automatically handled by your Onyx instance
        # so we don't need to call a method to process it
        
        # 4. Create connector
        print("\nCreating Google Drive connector...")
        connector = client.create_gdrive_connector("My Google Drive Connector")
        print(f"Created connector with ID: {connector['id']}")
        connector_id = connector["id"]
        
        # 5. Create CC pair
        print("\nLinking connector and credential...")
        ccpair = client.create_ccpair(
            connector_id=connector_id,
            credential_id=credential_id,
            name="My Google Drive Connection"
        )
        print(f"Created connector-credential pair: {ccpair}")
        
        # 6. Trigger indexing
        print("\nTriggering initial indexing...")
        indexing_result = client.trigger_indexing(
            connector_id=connector_id,
            credential_ids=[credential_id]
        )
        print(f"Indexing triggered: {indexing_result}")
        
        print("\nSetup complete! Google Drive will be indexed shortly.")
        
    except OnyxIngestionException as e:
        print(f"Error: {e}")