# git_statistics.py
import datetime
import sys
from collections import defaultdict

import requests

"""git仓库地址"""
root_url = "http://sourcecode.jsbchina.cn"
"""在git上设置的token"""
token = "KLX6GbczQrSJS7XJBDk5"
"""统计的开始日期"""
start_day = "20251101"
"""统计的结束日期"""
end_day = "20251201"

"""统计的时间区间-开始日期，datetime对象"""
start_date = datetime.datetime.strptime(start_day, '%Y%m%d')
"""统计的时间区间-结束日期，datetime对象"""
end_date = datetime.datetime.strptime(end_day, '%Y%m%d')

"""根据full_path包含的仓库"""
include_paths = ('GJ_2808', 'ZGPT_8331', 'FFT_8333')

"""哪些仓库路径前缀要排除"""
exclude_prefix = ()

"""哪些项目要排除"""
exclude_project = ()


def get_page(url, page, per_page):
    response = requests.get(f"{url}&page={page}&per_page={per_page}")
    list = response.json()
    if len(list) == per_page:
        list.extend(get_page(url, page + 1, per_page))
    return list

def get_all_commits(repository):
    """该仓库指定时间内，默认分支的所有提交"""
    since_date = start_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    until_date = end_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    user_dict = defaultdict(list)
    for branch in get_branches(repository):
        url = f"{root_url}/api/v4/projects/{repository.id}/repository/commits?ref_name={branch['name']}&since={since_date}&until={until_date}&private_token={token}"
        #print(url)
        #response = requests.get(url)
        commits = get_page(url, 1, 100)
        if len(commits) == 0:
            continue
        else:
            print(f"[{branch['name']}] commits: {len(commits)}, last: {branch['commit']['committer_name']} {branch['commit']['committed_date'][:-10]}")
        # 根据提交用户分组
        for commit_record in commits:
            commit = Commit()
            commit.id = commit_record['id']
            commit.repository_name = repository.name
            commit.committer_name = commit_record['committer_name']
            commit.committer_email = commit_record['committer_email']
            user_dict[commit.committer_email].append(commit)
    return user_dict


def get_commit_stats(repository_id, commit_id):
    """获取每个提交的明细"""
    url = f"{root_url}/api/v4/projects/{repository_id}/repository/commits/{commit_id}?private_token={token}"
    response = requests.get(url)
    #print(url, response.status_code, response.text)
    stats = CommitStats()
    if response.status_code == 200:
        detail = response.json()
        if len(detail['parent_ids']) > 1:
            return stats
        stats.total = detail['stats']['total']
        stats.deletions = detail['stats']['deletions']
        stats.additions = detail['stats']['additions']
        return stats
    else:
        print(f"{url}{response.status_code}{response.text}")
        return stats


def get_branches(repository):
    url = f"{root_url}/api/v4/projects/{repository.id}/repository/branches?private_token={token}"
    response = requests.get(url)
    branches = []
    if response.status_code == 200:
        list = response.json()
        for branch in list:
            last_active_time = datetime.datetime.strptime(branch['commit']['committed_date'][:-10], "%Y-%m-%dT%H:%M:%S")
            if last_active_time < start_date:
                continue
            #print(f"[{repository.name}/{branch['name']}] last: {branch['commit']['committer_name']} {branch['commit']['committed_date'][:-10]}")
            branches.append(branch)
    else:
        print(f"{url}{response.status_code}{response.text}")
    return branches


def start():
    """启动统计"""
    repositories = []
    res = get_page(f"{root_url}/api/v4/projects?private_token={token}", 1, 100)
    print(f"仓库总数量：{len(res)}, ", end='')
    #if len(res) <= 0:
        #break
    # 先遍历所有的仓库
    for e in res:
        last_active_time = datetime.datetime.strptime(e['last_activity_at'][:-10], "%Y-%m-%dT%H:%M:%S")
        #最新动态时间早于统计起始时间
        if last_active_time < start_date:
            continue
        #无提交权限的仓库
        #if not e['permissions']['project_access']:
        #    continue
        repository = Repository()
        repository.id = e['id']
        repository.name = e['name']
        repository.path = e['path_with_namespace']
        repository.web_url = e['web_url']
        repository.full_path = e['namespace']['full_path']
        repository.default_branch = e['default_branch']
        if not exclude_prefix and any(repository.name.startswith(prefix) for prefix in exclude_prefix):
            continue
        if include_paths and repository.full_path not in include_paths:
            continue
        if not exclude_project and repository.name in exclude_project:
            continue
        repositories.append(repository)
    print(f"需要统计的仓库数量: {len(repositories)}")
    #print('[')
    #for r in repositories:
    #    print(r.name, end=', ')
    #print(']')
    user_commit_statistics_list = []
    # 获取每个仓库的统计信息
    for repository in repositories:
        # 当前仓库，每个用户的所有提交记录
        print()
        print(f"********** {repository.name} *** branches **********")
        user_commits_dict = get_all_commits(repository)
        if user_commits_dict is None:
            continue
        print(f"---------- {repository.name} --- users -------------")
        for email, commits in user_commits_dict.items():
            user = CommitRepositoryUser()
            user.email = email
            user.repository_name = repository.name
            exist = []
            for commit in commits:
                # 避免重复
                if commit.id in exist:
                    continue
                exist.append(commit.id)
                user.username = commit.committer_name
                user.commit_total += 1
                stats = get_commit_stats(repository.id, commit.id)
                user.total += stats.total
                user.additions += stats.additions
                user.deletions += stats.deletions
            print(
                f"[{user.username}] commits: {user.commit_total}, lines: {user.total}({user.additions}(+){user.deletions}(-))")
            user_commit_statistics_list.append(user)
        print(f"********** {repository.name} *** finished **********")
    print(f"[{start_date} - {end_date}]统计执行完成")
    #
    # 计算每个用户的提交总数
    user_statistics_dict = defaultdict(list)
    # 每个项目的提交列表
    repository_statistics_dict = defaultdict(list)
    for ucs in user_commit_statistics_list:
        user_statistics_dict[ucs.email].append(ucs)
        repository_statistics_dict[ucs.repository_name].append(ucs)

    out_lines = []
    out_lines.append("姓名,邮箱,项目,提交数,总行数,增加行数,删除行数")
    for usl in user_statistics_dict.values():
        cru = CommitRepositoryUser()
        for us in usl:
            cru.email = us.email
            cru.username = us.username
            cru.total += us.total
            cru.additions += us.additions
            cru.deletions += us.deletions
            cru.commit_total += us.commit_total
            out_lines.append(
                f"{us.username},{us.email},{us.repository_name},{us.commit_total},{us.total},{us.additions},{us.deletions}")
        out_lines.append(
            f"{cru.username},{cru.email},合计,{cru.commit_total},{cru.total},{cru.additions},{cru.deletions}")
        out_lines.append(f"")

    with open(f'git_user_{start_day}-{end_day}.csv', mode='w', newline='', encoding='utf-8-sig') as csvfile:
        for line in out_lines:
            csvfile.write(line + "\r\n")

    # 计算每个仓库的总提交数
    repository_out_lines = []
    repository_out_lines.append("项目,提交数,总行数,增加行数,删除行数")
    for repository_name, usl in repository_statistics_dict.items():
        cru = CommitRepositoryUser()
        cru.repository_name = repository_name
        for us in usl:
            cru.total += us.total
            cru.additions += us.additions
            cru.deletions += us.deletions
            cru.commit_total += us.commit_total
        repository_out_lines.append(f"{cru.repository_name},{cru.commit_total},{cru.total},{cru.additions},{cru.deletions}")

    with open(f'git_repository_{start_day}-{end_day}.csv', mode='w', newline='', encoding='utf-8-sig') as csvfile:
        for line in repository_out_lines:
            csvfile.write(line + "\r\n")
class Repository:
    """仓库信息，只定义关注的字段"""
    id = None
    name = None
    path = None
    default_branch = None
    web_url = None
    full_path = None


class Commit:
    """提交记录"""
    id = None
    committer_name = None
    committer_email = None
    repository_name = None


class CommitStats:
    """每个提交记录的提交统计"""
    additions = 0
    deletions = 0
    total = 0


class CommitUser:
    username = None
    email = None
    additions = 0
    deletions = 0
    total = 0
    commit_total = 0


class CommitRepositoryUser(CommitUser):
    repository_name = None

if __name__ == '__main__':
    try:
        date = sys.argv[1]
        #参数1为4位以下，统计最近天数
        if len(date) < 4:
            now = datetime.datetime.now()
            start_day = datetime.datetime.strftime(now - datetime.timedelta(days=int(date)), '%Y%m%d')
            end_day = datetime.datetime.strftime(now + datetime.timedelta(days=1), '%Y%m%d')
        #参数1为4位，统计此年
        elif len(date) == 4:
            start_day = date + '0101'
            end_day = str(int(date) + 1) + '0101'
        #参数1为6位，统计此年月
        elif len(date) == 6:
            start_day = date + '01'
            start_date = datetime.datetime.strptime(start_day, '%Y%m%d')
            year = start_date.year
            month = start_date.month + 1
            if month > 12:
                year += 1
                month = 1
            end_day = str(year) + str(month) + '01'
        #参数1为8位，统计此日至今
        elif len(date) == 8:
            now = datetime.datetime.now()
            start_day = date
            end_day = datetime.datetime.strftime(now + datetime.timedelta(days=1), '%Y%m%d')
        print(f'统计区间{start_day}-{end_day}')
    except Exception as e:
        #print(e)
        #参数无或异常，统计本月
        now = datetime.datetime.now()
        year = now.year
        month = now.month + 1
        if month > 12:
            year += 1
            month = 1
        start_day = str(now.year) + str(now.month) + '01'
        end_day = str(year) + str(month) + '01'
        print(f'统计本月{start_day}-{end_day}')
    start_date = datetime.datetime.strptime(start_day, '%Y%m%d')
    end_date = datetime.datetime.strptime(end_day, '%Y%m%d')
    start()