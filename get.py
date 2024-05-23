import sys
import requests
import time
import json
import os
import zipfile
import re
from bs4 import BeautifulSoup
    
highest_build_str = 0
def get_channel_update_id(channel, max_retries=5, retry_delay=5):
    url = f"https://uupdump.net/fetchupd.php?arch=amd64&ring={channel}"
    
    # Retry loop
    E = False
    for attempt in range(max_retries):
        if E:
            return
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
                compilation = update.find('div', class_='sub header')
                if name_tag and id_tag:
                    name_tag =  re.sub(' +', ' ', name_tag.text.strip())
                    compilation_num_str = re.sub(' +', ' ', compilation.text.strip().split(" ")[-1])
                    compilation_num = float(re.sub(r'\.(?=.*\.)', '', compilation_num_str))
                    
                    if name_tag.startswith("Windows") and compilation_num > highest_build:
                        highest_build = compilation_num
                        global highest_build_str
                        highest_build_str = compilation_num_str
                        
                        id_tag_text = re.sub(' +', ' ', id_tag.text.strip())
                        update_id = id_tag_text
            
            return update_id
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                print(f"Too many requests. Waiting {retry_delay} seconds before retrying...", flush=True)
                time.sleep(retry_delay)
                continue
            else:
                E=True
                raise  # Raise other HTTP errors
   
        except Exception as e:
            E=True
            print(f"An error occurred: {e}", flush=True)
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

def load_opts():
    if not os.path.exists("opts.json"):
        raise FileNotFoundError("opts.json not found")

    with open("opts.json", "r") as file:
        data = json.load(file)
        return data.get("lang", "en-US"), data.get("editions", ["core", "professional"])

def download_update(update_id, lang, editions, arch, max_retries=5, retry_delay=5):
    editions_str = ';'.join(editions)
    url = f"https://uupdump.net/get.php?id={update_id}&pack={lang}&edition={editions_str}&arch={arch}"
    
    # Define the payload
    download_package_body = {
        'autodl': 2,
        'updates': 1,
        'cleanup': 1,
        'netfx': 1,
        'esd': 1
    }
    
    # Retry loop
    for attempt in range(max_retries):
        try:
            # Send POST request to download the package
            response = requests.post(url, data=download_package_body)
            response.raise_for_status()  # Raise an error for bad status codes
            
            # Save the downloaded file
            filename = f"windows-{arch}-{lang}.zip"
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
        print(f"No Windows version found for channel: {channel}")
        sys.exit(1)

    stored_update_id = load_stored_update_id(channel)

    if stored_update_id == latest_update_id:
        print(f"No new updates for channel: {channel}")
    else:
        print(f"New update found for channel: {channel}")
        print(f"New Update ID: {latest_update_id}")
        print(f"New Update Build: {highest_build_str}")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print(f'build={highest_build_str}', file=fh)
            print(f'buildId={latest_update_id}', file=fh)

        # Load language and editions from opts.json and download the update
        lang, editions = load_opts()
        zip_file_path = download_update(latest_update_id, lang, editions, 'amd64')
        zip_file_path_2 = download_update(latest_update_id, lang, editions, 'arm64')

        # Extract the downloaded zip file to the "work" folder
        extract_zip(zip_file_path, "work-x64")
        extract_zip(zip_file_path_2, "work-arm64")

        replace_powershell_with_pwsh("work-x64\\uup_download_windows.cmd")
        replace_powershell_with_pwsh("work-arm64\\uup_download_windows.cmd")

if __name__ == "__main__":
    main()
