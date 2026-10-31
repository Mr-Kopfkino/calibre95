// calibre95: bounded, on-demand PCM sampling of the music file being played.
// GPL-3.0-or-later. FFmpeg public API, pinned to the bundled FFmpeg 6.1 ABI.
// No system audio capture, no second audio output, no whole-track pre-scan.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <atomic>
extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/channel_layout.h>
#include <libavutil/samplefmt.h>
#include <libavutil/opt.h>
#include <libswresample/swresample.h>
}

#define DECLARE(fn) static decltype(&fn) p_##fn = nullptr
DECLARE(avformat_alloc_context); DECLARE(avformat_open_input);
DECLARE(avformat_find_stream_info); DECLARE(av_find_best_stream);
DECLARE(avformat_close_input); DECLARE(avformat_seek_file); DECLARE(av_read_frame);
DECLARE(avcodec_alloc_context3); DECLARE(avcodec_parameters_to_context);
DECLARE(avcodec_open2); DECLARE(avcodec_free_context); DECLARE(avcodec_flush_buffers);
DECLARE(avcodec_send_packet); DECLARE(avcodec_receive_frame);
DECLARE(av_packet_alloc); DECLARE(av_packet_free); DECLARE(av_packet_unref);
DECLARE(av_frame_alloc); DECLARE(av_frame_free); DECLARE(av_frame_unref);
DECLARE(av_rescale_q); DECLARE(av_strerror); DECLARE(avcodec_version);
DECLARE(swr_alloc_set_opts2); DECLARE(swr_init); DECLARE(swr_free); DECLARE(swr_convert);
DECLARE(av_channel_layout_default); DECLARE(av_channel_layout_uninit);

static thread_local char last_error[256];
static bool loaded = false;
static HMODULE handles[4] = {};
static void error_text(int err) {
    if (p_av_strerror) p_av_strerror(err, last_error, sizeof(last_error));
}
#define LOAD(module, fn) do { p_##fn = reinterpret_cast<decltype(p_##fn)>(GetProcAddress(module, #fn)); if(!p_##fn) return false; } while(0)
static bool load_api(const wchar_t* directory) {
    if (loaded) return true;
    const wchar_t* names[] = {L"avutil-58.dll", L"avcodec-60.dll", L"avformat-60.dll", L"swresample-4.dll"};
    for (int i=0;i<4;i++) {
        wchar_t path[32768];
        if (swprintf_s(path, L"%s\\%s", directory, names[i]) < 0) return false;
        handles[i] = LoadLibraryExW(path, nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        if (!handles[i]) { strcpy_s(last_error, "Cannot load bundled FFmpeg DLL"); return false; }
    }
    HMODULE u=handles[0], c=handles[1], f=handles[2], s=handles[3];
    LOAD(f,avformat_alloc_context); LOAD(f,avformat_open_input); LOAD(f,avformat_find_stream_info);
    LOAD(f,av_find_best_stream); LOAD(f,avformat_close_input); LOAD(f,avformat_seek_file); LOAD(f,av_read_frame);
    LOAD(c,avcodec_alloc_context3); LOAD(c,avcodec_parameters_to_context); LOAD(c,avcodec_open2);
    LOAD(c,avcodec_free_context); LOAD(c,avcodec_flush_buffers); LOAD(c,avcodec_send_packet);
    LOAD(c,avcodec_receive_frame); LOAD(c,av_packet_alloc); LOAD(c,av_packet_free); LOAD(c,av_packet_unref); LOAD(c,avcodec_version);
    LOAD(u,av_frame_alloc); LOAD(u,av_frame_free); LOAD(u,av_frame_unref); LOAD(u,av_rescale_q); LOAD(u,av_strerror);
    LOAD(u,av_channel_layout_default); LOAD(u,av_channel_layout_uninit);
    LOAD(s,swr_alloc_set_opts2); LOAD(s,swr_init); LOAD(s,swr_free); LOAD(s,swr_convert);
    if ((p_avcodec_version() >> 16) != 60) { strcpy_s(last_error,"Unexpected FFmpeg ABI"); return false; }
    loaded = true;
    return true;
}

static constexpr int RATE=22050, CAPACITY=16384;
struct Reader {
    AVFormatContext* format=nullptr;
    AVCodecContext* codec=nullptr;
    AVPacket* packet=nullptr;
    AVFrame* frame=nullptr;
    SwrContext* resample=nullptr;
    int stream=-1, count=0;
    int64_t first=0, next=0;
    bool eof=false, drain_sent=false, have_time=false;
    unsigned long long deadline=0;
    std::atomic<bool> cancel{false};
    float samples[CAPACITY];
    // A bounded conversion buffer; unusually large frames are truncated safely.
    float converted[65536];
    uint64_t decoded_frames=0, seeks=0;
};
static int interrupted(void* value) {
    Reader* r=static_cast<Reader*>(value);
    return r->cancel.load() || (r->deadline && GetTickCount64()>r->deadline);
}
static void dispose(Reader* r) {
    if(!r) return;
    p_swr_free(&r->resample);
    p_av_frame_free(&r->frame);
    p_av_packet_free(&r->packet);
    p_avcodec_free_context(&r->codec);
    p_avformat_close_input(&r->format);
    delete r;
}
static int resampler(Reader* r) {
    p_swr_free(&r->resample);
    AVChannelLayout mono=AV_CHANNEL_LAYOUT_MONO;
    if (!r->codec->ch_layout.nb_channels) p_av_channel_layout_default(&r->codec->ch_layout, 2);
    int error=p_swr_alloc_set_opts2(&r->resample,&mono,AV_SAMPLE_FMT_FLT,RATE,
        &r->codec->ch_layout,r->codec->sample_fmt,r->codec->sample_rate,0,nullptr);
    return error<0 ? error : p_swr_init(r->resample);
}
extern "C" __declspec(dllexport) void* c95_pcm_open(const wchar_t* directory,const wchar_t* filename) {
    last_error[0]=0;
    if(!load_api(directory)) return nullptr;
    Reader* r=new Reader();
    r->deadline=GetTickCount64()+1500;
    r->format=p_avformat_alloc_context();
    if(!r->format) { dispose(r); return nullptr; }
    r->format->interrupt_callback={interrupted,r};
    // Probe enough for local audio tags, but do not scan the file end-to-end.
    r->format->probesize=512*1024;
    r->format->max_analyze_duration=AV_TIME_BASE;
    char path[131072];
    if(!WideCharToMultiByte(CP_UTF8,0,filename,-1,path,sizeof(path),nullptr,nullptr)) { dispose(r); return nullptr; }
    int e=p_avformat_open_input(&r->format,path,nullptr,nullptr);
    if(e>=0) {
        for(unsigned int i=0;i<r->format->nb_streams;i++) {
            // Embedded album covers/video are unrelated to this tiny spectrum.
            if(r->format->streams[i]->codecpar->codec_type!=AVMEDIA_TYPE_AUDIO)
                r->format->streams[i]->discard=AVDISCARD_ALL;
        }
    }
    if(e>=0) e=p_avformat_find_stream_info(r->format,nullptr);
    const AVCodec* decoder=nullptr;
    if(e>=0) e=r->stream=p_av_find_best_stream(r->format,AVMEDIA_TYPE_AUDIO,-1,-1,&decoder,0);
    if(e>=0) {
        r->codec=p_avcodec_alloc_context3(decoder);
        e=r->codec ? p_avcodec_parameters_to_context(r->codec,r->format->streams[r->stream]->codecpar) : AVERROR(ENOMEM);
    }
    if(e>=0) { r->codec->thread_count=1; e=p_avcodec_open2(r->codec,decoder,nullptr); }
    if(e>=0 && (r->codec->sample_rate<8000 || r->codec->sample_rate>384000 || r->codec->ch_layout.nb_channels>16)) e=AVERROR(EINVAL);
    if(e>=0) e=resampler(r);
    if(e>=0) { r->packet=p_av_packet_alloc(); r->frame=p_av_frame_alloc(); if(!r->packet||!r->frame) e=AVERROR(ENOMEM); }
    if(e<0) { error_text(e); dispose(r); return nullptr; }
    r->deadline=0;
    return r;
}

static int seek_to(Reader* r,int64_t sample) {
    AVStream* st=r->format->streams[r->stream];
    int64_t origin=st->start_time==AV_NOPTS_VALUE ? 0 : st->start_time;
    int64_t timestamp=p_av_rescale_q(sample,AVRational{1,RATE},st->time_base)+origin;
    int e=p_avformat_seek_file(r->format,r->stream,INT64_MIN,timestamp,timestamp,AVSEEK_FLAG_BACKWARD);
    if(e<0) return e;
    p_avcodec_flush_buffers(r->codec); p_av_packet_unref(r->packet);
    e=resampler(r); if(e<0) return e;
    r->count=0; r->first=r->next=sample; r->have_time=false;
    r->eof=r->drain_sent=false; ++r->seeks;
    return 0;
}
static void append(Reader* r,const float* data,int count,int64_t at) {
    if(!r->have_time || llabs(at-r->next)>RATE/5) { r->count=0; r->first=at; r->next=at; r->have_time=true; }
    if(count>=CAPACITY) { data+=count-CAPACITY; at+=count-CAPACITY; count=CAPACITY; r->count=0; r->first=at; }
    int remove=(r->count+count>CAPACITY)?r->count+count-CAPACITY:0;
    if(remove) { memmove(r->samples,r->samples+remove,(r->count-remove)*sizeof(float)); r->count-=remove; r->first+=remove; }
    if(!r->count) r->first=at;
    memcpy(r->samples+r->count,data,count*sizeof(float)); r->count+=count; r->next=r->first+r->count;
}
static int consume_frame(Reader* r) {
    AVStream* st=r->format->streams[r->stream];
    int64_t pts=r->frame->best_effort_timestamp;
    int64_t origin=st->start_time==AV_NOPTS_VALUE ? 0 : st->start_time;
    int64_t at=pts==AV_NOPTS_VALUE ? r->next : p_av_rescale_q(pts-origin,st->time_base,AVRational{1,RATE});
    uint8_t* destination=reinterpret_cast<uint8_t*>(r->converted);
    int count=p_swr_convert(r->resample,&destination,65536,(const uint8_t**)r->frame->extended_data,r->frame->nb_samples);
    if(count>0) append(r,r->converted,count,at);
    p_av_frame_unref(r->frame); ++r->decoded_frames;
    return count;
}
extern "C" __declspec(dllexport) int c95_pcm_read(void* value,int64_t position_ms,float* output,int count) {
    Reader* r=static_cast<Reader*>(value);
    if(!r||!output||count<1||count>4096) return AVERROR(EINVAL);
    memset(output,0,count*sizeof(float));
    r->cancel.store(false); r->deadline=GetTickCount64()+180;
    int64_t start=(position_ms<0?0:position_ms)*RATE/1000, end=start+count;
    if((r->have_time && (start<r->first || start>r->next+RATE/4)) || (!r->have_time && start>RATE/4)) {
        int e=seek_to(r,start>RATE/10?start-RATE/10:0);
        if(e<0) { r->deadline=0; error_text(e); return e; }
    }
    int guard=0, e=0;
    while(r->next<end && !interrupted(r) && ++guard<160) {
        e=p_avcodec_receive_frame(r->codec,r->frame);
        if(e>=0) { e=consume_frame(r); if(e<0) break; continue; }
        if(e==AVERROR_EOF) { r->eof=true; break; }
        if(e!=AVERROR(EAGAIN)) break;
        if(r->drain_sent) break;
        e=p_av_read_frame(r->format,r->packet);
        if(e<0) { p_avcodec_send_packet(r->codec,nullptr); r->drain_sent=true; continue; }
        if(r->packet->stream_index==r->stream) e=p_avcodec_send_packet(r->codec,r->packet);
        else e=0;
        p_av_packet_unref(r->packet);
        if(e<0 && e!=AVERROR(EAGAIN)) break;
    }
    int copied=0;
    if(r->have_time) {
        int64_t begin=start>r->first?start:r->first;
        int64_t finish=end<r->next?end:r->next;
        if(finish>begin) { copied=(int)(finish-begin); memcpy(output+(begin-start),r->samples+(begin-r->first),copied*sizeof(float)); }
    }
    r->deadline=0;
    return copied;
}
extern "C" __declspec(dllexport) void c95_pcm_cancel(void* value) { if(value) static_cast<Reader*>(value)->cancel.store(true); }
extern "C" __declspec(dllexport) void c95_pcm_close(void* value) { dispose(static_cast<Reader*>(value)); }
extern "C" __declspec(dllexport) const char* c95_pcm_error() { return last_error; }
extern "C" __declspec(dllexport) uint64_t c95_pcm_frames(void* value) { return value?static_cast<Reader*>(value)->decoded_frames:0; }
extern "C" __declspec(dllexport) uint64_t c95_pcm_seeks(void* value) { return value?static_cast<Reader*>(value)->seeks:0; }
