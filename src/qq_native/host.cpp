#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <string>
#include <vector>
#include <filesystem>
#include <cstdint>
// QQNT 9.9.33-52230 exports Chromium libc++ ABI, not MSVC STL.
// Only borrowed, long-form strings/empty containers cross the boundary.
// Exact runtime hashes are checked by core/native_host.py before launch.
// No C++ objects are freed across CRTs; process exit releases the embedded runtime.
struct Vec {void* first; void* last; void* end;};
struct Str {uint64_t capacity; uint64_t size;const char* data;};
struct Settings {uint64_t flags=3;int policy=0;void* callbacks[8]={};};
HMODULE lib;
void* crashpad_adapter(void*,void* exports){return exports;}
template<class T> T symbol(const char* n) {auto p=GetProcAddress(lib,n); if(!p){fputs("QQ_CHATBOT_HOST_UNSUPPORTED_EXPORT\n",stderr);ExitProcess(4);}return reinterpret_cast<T>(p);}
int wmain(int argc,wchar_t** argv) {
 if(argc!=3)return 2;
 // argv[1] is the private, verified official runtime; argv[2] is this project root.
 const std::filesystem::path root = std::filesystem::absolute(argv[2]);
 const auto scriptPath = root / L"src" / L"qq_native" / L"entry.js";
 const auto configPath = root / L".runtime" / L"qq-native" / L"host-config.json";
 if(!std::filesystem::is_regular_file(scriptPath) || !std::filesystem::is_regular_file(configPath)) return 2;
 SetEnvironmentVariableW(L"QQ_CHATBOT_NATIVE_CONFIG",configPath.c_str());
 SetEnvironmentVariableW(L"NODE_OPTIONS",nullptr);
 SetEnvironmentVariableW(L"NODE_PATH",nullptr);
 const auto mutexName=L"Local\\QQChatBot.Native."+std::to_wstring(std::hash<std::wstring>{}(root.wstring()));
 auto mutex=CreateMutexW(nullptr,FALSE,mutexName.c_str());
 if(!mutex || GetLastError()==ERROR_ALREADY_EXISTS)return 6;
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 std::wstring dir(argv[1]); SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS|LOAD_LIBRARY_SEARCH_USER_DIRS);AddDllDirectory(dir.c_str());AddDllDirectory((dir+L"\\resources\\app").c_str());SetCurrentDirectoryW(dir.c_str());
 lib=LoadLibraryExW((dir+L"\\QQNT.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS|LOAD_LIBRARY_SEARCH_USER_DIRS);if(!lib)return 3;
 std::string program="qq-chatbot-native-host";
 Str s{65,program.size(),program.c_str()};Vec args{&s,&s+1,&s+1},empty{};void* init[2]={};
 symbol<void*(*)(void*,void*,unsigned)>("?InitializeOncePerProcess@node@@YA?AV?$shared_ptr@VInitializationResult@node@@@__Cr@std@@AEBV?$vector@V?$basic_string@DU?$char_traits@D@__Cr@std@@V?$allocator@D@23@@__Cr@std@@V?$allocator@V?$basic_string@DU?$char_traits@D@__Cr@std@@V?$allocator@D@23@@__Cr@std@@@23@@34@W4Flags@ProcessInitializationFlags@1@@Z")(init,&args,2|8|16|32|64|128|512);

 void* platform=symbol<void*(*)(int,void*)>("?CreatePlatform@node@@YAPEAVMultiIsolatePlatform@1@HPEAVTracingController@v8@@@Z")(4,nullptr);
 symbol<void(*)(void*)>("?InitializePlatform@V8@v8@@SAXPEAVPlatform@2@@Z")(platform);
 symbol<bool(*)(const char*,const char*)>("?InitializeICUDefaultLocation@V8@v8@@SA_NPEBD0@Z")("QQNT.dll","icudtl.dat");
 symbol<void(*)(const char*)>("?InitializeExternalStartupDataFromFile@V8@v8@@SAXPEBD@Z")("snapshot_blob.bin");
 symbol<bool(*)()>("?Initialize@V8@v8@@SA_NXZ")();
 auto loop=symbol<void*(*)()>("uv_default_loop")();
 auto allocator=symbol<void*(*)()>("?CreateArrayBufferAllocator@node@@YAPEAVArrayBufferAllocator@1@XZ")();
 Settings settings;void* heap=nullptr;
 auto isolate=symbol<void*(*)(void*,void*,void*,void*,void*,void*)>("?NewIsolate@node@@YAPEAVIsolate@v8@@PEAVArrayBufferAllocator@1@PEAUuv_loop_s@@PEAVMultiIsolatePlatform@1@PEBVEmbedderSnapshotData@1@AEBUIsolateSettings@1@V?$unique_ptr@VCppHeap@v8@@U?$default_delete@VCppHeap@v8@@@__Cr@std@@@__Cr@std@@@Z")(allocator,loop,platform,nullptr,&settings,&heap);

 if(!isolate)return 4;
 alignas(16) char locker[128]={},handles[128]={};
 symbol<void(*)(void*,void*)>("??0Locker@v8@@QEAA@PEAVIsolate@1@@Z")(locker,isolate);
 symbol<void(*)(void*)>("?Enter@Isolate@v8@@QEAAXXZ")(isolate);
 symbol<void(*)(void*,void*)>("??0HandleScope@v8@@QEAA@PEAVIsolate@1@@Z")(handles,isolate);
 void* context=nullptr;
 symbol<void*(*)(void*,void*,void*)>("?NewContext@node@@YA?AV?$Local@VContext@v8@@@v8@@PEAVIsolate@3@V?$Local@VObjectTemplate@v8@@@3@@Z")(&context,isolate,nullptr);

 if(!context)return 4;
 symbol<void(*)(void*)>("?Enter@Context@v8@@QEAAXXZ")(context);
 auto data=symbol<void*(*)(void*,void*,void*,void*,void*)>("?CreateIsolateData@node@@YAPEAVIsolateData@1@PEAVIsolate@v8@@PEAUuv_loop_s@@PEAVMultiIsolatePlatform@1@PEAVArrayBufferAllocator@1@PEBVEmbedderSnapshotData@1@@Z")(isolate,loop,platform,allocator,nullptr);
 void* inspector=nullptr;
 auto env=symbol<void*(*)(void*,void*,void*,void*,uint64_t,uint64_t,void*)>("?CreateEnvironment@node@@YAPEAVEnvironment@1@PEAVIsolateData@1@V?$Local@VContext@v8@@@v8@@AEBV?$vector@V?$basic_string@DU?$char_traits@D@__Cr@std@@V?$allocator@D@23@@__Cr@std@@V?$allocator@V?$basic_string@DU?$char_traits@D@__Cr@std@@V?$allocator@D@23@@__Cr@std@@@23@@__Cr@std@@2W4Flags@EnvironmentFlags@1@UThreadId@1@V?$unique_ptr@UInspectorParentHandle@node@@U?$default_delete@UInspectorParentHandle@node@@@__Cr@std@@@78@@Z")(data,context,&args,&empty,1|32|128|512|1024,UINT64_MAX,&inspector);

 if(!env)return 4;
 // Electron Windows crashpad binding has no exports; the Windows host supplies it.
  symbol<void(*)(void*,const char*,void*(*)(void*,void*),int)>("?AddLinkedBinding@node@@YAXPEAVEnvironment@1@PEBDP6APEAUnapi_value__@@PEAUnapi_env__@@PEAU3@@ZH@Z")(env,"electron_common_crashpad_support",crashpad_adapter,8);
 int count=WideCharToMultiByte(CP_UTF8,0,scriptPath.c_str(),-1,nullptr,0,nullptr,nullptr);std::string script(count,'\0');WideCharToMultiByte(CP_UTF8,0,scriptPath.c_str(),-1,script.data(),count,nullptr,nullptr);script.resize(count-1);
 std::string source="require('module').createRequire(process.cwd()+'/entry.js')('";
 for(char c:script){if(c=='\\'||c=='\'')source+='\\';source+=c;}source+="').start(process.env.QQ_CHATBOT_NATIVE_CONFIG).catch(() => { process.stderr.write('QQ_CHATBOT_NATIVE_START_FAILED\\n'); process.exit(5); });";
 struct View{const char* p;size_t n;}view{source.data(),source.size()};alignas(16) char callback[128]={};void* output=nullptr;
 symbol<void*(*)(void*,void*,void*,void*)>("?LoadEnvironment@node@@YA?AV?$MaybeLocal@VValue@v8@@@v8@@PEAVEnvironment@1@V?$basic_string_view@DU?$char_traits@D@__Cr@std@@@__Cr@std@@V?$function@$$A6AXPEAVEnvironment@node@@V?$Local@VValue@v8@@@v8@@1@Z@67@@Z")(&output,env,&view,callback);

  symbol<void*(*)(void*,void*)>("?SpinEventLoop@node@@YA?AV?$Maybe@H@v8@@PEAVEnvironment@1@@Z")(&output,env);
 ExitProcess(0);
}
