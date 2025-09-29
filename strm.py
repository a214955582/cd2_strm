from flask import Flask, request, jsonify
import os, shutil, logging, subprocess, signal, time
import asyncio, requests


def check_port(port):
    """检查指定端口是否被占用"""
    try:
        # 使用ss命令检查端口占用情况(比netstat更高效)
        result = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True)
        return f':{port} ' in result.stdout
    except FileNotFoundError:
        # 如果ss命令不存在，尝试使用netstat
        try:
            result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
            return f':{port} ' in result.stdout
        except FileNotFoundError:
            print("错误：找不到ss或netstat命令")
            return False


def find_pid_by_port(port):
    """查找使用指定端口的进程PID"""
    try:
        # 使用lsof命令精确查找端口对应的PID
        cmd = f"sudo netstat -tulnp | grep {port}"
        output = subprocess.check_output(cmd, shell=True, text=True).strip()
        print(output)
        if output:
            return int(output.split('\n')[0])  # 返回第一个PID
    except subprocess.CalledProcessError:
        pass
    return None


def kill_process(pid):
    """终止指定PID的进程"""
    try:
        os.kill(pid, signal.SIGTERM)  # 先尝试优雅终止
        print(f"已发送终止信号给进程 {pid}")

        # 等待3秒检查进程是否已终止
        try:
            os.kill(pid, 0)  # 检查进程是否存在
            print(f"进程 {pid} 未响应终止信号，尝试强制终止...")
            os.kill(pid, signal.SIGKILL)  # 强制终止
        except OSError:
            print(f"进程 {pid} 已成功终止")
            return True

    except OSError as e:
        print(f"终止进程 {pid} 失败: {e}")
        return False
    return True


def strm_port(port: int):
    if not check_port(port):
        print(f"端口 {port} 未被占用")
        return

    print(f"端口 {port} 已被占用")
    pid = find_pid_by_port(port)

    if pid:
        print(f"找到占用端口的进程: PID={pid}")
        if kill_process(pid):
            print("进程终止成功")
        else:
            print("进程终止失败")
    else:
        print("无法找到占用该端口的进程")


async def create_strm(output_path: str, media_url: str):
    """
    生成.strm文件
    :param output_path: 文件保存路径（如 "/path/to/movie.strm"）
    :param media_url: 媒体流URL（如 "http://example.com/movie.mp4"）
    """
    media_extensions = ['.mkv', '.iso', '.ts', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv',
                        '.rm', '.mov', '.srt']

    for extension in media_extensions:
        if extension in media_url:
            output_path = os.path.splitext(output_path)[0] + '.strm'

            media_url = strm_prefix + media_url

            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # # 写入URL内容
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(media_url)

            print(f"成功生成: {output_path}")
            return f"成功生成: {output_path}"


async def delete_strm(output_path: str, media_url: str):
    output_path = os.path.dirname(output_path)
    pattern = os.path.splitext(media_url.split('/')[-1])[0]

    deleted_files = 0
    media_extensions = ['.mkv', '.iso', '.ts', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv',
                        '.rm', '.mov', '.srt']

    for extension in media_extensions:
        if extension in media_url:
            for root, dirs, files in os.walk(output_path):
                for file in files:
                    if pattern in file:
                        file_path = os.path.join(root, file)
                        try:
                            os.remove(file_path)
                            print(f"已删除: {file_path}")
                            deleted_files += 1
                        except Exception as e:
                            print(f"删除失败 {file_path}: {e}")

            print(f"操作完成，共删除 {deleted_files} 个文件")
            return f"操作完成，共删除 {deleted_files} 个文件"


async def create_dir(output_path: str):
    try:
        os.makedirs(output_path)
        print(f'文件夹创建成功：{output_path}')
    except FileExistsError:
        print(f'文件夹已存在：{output_path}')


async def delete_dir(output_path: str):
    try:
        shutil.rmtree(output_path)
        print(f'文件夹删除成功：{output_path}')
    except FileNotFoundError:
        print(f'文件夹不存在：{output_path}')


def get_library_ids(EMBY_URL: str, EMBY_API_KEY: str):
    url = f"{EMBY_URL}/emby/Library/MediaFolders?api_key={EMBY_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for folder in data['Items']:
            emby_ids[folder['Name']] = folder['Id']
        print(emby_ids)
    else:
        print(f"Error: {response.status_code}")


def scan_specific_library(server_url, api_key, library_name, library_id):
    """
    扫描特定媒体库
    :param server_url: Emby 服务器地址
    :param api_key: Emby API 密钥
    :param library_id: 要扫描的媒体库ID
    """
    url = f"{server_url}/emby/Items/{library_id}/Refresh"

    params = {
        "api_key": api_key,
        "Recursive": "true"  # 是否递归扫描子目录
    }

    try:
        response = requests.post(url, params=params)
        if response.status_code == 204:
            print(f"成功触发媒体库 {library_name} 扫描")
            return True
        else:
            print(f"扫描失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"请求出错: {str(e)}")
        return False

def get_all_files(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)  # 完整路径
            file_list.append(file_path)
    return file_list


app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # 设置为 ERROR 或更高等级以屏蔽常规请求日志


@app.route('/file_notify', methods=['POST'])
def api():
    try:
        data = request.get_json()
        # print("Received data:", data)  # 查看解析结果
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(
            f"{now} 收到设备消息：{data['device_name']},  动作：{data['data'][0]['action']},  源路径：{data['data'][0]['source_file']},  目的路径：{data['data'][0]['destination_file']}")

        for task in data['data']:
            source_file = task['source_file']
            destination_file = task['destination_file']

            if task['action'] == 'create' and task['is_dir'] == 'false':
                asyncio.run(create_strm(local_path + source_file, source_file))
            elif task['action'] == 'delete' and task['is_dir'] == 'false':
                asyncio.run(delete_strm(local_path + source_file, source_file))
            elif task['action'] == 'create' and task['is_dir'] == 'true':
                asyncio.run(create_dir(local_path + source_file))
            elif task['action'] == 'delete' and task['is_dir'] == 'true':
                asyncio.run(delete_dir(local_path + source_file))
            elif task['action'] == 'rename' and task['is_dir'] == 'false':
                asyncio.run(delete_strm(local_path + source_file, source_file))
                asyncio.run(create_strm(local_path + destination_file, destination_file))
            elif task['action'] == 'rename' and task['is_dir'] == 'true':
                asyncio.run(delete_dir(local_path + source_file))
                all_files = get_all_files(strm_prefix + destination_file)
                for file_name in all_files:
                    file_name = file_name.replace(strm_prefix, '')
                    asyncio.run(create_strm(local_path + file_name,
                                            file_name))

        for name, name_id in emby_ids.items():
            dir_name = data['data'][0]['destination_file'] if data['data'][0]['destination_file'] else data['data'][0]['source_file']
            if name in dir_name:
                scan_specific_library(emby_url, emby_api_key, name, name_id)
                break

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    global local_path
    global strm_prefix
    global emby_ids
    global emby_url
    global emby_api_key

    emby_ids = dict()
    emby_url = os.getenv('EMBY_URL')
    emby_api_key = os.getenv('EMBY_API_KEY')
    local_path = os.getenv('LOCAL_PATH')
    strm_prefix = os.getenv('STRM_PREFIX')
    strm_port(18122)
    get_library_ids(emby_url, emby_api_key)
    app.run(port=18122, host='0.0.0.0', debug=False)