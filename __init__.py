
import concurrent.futures
from multiprocessing import cpu_count
import json

from pydriller import Repository

import requests

forks_req = requests.get(f"https://codeberg.org/api/v1/repos/Starfish/TinyWeatherForecastGermany/forks", timeout=10)
forks_req_json = forks_req.json()

with open('forks-api.json','w+',encoding='utf-8') as fh:
    fh.write(str(json.dumps(forks_req_json, indent=4)))

#with open('forks-api.json','r',encoding='utf-8') as fh:
#    forks_req_json = json.loads(str(fh.read()))

def get_commits_json(clone_url, fork_id):
    print(f"analyzing '{clone_url}' ... ")

    commits_list = []

    for commit in Repository(clone_url).traverse_commits():
        commit_dict = {}
        commit_dict['hash'] = str(commit.hash)
        commit_dict['msg'] = str(commit.msg)
        commit_dict['author_name'] = str(commit.author.name)

        #commit_dict['mod_files'] = []
        #for file in commit.modified_files:
        #    commit_dict['mod_files'].append(str(file.filename))
        
        commits_list.append(commit_dict)
        del commit_dict

    with open(f"fork-{fork_id}.json",'w+',encoding='utf-8') as fh:
        fh.write(str(json.dumps(commits_list, indent=4)))
    del commits_list

with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_count()) as executor:
    for fork_entry in forks_req_json:
        clone_url = str(fork_entry['clone_url'])

        future = executor.submit(get_commits_json, clone_url, fork_entry['id'])
        #print(future.result())
