import sys
import requests
import json
from bs4 import BeautifulSoup
import os
import zipfile
import subprocess

def get_channel_update_id(channel):
    url = f"https://api.uupdump.net/fetchupd.php?ring={channel}"
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad status codes
    data = response.json()

    updates = data.get("response", {}).get("updateArray", [])
    for update in updates:
        if update["updateTitle"].startswith("Windows"):
            return update["updateId"]
    return None

def load_stored_update_id(channel):
    if not os.path.exists("built.json"):
        return None

    with open("built.json", "r") as file:
        data = json.load(file)
        return data.get(channel)

def save_update_id(channel, update_id):
    data = {}
    if os.path.exists("built.json"):
        with open("built.json", "r") as file:
            data = json.load(file)

    data[channel] = update_id

    with open("built.json", "w") as file:
        json.dump(data, file, indent=4)

def load_opts():
    if not os.path.exists("opts.json"):
        raise FileNotFoundError("opts.json not found")

    with open("opts.json", "r") as file:
        data = json.load(file)
        return data.get("lang", "en-US"), data.get("editions", ["core", "professional"])

def download_update(update_id, lang, editions):
    editions_str = ';'.join(editions)
    url = f"https://uupdump.net/download.php?id={update_id}&pack={lang}&edition={editions_str}"
    
    # Fetch the page content
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad status codes
    
    # Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find checkboxes with class 'checked' for parameters 'esd', 'netfx', 'cleanup', and 'updates'
    checkboxes = soup.find_all('input', {'name': ['esd', 'netfx', 'cleanup', 'updates'], 'class': 'checked'})
    
    # Find the submit button
    submit_button = soup.find('input', {'type': 'submit'})
    
    # If checkboxes and submit button found, continue
    if checkboxes and submit_button:
        # Create payload with checked checkboxes
        payload = {checkbox['name']: 'checked' for checkbox in checkboxes}
        
        # Send POST request to download the file
        download_response = requests.post(url, data=payload)
        download_response.raise_for_status()  # Raise an error for bad status codes
        
        # Assuming the file is in the response content, you can save it
        filename = f"update_{update_id}.zip"
        with open(filename, 'wb') as file:
            file.write(download_response.content)
        
        print(f"Downloaded file to {filename}")
        return filename
    else:
        print("Checkboxes or submit button not found.")
        return None

def extract_zip(file_path, extract_to):
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted {file_path} to {extract_to}")

def main():
    if len(sys.argv) != 2:
        print("Usage: get.py <channel>")
        sys.exit(1)

    channel = sys.argv[1]
    print(f"Checking updates for channel: {channel}")

    latest_update_id = get_channel_update_id(channel)
    if latest_update_id is None:
        print(f"No Windows updates found for channel: {channel}")
        subprocess.run(["echo", "needsUpd=false >> $GITHUB_OUTPUT"], shell=True)
        sys.exit(1)

    stored_update_id = load_stored_update_id(channel)

    if stored_update_id == latest_update_id:
        print(f"No new updates for channel: {channel}")
        subprocess.run(["echo", "needsUpd=false >> $GITHUB_OUTPUT"], shell=True)
    else:
        print(f"New update found for channel: {channel}")
        print(f"Old Update ID: {stored_update_id}")
        print(f"New Update ID: {latest_update_id}")
        save_update_id(channel, latest_update_id)

        # Load language and editions from opts.json and download the update
        lang, editions = load_opts()
        zip_file_path = download_update(latest_update_id, lang, editions)

        # Extract the downloaded zip file to the "work" folder
        extract_zip(zip_file_path, "work")

        subprocess.run(["echo", "needsUpd=true >> $GITHUB_OUTPUT"], shell=True)

if __name__ == "__main__":
    main()
