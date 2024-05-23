import sys
import requests
import time
import json
import os
import zipfile
import subprocess
from bs4 import BeautifulSoup

def get_channel_update_id(channel, max_retries=5, retry_delay=5):
    url = f"https://uupdump.net/fetchupd.php?arch=amd64&ring={channel}"
    
    # Retry loop
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad status codes
            
            soup = BeautifulSoup(response.text, 'html.parser')
            updates = soup.find_all('tr')

            highest_build = 0
            update_id = None

            for update in updates:
                name_tag = update.find('a')
                id_tag = update.find('code')
                if name_tag and id_tag and name_tag.text.startswith("Windows"):
                    build_match = re.search(r'\((\d+\.\d+)\)', name_tag.text)
                    if build_match:
                        build_str = build_match.group(1)
                        build = float(build_str.replace('.', ''))
                        if build > highest_build:
                            highest_build = build
                            update_id = id_tag.text.strip()
            
            subprocess.run(["echo", f"build={highest_build} >> $GITHUB_OUTPUT"], shell=True)
            return update_id
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                print(f"Too many requests. Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
                continue
            else:
                raise  # Raise other HTTP errors
            
        except Exception as e:
            print(f"An error occurred: {e}")
            continue

    # If max retries reached without success
    print(f"Failed to get update ID after {max_retries} attempts.")
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

def download_update(update_id, lang, editions, max_retries=5, retry_delay=5):
    editions_str = ';'.join(editions)
    url = f"https://uupdump.net/get.php?id={update_id}&pack={lang}&edition={editions_str}&arch=amd64"
    
    # Define the payload
    download_package_body = {
        'autodl': 2,  # Assuming no virtual editions
        'updates': 1,
        'cleanup': 1
    }
    
    # Retry loop
    for attempt in range(max_retries):
        try:
            # Send POST request to download the package
            response = requests.post(url, data=download_package_body)
            response.raise_for_status()  # Raise an error for bad status codes
            
            # Save the downloaded file
            filename = f"update_{update_id}.zip"
            with open(filename, 'wb') as file:
                file.write(response.content)
            
            print(f"Downloaded file to {filename}")
            return filename
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                print(f"Too many requests. Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
                continue
            else:
                raise  # Raise other HTTP errors
            
    # If max retries reached without success
    print(f"Failed to download after {max_retries} attempts.")
    return None

def extract_zip(file_path, extract_to):
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted {file_path} to {extract_to}")

def replace_powershell_with_pwsh(file_path):
    try:
        # Read the content of the file
        with open(file_path, 'r') as file:
            content = file.read()

        # Replace "powershell" with "pwsh"
        modified_content = content.replace("powershell", "pwsh")

        # Write the modified content back to the file
        with open(file_path, 'w') as file:
            file.write(modified_content)

        print(f"Successfully replaced 'powershell' with 'pwsh' in {file_path}")
    except Exception as e:
        print(f"An error occurred while replacing 'powershell' with 'pwsh': {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: get.py <channel>")
        sys.exit(1)

    channel = sys.argv[1]
    print(f"Checking updates for channel: {channel}")

    latest_update_id = get_channel_update_id(channel)
    if latest_update_id is None:
        print(f"No Windows updates found for channel: {channel}")
        sys.exit(1)

    stored_update_id = load_stored_update_id(channel)

    if stored_update_id == latest_update_id:
        print(f"No new updates for channel: {channel}")
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

        replace_powershell_with_pwsh("work\\uup_download_windows.cmd")

if __name__ == "__main__":
    main()
