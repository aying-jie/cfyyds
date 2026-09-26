import requests
import re
import os
import ipaddress
import random
import uuid
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ================= 配置 =================
PORT = '443'

SOURCES = {
    'https://api.uouin.com/cloudflare.html': 'Uouin',
    'https://ip.164746.xyz': 'ZXW',
    'https://ipdb.api.030101.xyz/?type=bestcf': 'IPDB',
    'https://www.wetest.vip/page/cloudflare/address_v6.html': 'WeTestV6',
    'https://ipdb.api.030101.xyz/?type=bestcfv6': 'IPDBv6',
    'https://cf.090227.xyz/CloudFlareYes': 'CFYes',
    'https://ip.haogege.xyz': 'HaoGG',
    'https://vps789.com/openApi/cfIpApi': 'VPS',
    'https://www.wetest.vip/page/cloudflare/address_v4.html': 'WeTest',
    'https://addressesapi.090227.xyz/ct': 'CMLiuss',
    'https://addressesapi.090227.xyz/cmcc-ipv6': 'CMLiussv6',
    'https://raw.githubusercontent.com/xingpingcn/enhanced-FaaS-in-China/refs/heads/main/Cf.json': 'FaaS'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ================= 工具函数 =================
def get_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.headers.update(HEADERS)
    return session


def extract_text_from_response(resp, url):
    """从响应中提取可用于正则的文本"""
    content_type = resp.headers.get('Content-Type', '').lower()
    text = resp.text

    # 1) JSON 源
    if 'application/json' in content_type or url.endswith('.json'):
        try:
            data = resp.json()

            def collect_strings(obj):
                if isinstance(obj, str):
                    return [obj]
                elif isinstance(obj, dict):
                    res = []
                    for v in obj.values():
                        res.extend(collect_strings(v))
                    return res
                elif isinstance(obj, list):
                    res = []
                    for item in obj:
                        res.extend(collect_strings(item))
                    return res
                else:
                    return [str(obj)]

            strings = collect_strings(data)
            return '\n'.join(strings)
        except Exception:
            pass  # 解析失败则继续按文本处理

    # 2) HTML 源
    if 'text/html' in content_type or '<html' in text.lower() or '<table' in text.lower():
        soup = BeautifulSoup(text, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()
        return soup.get_text(separator='\n')

    # 3) 纯文本
    return text


def extract_ips(text):
    """从文本中提取 IPv4 和 IPv6 地址"""
    ipv4_set = set()
    ipv6_set = set()

    # IPv4 正则（较严格）
    ipv4_pattern = r'\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b'
    for match in re.finditer(ipv4_pattern, text):
        ip = match.group()
        try:
            ipaddress.IPv4Address(ip)
            ipv4_set.add(ip)
        except ValueError:
            pass

    # IPv6 候选：连续包含十六进制字符和冒号的字符串
    candidates = re.findall(r'[0-9a-fA-F:]{2,}', text)
    for cand in candidates:
        if ':' not in cand:
            continue
        try:
            ip = ipaddress.IPv6Address(cand)
            ipv6_set.add(ip.compressed)
        except ValueError:
            continue

    return ipv4_set, ipv6_set


# ================= 主流程 =================
def main():
    session = get_session()

    ipv4_dict = {}
    ipv6_dict = {}

    # 北京时间
    beijing_time = datetime.utcnow() + timedelta(hours=8)
    timestamp = beijing_time.strftime('%Y%m%d_%H:%M')

    for url, shortname in SOURCES.items():
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            text = extract_text_from_response(resp, url)
            ipv4_set, ipv6_set = extract_ips(text)

            for ip in ipv4_set:
                ip_with_port = f"{ip}:{PORT}"
                if ip_with_port not in ipv4_dict:
                    comment = f"{shortname}-{uuid.uuid4().hex[-5:]}{random.randint(0, 9)}"
                    ipv4_dict[ip_with_port] = comment

            for ip in ipv6_set:
                ip_with_port = f"[{ip}]:{PORT}"
                if ip_with_port not in ipv6_dict:
                    comment = f"{shortname}-{uuid.uuid4().hex[-5:]}{random.randint(0, 9)}"
                    ipv6_dict[ip_with_port] = comment

            print(f"[OK] {url} -> IPv4: {len(ipv4_set)}, IPv6: {len(ipv6_set)}")
        except requests.RequestException as e:
            print(f"[请求错误] {url} -> {e}")
        except Exception as e:
            print(f"[解析错误] {url} -> {e}")

    # 写入 ipv4.txt
    with open('ipv4.txt', 'w', encoding='utf-8') as f4:
        f4.write(f"# ipv4.list.updated.at: {timestamp}\n")
        for ip in sorted(ipv4_dict):
            f4.write(f"{ip}#{ipv4_dict[ip]}\n")

    # 写入 ipv6.txt
    with open('ipv6.txt', 'w', encoding='utf-8') as f6:
        f6.write(f"# ipv6.list.updated.at: {timestamp}\n")
        for ip in sorted(ipv6_dict):
            f6.write(f"{ip}#{ipv6_dict[ip]}\n")

    print(f"✅ IPv4 写入 ipv4.txt，共 {len(ipv4_dict)} 个")
    print(f"✅ IPv6 写入 ipv6.txt，共 {len(ipv6_dict)} 个")


if __name__ == '__main__':
    main()