import concurrent.futures
import os
import json
import sys
from multiprocessing import cpu_count
from pprint import pprint

import requests
from pydriller import Repository

forks_req = requests.get(
    "https://codeberg.org/api/v1/repos/Starfish/TinyWeatherForecastGermany/forks",
    timeout=10,
)
if forks_req.ok:
    forks_req_json = forks_req.json()
else:
    print(
        f"failed to request forks -> received unexpected status code {forks_req.status_code} -> text: {forks_req.text}"
    )
    sys.exit(0)

with open("forks-api.json", "w+", encoding="utf-8") as fh:
    fh.write(str(json.dumps(forks_req_json, indent=4)))

# with open('forks-api.json','r',encoding='utf-8') as fh:
#    forks_req_json = json.loads(str(fh.read()))

for fork_entry in forks_req_json:
    clone_url = str(fork_entry["clone_url"])
    fork_id = str(fork_entry["id"])
    os.system(
        f"cd TinyWeatherForecastGermany && git remote add fork_{fork_id} '{clone_url}'"
        f" && git fetch -a fork_{fork_id} || true"
    )

os.system("cd TinyWeatherForecastGermany && git fetch -a || true")


def get_commits_json(clone_url, fork_id):
    print(f"analyzing '{clone_url}' ... ")

    mermaid_str = """
gitGraph
    checkout main
"""
    commits_list = []

    for commit in Repository(clone_url).traverse_commits():
        commit_dict = {}
        commit_dict["hash"] = str(commit.hash)
        commit_dict["msg"] = str(commit.msg)
        commit_dict["author_name"] = str(commit.author.name)
        # commit_dict['branches'] = commit.branches

        # commit_dict['mod_files'] = []
        # for file in commit.modified_files:
        #    commit_dict['mod_files'].append(str(file.filename))

        mermaid_str += '    commit id:"' + str(commit.hash)[0:6] + '"\n'

        commits_list.append(commit_dict)
        del commit_dict

    with open(f"fork-{fork_id}.json", "w+", encoding="utf-8") as fh:
        fh.write(str(json.dumps(commits_list, indent=4)))
    del commits_list

    with open(f"fork-{fork_id}.mermaid", "w+", encoding="utf-8") as fh:
        fh.write(str(mermaid_str))


def generate_mermaid_gitgraph():
    with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_count()) as executor:
        for fork_entry in forks_req_json:
            clone_url = str(fork_entry["clone_url"])

            future = executor.submit(get_commits_json, clone_url, fork_entry["id"])
            # print(future.result())
