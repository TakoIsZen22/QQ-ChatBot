"""固定来源、SHA256 校验的公开组件下载与安全 ZIP 解压。无账户或密钥处理。"""
import hashlib
import json
import re
import shutil
import stat
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

HOSTS={'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com',
       'qqdl.gtimg.cn','www.python.org'}


def catalog(root):return json.loads((Path(root)/'config/runtime-downloads.json').read_text(encoding='utf-8-sig'))


def checked_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in HOSTS or p.username or p.password or p.port not in (None,443):
        raise ValueError('组件只能从已登记的官方 HTTPS 下载地址获取')
    return url


class TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        checked_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def download(entry,folder,progress=lambda *args:None,timeout=45):
    url=checked_url(entry['url']);sha=entry['sha256']
    if not re.fullmatch('[a-f0-9]{64}',sha):raise ValueError('缺少有效的组件 SHA256')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    target=folder/(sha+Path(urlsplit(url).path).suffix)
    if target.is_file() and target.stat().st_size<=entry['max_bytes'] and digest(target)==sha:return target
    part=target.with_suffix(target.suffix+'.part')
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'QQ-ChatBot-Setup/1'})
        with urllib.request.build_opener(TrustedRedirect()).open(req,timeout=timeout) as response,part.open('wb') as out:
            checked_url(response.geturl());total=int(response.headers.get('Content-Length') or 0);size=0
            if total>entry['max_bytes']:raise ValueError('组件大小超过限制')
            while block:=response.read(256*1024):
                size+=len(block)
                if size>entry['max_bytes']:raise ValueError('组件大小超过限制')
                out.write(block);progress(size,total)
        if digest(part)!=sha:raise ValueError('组件 SHA256 不匹配，已拒绝安装；请重试或检查官方版本')
        part.replace(target);return target
    finally:
        if part.exists():part.unlink()


def safe_zip(archive,destination,limits):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        rows=z.infolist();names=set()
        if len(rows)>limits['max_files'] or sum(r.file_size for r in rows)>limits['max_unpacked_bytes']:
            raise ValueError('解压内容超过限制')
        for row in rows:
            name=row.filename;parts=PurePosixPath(name).parts;mode=row.external_attr>>16
            if not parts or name.startswith(('/','\\')) or '\\' in name or ':' in name or '..' in parts or stat.S_ISLNK(mode):
                raise ValueError('压缩包包含不安全路径')
            if any(p.rstrip(' .')!=p or p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for p in parts):
                raise ValueError('压缩包包含不安全 Windows 文件名')
            key=name.rstrip('/').casefold()
            if key in names:raise ValueError('压缩包包含重复路径')
            names.add(key)
            if not (destination/name).resolve().is_relative_to(destination):raise ValueError('解压路径越界')
        for row in rows:
            target=destination/row.filename
            if row.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(row) as source,target.open('xb') as out:shutil.copyfileobj(source,out)
