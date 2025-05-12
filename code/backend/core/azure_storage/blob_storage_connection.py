import logging, os
from azure.storage.blob import BlobServiceClient, ContentSettings


def connect_to_blob_storage(sas_token, account_url, container_name):
    """
    Connects to an Azure Blob Storage container using a SAS token and account URL.

    Args:
        sas_token (str): The Shared Access Signature (SAS) token for authentication.
        account_url (str): The URL of the Azure Storage account.
        container_name (str): The name of the container to connect to.

    Returns:
        ContainerClient: An instance of ContainerClient for the specified container. This can be further used to create blob client.
    """
    
    container_client = None
    if not sas_token or not account_url:
        raise ValueError("AZURE_STORAGE_SAS_TOKEN and AZURE_STORAGE_ACCOUNT_URL environment variables must be set")

    # Initialize the BlobServiceClient using the account URL and SAS token
    blob_service_client = BlobServiceClient(account_url=account_url, credential=sas_token)
    container_client = blob_service_client.get_container_client(container_name)

    return container_client

def read_from_blob_storage(container_client, file_name):
    """
    Function to read from Azure Blob Storage and download the file locally.
    
    :param file_name: Name of the file in the blob storage
    :param download_path: Local path where the file will be saved
    """
    try:
        # Specify the blob name
        blob_name = file_name

        # Get the blob client
        blob_client = container_client.get_blob_client(blob_name)

        # Set the download path to the present working directory
        # download_path = os.path.join(os.getcwd(), file_name)

        # Ensure the directory exists
        # os.makedirs(os.path.dirname(download_path), exist_ok=True)
        blob = blob_client.download_blob().readall()
        # Download the blob content and save it to a local file
        # with open(download_path, "wb") as download_file:
            
        #     download_file.write(blob)
        
        logging.info(f'File {file_name} downloaded successfully from Azure Blob Storage')
        # return the blob content
        return blob
    except Exception as e:
        logging.error(f'Failed to download file from Azure Blob Storage: {e}')
        raise e
    
def push_to_blob_storage(file_name, content_type, sas_token, account_url, container_name, tags = None, content = None, tmp_file = None):
    """ Function to push the file to Azure Blob Storage for data extraction """
        
    container_client = connect_to_blob_storage(sas_token, account_url, container_name)
    blob_client = container_client.get_blob_client(file_name)
    logging.info("Uploading file to Azure Blob Storage")
    if content:
        blob_client.upload_blob(content, content_settings=ContentSettings(content_type=content_type), overwrite=True, tags=tags)
    else:
        with open(tmp_file.name, "rb") as data:
            blob_client.upload_blob(data, content_settings=ContentSettings(content_type=content_type), overwrite=True, tags=tags)
    logging.info("File uploaded to Azure Blob Storage")
    file_path = f"{file_name}"
    return file_path


def move_blob_to_failed_folder(container_client, file_name):
    """
    Function to move a blob from the main folder to the failed folder in Azure Blob Storage.
    
    :param container_client: The container client for the Azure Blob Storage account.
    :param file_name: The name of the blob to be moved.
    """
    try:
        # Specify the blob name
        blob_name = file_name

        # Get the blob client
        blob_client = container_client.get_blob_client(blob_name)
        
        blob_split = blob_name.split('/')
        if len(blob_split) == 3:
            failed_blob_name = f"{blob_split[0]}/{blob_split[1]}/failed/{blob_split[2]}"
        else:
            failed_blob_name = f"failed/{blob_name}" 

        # Move the blob to the failed folder
        new_blob_client = container_client.get_blob_client(failed_blob_name)
        new_blob_client.start_copy_from_url(blob_client.url)

        properties = new_blob_client.get_blob_properties()
        while properties.copy.status != 'success':
            properties = new_blob_client.get_blob_properties()
        blob_client.delete_blob()
        
        logging.info(f'File {file_name} moved to failed folder in Azure Blob Storage')
        return failed_blob_name
    except Exception as e:
        logging.error(f'Failed to move file to failed folder in Azure Blob Storage: {e}')
        raise e    