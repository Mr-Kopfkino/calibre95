using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using System.Reflection;

[assembly: AssemblyTitle("calibre95")]
[assembly: AssemblyProduct("calibre95")]
[assembly: AssemblyDescription("Windows 95 style ebook library and reader")]
[assembly: AssemblyVersion("1.0.1.0")]
[assembly: AssemblyFileVersion("1.0.1.0")]

// Build using the .NET Framework compiler shipped with supported Windows versions.
internal static class Launcher
{
    private static readonly object LogLock = new object();
    private static string language = "zh_CN";

    private static string L(string chinese, string english, string japanese)
    {
        return language == "en" ? english : language == "ja" ? japanese : chinese;
    }

    [STAThread]
    private static int Main()
    {
        Application.EnableVisualStyles();
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string engine = Path.Combine(root, "runtime", "calibre-debug.exe");
        string entry = Path.Combine(root, "app", "main.py");
        string data = Path.Combine(root, "Data");
        try
        {
            Match saved = Regex.Match(File.ReadAllText(Path.Combine(data, "settings.json"), Encoding.UTF8),
                "\"language\"\\s*:\\s*\"(en|ja)\"");
            if (saved.Success) language = saved.Groups[1].Value;
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        string logPath = Path.Combine(data, "logs", "startup.log");
        string mutexName;
        using (SHA256 hash = SHA256.Create())
        {
            mutexName = "Local\\RetroReader_" + BitConverter.ToString(
                hash.ComputeHash(Encoding.UTF8.GetBytes(root.ToUpperInvariant()))).Replace("-", "");
        }
        using (Mutex singleInstance = new Mutex(false, mutexName))
        {
            bool locked = false;
            try
            {
                try { locked = singleInstance.WaitOne(0, false); }
                catch (AbandonedMutexException) { locked = true; }
                if (!locked)
                {
                    MessageBox.Show(L("calibre95已经在运行。请切换到已打开的窗口。", "calibre95 is already running. Switch to its open window.", "calibre95は既に起動しています。開いているウィンドウに切り替えてください。"), L("calibre95", "calibre95", "calibre95"), MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return 0;
                }
                if (!File.Exists(engine) || !File.Exists(entry))
                {
                    MessageBox.Show(L("程序文件不完整。请保留整个软件文件夹，然后双击本程序。\n\n缺少：", "Application files are incomplete. Keep the whole application folder together.\n\nMissing: ", "プログラムファイルが不足しています。アプリケーションのフォルダー全体を保存してください。\n\n見つからないファイル：") +
                        (!File.Exists(engine) ? engine : entry), L("calibre95 · 无法启动", "calibre95 · Cannot start", "calibre95 · 起動できません"), MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return 1;
                }
                Directory.CreateDirectory(Path.Combine(data, "config"));
                Directory.CreateDirectory(Path.Combine(data, "temp"));
                Directory.CreateDirectory(Path.GetDirectoryName(logPath));
                // Keep the previous run for diagnosis without growing logs indefinitely.
                if (File.Exists(logPath)) File.Copy(logPath, logPath + ".previous", true);
                using (StreamWriter log = new StreamWriter(logPath, false, new UTF8Encoding(false)))
                {
                    log.AutoFlush = true;
                    log.WriteLine("calibre95 start: " + DateTimeOffset.Now.ToString("o"));
                    ProcessStartInfo start = new ProcessStartInfo(engine, Quote(entry));
                    start.WorkingDirectory = root;
                    start.UseShellExecute = false;
                    start.CreateNoWindow = true;
                    start.WindowStyle = ProcessWindowStyle.Hidden;
                    start.RedirectStandardOutput = true;
                    start.RedirectStandardError = true;
                    start.StandardOutputEncoding = Encoding.UTF8;
                    start.StandardErrorEncoding = Encoding.UTF8;
                    start.EnvironmentVariables["CALIBRE_CONFIG_DIRECTORY"] = Path.Combine(data, "config");
                    start.EnvironmentVariables["CALIBRE_DEVELOP_FROM"] = Path.Combine(root, "source", "calibre-src");
                    start.EnvironmentVariables["CALIBRE_NO_DEFAULT_PROGRAMS"] = "1";
                    start.EnvironmentVariables["RETROREADER_DATA_DIR"] = data;
                    start.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
                    start.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                    start.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
                    start.EnvironmentVariables["TEMP"] = Path.Combine(data, "temp");
                    start.EnvironmentVariables["TMP"] = Path.Combine(data, "temp");
                    start.EnvironmentVariables["CALIBRE_TEMP_DIR"] = Path.Combine(data, "temp");
                    start.EnvironmentVariables["QT_PLUGIN_PATH"] = Path.Combine(root, "runtime", "app", "plugins");
                    using (Process process = new Process())
                    {
                        process.StartInfo = start;
                        process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
                        {
                            if (e.Data != null) lock (LogLock) { log.WriteLine(e.Data); }
                        };
                        process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
                        {
                            if (e.Data != null) lock (LogLock) { log.WriteLine(e.Data); }
                        };
                        process.Start();
                        process.BeginOutputReadLine();
                        process.BeginErrorReadLine();
                        process.WaitForExit();
                        int code = process.ExitCode;
                        log.WriteLine("Exit code: " + code);
                        if (code != 0)
                        {
                            MessageBox.Show(L("程序意外退出。你的书库保存在 Data 文件夹中。\n\n诊断日志：\n", "The application exited unexpectedly. Your library is in the Data folder.\n\nDiagnostic log:\n", "アプリが予期せず終了しました。書庫は Data フォルダーにあります。\n\n診断ログ：\n") + logPath,
                                L("calibre95 · 运行提示", "calibre95 · Application notice", "calibre95 · 実行のお知らせ"), MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                        return code;
                    }
                }
            }
            catch (Exception error)
            {
                MessageBox.Show(L("无法启动calibre95。请确认所在文件夹可写，且程序文件完整。\n\n", "Cannot start calibre95. Check that its folder is writable and application files are complete.\n\n", "calibre95を起動できません。フォルダーに書き込めること、ファイルがそろっていることを確認してください。\n\n") + error.Message,
                    L("calibre95 · 无法启动", "calibre95 · Cannot start", "calibre95 · 起動できません"), MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
            finally
            {
                if (locked) singleInstance.ReleaseMutex();
            }
        }
    }

    // Windows command-line quoting, including trailing backslashes.
    private static string Quote(string value)
    {
        StringBuilder result = new StringBuilder("\"");
        int backslashes = 0;
        foreach (char ch in value)
        {
            if (ch == '\\') { backslashes++; continue; }
            if (ch == '"')
            {
                result.Append('\\', backslashes * 2 + 1);
                result.Append('"');
            }
            else
            {
                result.Append('\\', backslashes);
                result.Append(ch);
            }
            backslashes = 0;
        }
        result.Append('\\', backslashes * 2);
        result.Append('"');
        return result.ToString();
    }
}
