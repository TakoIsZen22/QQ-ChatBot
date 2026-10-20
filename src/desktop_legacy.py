"""零新增依赖的Windows原生桌面端。pythonw运行，不附着终端。"""
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk,messagebox
import webbrowser
from datetime import datetime
from pathlib import Path
from .core.config import ROOT,load
from .core.desktop_backend import DesktopBackend
from .core.instance import InstanceLock
from .core.identity import installed_identity

BG='#f3f8fb';INK='#173c52';BLUE='#127ea7'

class DesktopApp:
    def __init__(self,root,backend=None,auto_start=True):
        self.root=root;self.backend=backend or DesktopBackend();self.events=queue.Queue()
        self.cfg=load()
        self.identity=installed_identity(ROOT);self.nickname=self.identity.profile()['nickname']
        self.polling=False;self.last_chat=None;self.qr_image=None;self.qr_stamp=None;self.closed=False
        root.title(self.identity.title()+' · 备用界面');root.geometry('1080x760');root.minsize(820,610);root.configure(bg=BG)
        icon=self.identity.image_path('icon','ico')
        if icon.is_file():
            try:root.iconbitmap(default=str(icon))
            except tk.TclError:pass
        root.option_add('*Font',('Microsoft YaHei UI',10))
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('TFrame',background=BG);style.configure('TLabel',background=BG,foreground=INK)
        style.configure('Title.TLabel',font=('Microsoft YaHei UI',23,'bold'))
        style.configure('Sub.TLabel',foreground='#718b9a',font=('Microsoft YaHei UI',9))
        style.configure('TButton',padding=(13,9),background='white',foreground=INK,borderwidth=1)
        style.map('TButton',background=[('active','#deeff7')])
        style.configure('Primary.TButton',background=BLUE,foreground='white')
        style.map('Primary.TButton',background=[('active','#096888')])
        style.configure('Danger.TButton',foreground='#a42c40',background='#fff0f2')
        style.configure('TNotebook',background=BG,borderwidth=0)
        style.configure('TNotebook.Tab',padding=(20,10),background='#e5eef4')
        style.map('TNotebook.Tab',background=[('selected','white')])
        top=ttk.Frame(root,padding=(24,20,24,12));top.pack(fill='x')
        avatar=self.identity.image_path('portrait')
        if avatar.is_file():
            picture=tk.PhotoImage(file=str(avatar))
            self.brand_image=picture.subsample(max(1,(picture.width()+47)//48))
            ttk.Label(top,image=self.brand_image).pack(side='left',padx=(0,10))
        ttk.Label(top,text='QQ ChatBot',style='Title.TLabel').pack(side='left')
        ttk.Label(top,text=self.nickname+' · 本机伴侣，记得你，也慢慢长成自己',style='Sub.TLabel').pack(side='left',padx=20)
        self.state=tk.StringVar(value='正在连接…');ttk.Label(top,textvariable=self.state).pack(side='right')
        controls=ttk.Frame(root,padding=(24,0,24,12));controls.pack(fill='x')
        self.action_buttons=[]
        for title,fn,kind in [('启动服务',self.backend.start_all,'Primary.TButton'),('重启聊天',self.backend.restart_core,'TButton'),('停止全部',self.backend.stop_all,'TButton')]:
            b=ttk.Button(controls,text=title,style=kind,command=lambda f=fn:self.operation(f));b.pack(side='left',padx=(0,8));self.action_buttons.append(b)
        ttk.Separator(controls,orient='vertical').pack(side='left',fill='y',padx=12)
        ttk.Button(controls,text='■ 全部暂停',style='Danger.TButton',command=lambda:self.mode('paused')).pack(side='left',padx=4)
        ttk.Button(controls,text='只回复',command=lambda:self.mode('reply_only')).pack(side='left',padx=4)
        ttk.Button(controls,text='允许主动',command=lambda:self.mode('active')).pack(side='left',padx=4)
        self.notebook=ttk.Notebook(root);self.notebook.pack(fill='both',expand=True,padx=24,pady=(0,12))
        self.notebook.bind('<<NotebookTabChanged>>',self.tab_changed)
        self.chat_page=self.page('聊天');self.memory_page=self.page('记忆与日记');self.settings_page=self.page('模型与状态');self.qr_page=self.page('QQ扫码');self.log_page=self.page('运行记录')
        self.build_chat();self.build_memory();self.build_settings();self.build_qr();self.build_logs()
        self.notice=tk.StringVar(value='关闭此窗口只关闭界面；服务继续后台运行。停止服务请点「停止全部」。')
        ttk.Label(root,textvariable=self.notice,style='Sub.TLabel',padding=(24,0,24,14)).pack(fill='x')
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.drain)
        if auto_start:root.after(200,lambda:self.operation(self.backend.start_all))
        root.after(500,self.poll)

    def page(self,title):
        frame=ttk.Frame(self.notebook,padding=18);self.notebook.add(frame,text=title);return frame

    def text_box(self,parent,height=10):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        text=tk.Text(frame,height=height,wrap='word',background='white',foreground=INK,relief='flat',padx=16,pady=14,font=('Microsoft YaHei UI',11))
        bar=ttk.Scrollbar(frame,command=text.yview);text.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y');text.pack(side='left',fill='both',expand=True)
        return text

    def build_chat(self):
        self.chat=self.text_box(self.chat_page)
        self.chat.tag_configure('user',foreground='#147b9d',font=('Microsoft YaHei UI',10,'bold'),spacing1=15)
        self.chat.tag_configure('assistant',foreground='#635c95',font=('Microsoft YaHei UI',10,'bold'),spacing1=15)
        self.chat.tag_configure('body',spacing3=12,lmargin1=12,lmargin2=12)
        self.chat.configure(state='disabled')
        bottom=ttk.Frame(self.chat_page);bottom.pack(fill='x',pady=(14,0))
        self.input=tk.Text(bottom,height=3,wrap='word',background='white',foreground=INK,relief='solid',borderwidth=1,padx=10,pady=8)
        self.input.pack(side='left',fill='x',expand=True);self.input.bind('<Control-Return>',lambda e:self.send())
        ttk.Button(bottom,text='发送 ↗',style='Primary.TButton',command=self.send).pack(side='right',padx=(12,0))
        ttk.Label(self.chat_page,text='Ctrl+Enter 发送；QQ 与这里共用当前主人的记忆。',style='Sub.TLabel').pack(anchor='w',pady=(6,0))

    def build_memory(self):
        row=ttk.Frame(self.memory_page);row.pack(fill='x',pady=(0,12))
        self.memory_input=tk.StringVar();ttk.Entry(row,textvariable=self.memory_input).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='记住这件事',command=self.add_memory).pack(side='left',padx=8)
        ttk.Button(row,text='刷新',command=self.refresh_memory).pack(side='left')
        self.memories=self.text_box(self.memory_page)
        ttk.Label(self.memory_page,text='她的日记 · 每天最多三条',padding=(0,12,0,6)).pack(anchor='w')
        self.diaries=self.text_box(self.memory_page,height=6)

    def build_settings(self):
        ttk.Label(self.settings_page,text='模型使用配置中选择的兼容 API；这里不接收或显示密钥。',style='Sub.TLabel').pack(anchor='w',pady=(0,18))
        row=ttk.Frame(self.settings_page);row.pack(fill='x')
        ttk.Label(row,text='主模型').pack(side='left',padx=(0,12))
        self.model=tk.StringVar(value=load()['model']['main']);self.model_box=ttk.Combobox(row,textvariable=self.model,width=42);self.model_box.pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='读取模型清单',command=self.load_models).pack(side='left',padx=8)
        ttk.Button(row,text='保存模型',command=self.save_model).pack(side='left')
        ttk.Label(self.settings_page,text='保存后点顶部「重启聊天」，再点「只回复」。',style='Sub.TLabel').pack(anchor='w',pady=(8,18))
        self.status_text=self.text_box(self.settings_page,height=12)
        buttons=ttk.Frame(self.settings_page);buttons.pack(fill='x',pady=(12,0))
        ttk.Button(buttons,text='打开完整网页面板',command=lambda:webbrowser.open(f'http://127.0.0.1:{load()["server"]["port"]}')).pack(side='left')
        ttk.Button(buttons,text='打开项目文件夹',command=lambda:os.startfile(str(ROOT))).pack(side='left',padx=8)
        ttk.Button(buttons,text='Agent交接手册',command=lambda:os.startfile(str(ROOT/'HANDOFF.md'))).pack(side='left')

    def build_qr(self):
        ttk.Label(self.qr_page,text='QQ首次登录或登录失效时，用机器人账号扫码。',font=('Microsoft YaHei UI',13,'bold')).pack(pady=(8,5))
        ttk.Label(self.qr_page,text='主人号和机器人号取统一配置。二维码只显示在本机，不发送到任何服务。',style='Sub.TLabel').pack()
        self.qr_label=ttk.Label(self.qr_page,text='已登录时无需扫码；未登录时请先点「启动QQ」。',anchor='center');self.qr_label.pack(fill='both',expand=True,pady=15)
        row=ttk.Frame(self.qr_page);row.pack()
        ttk.Button(row,text='启动QQ',command=lambda:self.operation(self.backend.start_qq)).pack(side='left',padx=5)
        ttk.Button(row,text='刷新二维码',command=self.refresh_qr).pack(side='left',padx=5)
        ttk.Button(row,text='QQ 接入指南',command=lambda:os.startfile(str(ROOT/'docs/QQ_SETUP.md'))).pack(side='left',padx=5)

    def build_logs(self):
        ttk.Button(self.log_page,text='刷新运行记录',command=self.refresh_logs).pack(anchor='w',pady=(0,10))
        self.log_text=self.text_box(self.log_page)

    @staticmethod
    def replace(widget,text):
        widget.configure(state='normal');widget.delete('1.0','end');widget.insert('end',text);widget.configure(state='disabled')

    def async_job(self,fn,success=None,show_error=True):
        def run():
            try:self.events.put(('ok',success,fn()))
            except Exception as e:self.events.put(('error',show_error,str(e)))
        threading.Thread(target=run,daemon=True).start()

    def operation(self,fn):
        for b in self.action_buttons:b.configure(state='disabled')
        self.notice.set('正在处理…')
        def done(value):
            for b in self.action_buttons:b.configure(state='normal')
            self.notice.set(str(value));self.refresh_qr()
        self.async_job(fn,done)

    def drain(self):
        if self.closed:return
        try:
            while True:
                kind,callback,value=self.events.get_nowait()
                if kind=='ok' and callback:
                    try:callback(value)
                    except Exception as e:self.notice.set('界面更新失败：'+str(e))
                elif kind=='error':
                    for b in self.action_buttons:b.configure(state='normal')
                    if callback:self.notice.set('未完成：'+value)
        except queue.Empty:pass
        self.root.after(100,self.drain)

    def poll(self):
        if self.closed:return
        if not self.polling:
            self.polling=True
            def fetch():
                try:return self.backend.request('status'),self.backend.request('chat')
                except Exception:return None,None
            def update(result):
                self.polling=False;status,rows=result
                if status is None:self.state.set('聊天服务未启动');return
                mode={'paused':'已暂停','reply_only':'只回复','active':'允许主动'}[status['mode']]
                qq='QQ在线' if status['qq_connected'] and status['qq_online'] else 'QQ未连接'
                self.state.set(mode+'  ·  '+qq)
                self.replace(self.status_text,'\n'.join([f'模式：{mode}',f'QQ：{qq}',f'机器人账号：{status.get("qq_bot_id") or "未连接"}',f'主模型：{status["model"]}',f'网关：{status["model_gateway"]}',f'长期记忆：{status["memory_count"]} 条',f'消息队列：{status["queue"]}',f'最近说话：{status["last_spoke"] or "还没有"}',f'成长权重：{status["weights"]}']))
                if rows!=self.last_chat:
                    self.last_chat=rows;self.chat.configure(state='normal');self.chat.delete('1.0','end')
                    if not rows:self.chat.insert('end',self.nickname+'在这里。和她说第一句话吧。\n','body')
                    for r in rows:
                        role='user' if r['role']=='user' else 'assistant'
                        label=self.cfg['owner']['name'] if role=='user' else self.nickname
                        stamp=datetime.fromisoformat(r['ts']).astimezone().strftime('%H:%M')
                        self.chat.insert('end',label+'  '+stamp+'\n',role);self.chat.insert('end',r['content']+'\n','body')
                    self.chat.configure(state='disabled');self.chat.see('end')
                self.refresh_qr()
            self.async_job(fetch,update,False)
        self.root.after(self.cfg['desktop']['poll_interval_ms'],self.poll)

    def send(self):
        text=self.input.get('1.0','end').strip()
        if not text:return 'break'
        def done(result):
            if self.input.get('1.0','end').strip()==text:self.input.delete('1.0','end')
            self.notice.set('当前已暂停，点「只回复」恢复聊天。' if result.get('paused') else '已收到，正在回复…')
        self.async_job(lambda:self.backend.request('chat',{'text':text}),done)
        return 'break'

    def mode(self,value):
        # 安全按钮不随启动/停止操作禁用。
        self.async_job(lambda:self.backend.request('safety',{'mode':value}),lambda r:self.notice.set({'paused':'全部暂停已生效','reply_only':'已恢复，只回复不主动','active':'已允许主动；仍受主动配置和免打扰限制'}[value]))

    def refresh_memory(self):
        def read():return self.backend.request('memory'),self.backend.request('diary')
        def show(result):
            mem,diary=result
            self.replace(self.memories,'\n\n'.join(r['content']+'\n  '+r['category']+' / '+r['importance'] for r in mem) or '暂时没有长期记忆')
            self.replace(self.diaries,'\n\n'.join(r['day']+'  '+r['text'] for r in diary) or '暂时没有日记')
        self.async_job(read,show)

    def add_memory(self):
        text=self.memory_input.get().strip()
        if not text:return
        def done(r):self.memory_input.set('');self.refresh_memory();self.notice.set('已记住')
        self.async_job(lambda:self.backend.request('memory',{'content':text}),done)

    def load_models(self):
        self.async_job(lambda:self.backend.request('models'),lambda rows:self.model_box.configure(values=[r['id'] for r in rows]))

    def save_model(self):
        name=self.model.get().strip()
        if not name:return
        self.async_job(lambda:self.backend.request('config',{'model':{'main':name}}),lambda r:self.notice.set('模型已保存，请重启聊天，再点「只回复」。'))

    def refresh_qr(self):
        path=ROOT/'.runtime/qq-native/qrcode.png'
        if path.is_file() and time.time()-path.stat().st_mtime>self.cfg['desktop']['qr_max_age_seconds']:
            self.qr_image=None
            self.qr_stamp=path.stat().st_mtime
            self.qr_label.configure(image='',text='二维码已过期；自写 QQ 接入仍待验收，请查看接入指南。')
        if path.is_file() and path.stat().st_mtime!=self.qr_stamp:
            try:
                image=tk.PhotoImage(file=str(path))
                factor=max(1,(image.width()+359)//360)
                self.qr_image=image.subsample(factor,factor);self.qr_stamp=path.stat().st_mtime
                self.qr_label.configure(image=self.qr_image,text='')
            except tk.TclError:self.qr_label.configure(text='二维码暂不可读取，请稍后刷新')
        if 'QQ在线' in self.state.get():self.qr_label.configure(image='',text='✓ '+self.nickname+'QQ已在线，无需扫码')
        elif self.qr_image:self.qr_label.configure(image=self.qr_image,text='')

    def refresh_logs(self):self.async_job(self.backend.logs,lambda text:self.replace(self.log_text,text))

    def tab_changed(self,event=None):
        if not hasattr(self,'memory_page'):return
        selected=self.notebook.select()
        if selected==str(self.memory_page):self.refresh_memory()
        elif selected==str(self.log_page):self.refresh_logs()
        elif selected==str(self.qr_page):self.refresh_qr()

    def close(self):
        self.closed=True;self.root.destroy()

def main():
    try:
        lock=InstanceLock(ROOT/'.runtime/desktop.lock')
    except (RuntimeError,OSError):
        # 再次双击桌面图标时，把已有窗口带回前台。
        if os.name=='nt':
            import ctypes
            handle=ctypes.windll.user32.FindWindowW(None,installed_identity().title()+' · 备用界面')
            if handle:
                ctypes.windll.user32.ShowWindow(handle,9)
                ctypes.windll.user32.SetForegroundWindow(handle)
        return
    root=tk.Tk()
    try:
        app=DesktopApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror('QQ ChatBot 启动失败',str(e));root.destroy()
    finally:lock.close()

if __name__=='__main__':main()
