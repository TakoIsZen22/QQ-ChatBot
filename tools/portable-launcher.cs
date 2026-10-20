using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Reflection;
[assembly: AssemblyTitle("QQ ChatBot")]
[assembly: AssemblyProduct("QQ ChatBot")]
class Launcher {
    [STAThread] static void Main(string[] args) {
        string root=AppDomain.CurrentDomain.BaseDirectory;
        try {
            // Only our fixed desktop entry and its documented switches are executable.
            foreach(string arg in args) if(arg!="--startup" && arg!="--register" && arg!="--unregister" && arg!="--inspect-appearance")
                throw new Exception("不支持的启动参数。");
            string runtime=Path.Combine(root,"_runtime","pythonw.exe");
            if(!File.Exists(runtime)) throw new Exception("请先完整解压 Windows 发布包，不能只复制 EXE。");
            Directory.CreateDirectory(Path.Combine(root,".runtime"));
            File.WriteAllText(Path.Combine(root,".runtime","write-check.tmp"),"");
            File.Delete(Path.Combine(root,".runtime","write-check.tmp"));
            ProcessStartInfo start=new ProcessStartInfo(runtime,"-m src.desktop "+string.Join(" ",args));
            start.WorkingDirectory=root;start.UseShellExecute=false;start.CreateNoWindow=true;
            start.EnvironmentVariables["PYTHONUTF8"]="1";
            Process.Start(start);
        } catch(Exception e) { MessageBox.Show("QQ ChatBot 无法启动："+e.Message+"\n请解压到你有写入权限的短路径目录。","QQ ChatBot",MessageBoxButtons.OK,MessageBoxIcon.Error); }
    }
}
