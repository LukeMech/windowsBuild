import json
import sys

def save_update_id(channel, update_id):
    data = {}
    if os.path.exists("built.json"):
        with open("built.json", "r") as file:
            data = json.load(file)

    data[channel] = update_id

    with open("built.json", "w") as file:
        json.dump(data, file, indent=4)
        
def main():
    if len(sys.argv) != 3:
        print("Usage: updateBuild.py <channel> <newId>")
        sys.exit(1)
        
    channel = sys.argv[1]
    update_id = sys.argv[2]
    
    save_update_id(channel, update_id)