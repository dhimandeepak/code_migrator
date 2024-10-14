import requests
import json

def get_current_version():
    return "1.0"

def get_target_version(framework):
    print('calling get_target_version '+framework)

    if framework=='spring':
        return get_latest_release('spring-projects', 'spring-boot')
    elif framework=='Vert.x':
        return "4.5.6"
    else: 
        return "Framework not supported"

def get_migration_steps(current_version, target_version):
    return "Migrate from 1.0 to 4.0"


def get_latest_tag(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}/tags'
    response = requests.get(url)

    if response.status_code == 200:
        tags = response.json()
        print(json.dumps(tags, indent=4))
        if tags:
            latest_tag = tags[0]['name']  # The latest tag is usually the first in the list
            return latest_tag
        else:
            return "No tags found."
    else:
        return f"Error: {response.status_code} - {response.text}"

def get_latest_release(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}/releases/latest'
    response = requests.get(url)

    if response.status_code == 200:
        release_info = response.json()
        return release_info['tag_name']
    else:
        return f"Error: {response.status_code} - {response.text}"
    