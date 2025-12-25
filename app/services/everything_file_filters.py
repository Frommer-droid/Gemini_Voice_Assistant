FILE_TYPE_FILTERS = {
    "музыка": {
        "keywords": ["музыка", "музык", "песня", "песни", "audio", "music"],
        "ext": "aac;ac3;aif;aifc;aiff;au;cda;dts;fla;flac;it;m1a;m2a;m3u;m4a;mid;midi;mka;mod;mp2;mp3;mpa;ogg;ra;rmi;spc;snd;umx;voc;wav;wma;xm",
    },
    "архивы": {
        "keywords": ["архив", "архивы", "архивн", "zip", "rar", "7z"],
        "ext": "7z;ace;arj;bz2;cab;gz;gzip;jar;r00;r01;r02;r03;r04;r05;r06;r07;r08;r09;r10;r11;r12;r13;r14;r15;r16;r17;r18;r19;r20;r21;r22;r23;r24;r25;r26;r27;r28;r29;rar;tar;tgz;z;zip",
    },
    "документы": {
        "keywords": ["документ", "документы", "докум", "дока", "docs", "documents", "text", "текст"],
        "ext": "py;c;chm;cpp;csv;cxx;doc;docm;docx;dot;dotm;dotx;h;hpp;htm;html;hxx;ini;java;js;lua;mht;mhtml;odt;pdf;potx;potm;ppam;ppsm;ppsx;pps;ppt;pptm;pptx;rtf;sldm;sldx;thmx;txt;vsd;wpd;wps;wri;xlam;xls;xlsb;xlsm;xlsx;xltm;xltx;xml;ahk;srt;djvu;epub;mobi;md;tex;json;yml;yaml;fb2",
    },
    "программы": {
        "keywords": ["программа", "программы", "программ", "exe", "установщик", "setup", "installer", "приложение"],
        "ext": "bat;cmd;exe;msi;scr;pyw",
    },
    "фото": {
        "keywords": ["фото", "фотограф", "изображени", "картин", "photo", "image", "pictures"],
        "ext": "ani;bmp;gif;ico;jpe;jpeg;jpg;pcx;png;psd;tga;tif;tiff;wmf",
    },
    "видео": {
        "keywords": ["видео", "video", "movie", "фильм", "фильмы", "клипы"],
        "ext": "3g2;3gp;3gp2;3gpp;amr;amv;asf;avi;bdmv;bik;d2v;divx;drc;dsa;dsm;dss;dsv;evo;f4v;flc;fli;flic;flv;hdmov;ifo;ivf;m1v;m2p;m2t;m2ts;m2v;m4b;m4p;m4v;mkv;mp2v;mp4;mp4v;mpe;mpeg;mpg;mpls;mpv2;mpv4;mov;mts;ogm;ogv;pss;pva;qt;ram;ratdvd;rm;rmm;rmvb;roq;rpm;smil;smk;swf;tp;tpr;ts;vob;vp6;webm;wm;wmp;wmv",
    },
}


def detect_file_filter(name: str):
    norm = (name or "").strip().lower()
    best = None
    for key, data in FILE_TYPE_FILTERS.items():
        for kw in data["keywords"]:
            if kw in norm:
                best = data["ext"]
                break
        if best:
            break
    return best
