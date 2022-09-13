
from pprint import pprint
import json
import os
import re

from pydriller import Repository

commits_list = []

dot_graph_1 = """
digraph G {
"""
dot_graph_2 = ''

# if repo not cloned yet -> Repository("https://codeberg.org/Starfish/TinyWeatherForecastGermany.git")
for commit in Repository(f"TinyWeatherForecastGermany/").traverse_commits():
    commit_dict = {}
    commit_dict['hash'] = str(commit.hash)
    commit_dict['msg'] = str(commit.msg).replace('"',"'")

    commit_dict['timestamp'] = str(commit.committer_date)

    commit_dict['author_name'] = str(commit.author.name)
    commit_dict['branches'] = list(commit.branches)
    commit_dict['parents'] = list(commit.parents)
    commit_dict['merge'] = commit.merge
    
    c_color = ''
    if commit_dict['merge']:  #'merge pull' in str(commit_dict['msg']).lower():
        c_color = ',color=blue'
    
    dot_graph_1 += f"\t\"{commit_dict['hash']}\" [label=<<B>{commit_dict['hash'][0:6]}</B>{commit_dict['author_name']}>, comment=\"{commit_dict['timestamp']}\", tooltip=\"{commit_dict['timestamp']}\n{commit_dict['msg']}\", shape=box{c_color}, URL=\"https://codeberg.org/Starfish/TinyWeatherForecastGermany/commit/{commit_dict['hash']}\"];\n"

    c_parents_len = len(commit_dict['parents'])
    if c_parents_len > 0:
        for c_parent in commit_dict['parents']:
            dot_graph_2 += f"\t \"{c_parent}\" -> \"{commit_dict['hash']}\";\n"

    commits_list.append(commit_dict)
    del commit_dict

#with open(f"test.json",'w+',encoding='utf-8') as fh:
#    fh.write(str(json.dumps(commits_list, indent=4)))

dot_graph_1 += "\n\n" + dot_graph_2 + "}"

with open(f"git_graph.dot",'w+',encoding='utf-8') as fh:
    fh.write(str(dot_graph_1))

os.system("dot -Tsvg -o git_graph.svg git_graph.dot")

svg_contents = ''
with open(f"git_graph.svg",'r',encoding='utf-8') as fh:
    svg_contents = str(fh.read())

svg_contents = re.sub(r'(?im)[\r\n]*\<!\-\-[\w \?\&\#\;\,\:\+]+\-\-\>[\r\n]*','',str(svg_contents))

with open(f"git_graph.svg",'w+',encoding='utf-8') as fh:
    fh.write(str(svg_contents))
