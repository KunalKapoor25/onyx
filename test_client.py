from onyx_ingestion_client import OnyxIngestionClient, DocumentSource, AccessType

def test_gdrive_setup():
    client = OnyxIngestionClient(
        base_url="http://localhost:8080",
        api_key="fake-key"
    )
    
    # Test the full flow
    result = client.setup_google_drive_connection(
        name="Test Drive",
        oauth_code="fake_code",
        oauth_state="fake_state"
    )
    
    print("Setup complete:", result)

if __name__ == "__main__":
    test_gdrive_setup() 