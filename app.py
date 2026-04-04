import os
import sys
import uuid
import time
from flask import Flask, request, jsonify, send_file, render_template_string

# ============================
# استيراد المكتبات
# ============================
try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
    from moviepy.video.fx import Resize
except ImportError:
    print("ERROR: moviepy not installed")
    sys.exit(1)

try:
    from gtts import gTTS
except ImportError:
    print("ERROR: gTTS not installed")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed")
    sys.exit(1)

# ElevenLabs اختياري
try:
    from elevenlabs import generate, set_api_key, Voice, VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    print("Note: elevenlabs not installed (optional)")

# ============================
# دالة مساعدة لتحويل اللون إلى RGB tuple
# ============================
def color_to_rgb(color):
    """تحويل اسم اللون أو رمز Hex إلى tuple (R,G,B)"""
    if color is None:
        return (0, 0, 0)  # أسود افتراضي
    if isinstance(color, tuple):
        return color
    if isinstance(color, str):
        color = color.strip().lower()
        # أسماء الألوان الأساسية
        named_colors = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255),
            'navy': (0, 0, 128),
            'darkgreen': (0, 100, 0),
            'purple': (128, 0, 128),
            'orange': (255, 165, 0),
            'pink': (255, 192, 203),
            'brown': (165, 42, 42),
            'gray': (128, 128, 128),
            'lightblue': (173, 216, 230),
            'lightgreen': (144, 238, 144),
            'gold': (255, 215, 0),
            'silver': (192, 192, 192),
            'beige': (245, 245, 220),
            'coral': (255, 127, 80),
            'lavender': (230, 230, 250),
            'turquoise': (64, 224, 208),
            # ألوان الأنماط المخصصة
            '#FFE066': (255, 224, 102),
            '#FF5733': (255, 87, 51),
            '#1A1A1A': (26, 26, 26),
            '#F5F5DC': (245, 245, 220),
            '#2C3E50': (44, 62, 80),
            '#F1C40F': (241, 196, 15),
        }
        if color in named_colors:
            return named_colors[color]
        # محاولة تحويل رمز Hex مثل #FFFFFF أو FFFFFF
        if color.startswith('#'):
            color = color[1:]
        if len(color) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color):
            return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
        if len(color) == 3 and all(c in '0123456789ABCDEFabcdef' for c in color):
            return (int(color[0]*2, 16), int(color[1]*2, 16), int(color[2]*2, 16))
    # القيمة الافتراضية
    return (0, 0, 0)

# ============================
# إعداد Flask والمجلدات
# ============================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
OUTPUT_DIR = os.path.join(STATIC_DIR, 'output')
AVATARS_DIR = os.path.join(STATIC_DIR, 'avatars')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AVATARS_DIR, exist_ok=True)

# صورة رمزية افتراضية
def create_default_avatar():
    path = os.path.join(AVATARS_DIR, 'default.png')
    if not os.path.exists(path):
        img = Image.new('RGB', (400,400), (73,109,137))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        d.text((100,180), "AI Avatar", fill=(255,255,255), font=font)
        img.save(path)
    return path

DEFAULT_AVATAR = create_default_avatar()

# دوال إنشاء الفيديو
def generate_audio(text, out_path, use_elevenlabs=False, api_key=None):
    if use_elevenlabs and api_key and ELEVENLABS_AVAILABLE:
        try:
            set_api_key(api_key)
            audio = generate(text=text, voice=Voice(voice_id='EXAVITQu4vrTQcpA88OZ',
                          settings=VoiceSettings(stability=0.35, similarity_boost=0.75)))
            with open(out_path, 'wb') as f:
                f.write(audio)
            return out_path
        except:
            pass
    tts = gTTS(text=text, lang='ar')
    tts.save(out_path)
    return out_path

def create_video_simple(text, out_path, duration=5, avatar=None, style='عادي', txt_color=None, bg_color=None):
    w, h = 640, 480
    avatar_path = avatar if (avatar and os.path.exists(avatar)) else DEFAULT_AVATAR
    
    # تحديد الألوان والأحجام حسب النمط (مع تحويل إلى RGB)
    if style == 'كرتوني':
        bg_rgb = color_to_rgb(bg_color or '#FFE066')
        txt_rgb = color_to_rgb(txt_color or '#FF5733')
        font_size = 40
        font_name = "Comic Sans MS"
    elif style == 'سينمائي':
        bg_rgb = color_to_rgb(bg_color or '#1A1A1A')
        txt_rgb = color_to_rgb(txt_color or '#F5F5DC')
        font_size = 36
        font_name = "Georgia"
    elif style == 'أغنية':
        bg_rgb = color_to_rgb(bg_color or '#2C3E50')
        txt_rgb = color_to_rgb(txt_color or '#F1C40F')
        font_size = 38
        font_name = "Arial"
    else:  # عادي
        bg_rgb = color_to_rgb(bg_color or 'black')
        txt_rgb = color_to_rgb(txt_color or 'white')
        font_size = 30
        font_name = "Arial"
    
    # خلفية
    bg_clip = ColorClip(size=(w,h), color=bg_rgb, duration=duration)
    clips = [bg_clip]
    
    # تأثير سينمائي (شريط أسود)
    if style == 'سينمائي':
        bar_height = 60
        top_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', 0))
        bottom_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', h - bar_height))
        clips.extend([top_bar, bottom_bar])
    
    # النص
    txt_clip = TextClip(font=font_name, text=text, font_size=font_size, color=txt_rgb,
                        bg_color=(0,0,0,0.5), size=(w-100, None),
                        method='caption', text_align='center'
                       ).with_position(('center', h-150)).with_duration(duration)
    clips.append(txt_clip)
    
    # الصورة الرمزية
    if avatar_path and style != 'سينمائي':
        try:
            av_clip = VideoClip.from_image(avatar_path, duration=duration).resized(height=150)
            av_clip = av_clip.with_position(('center', 50))
            clips.append(av_clip)
        except:
            pass
    
    final = CompositeVideoClip(clips)
    final.write_videofile(out_path, fps=24, codec='libx264', audio_codec='aac')
    return out_path

def create_video_synced(text, audio_path, out_path, avatar=None, style='عادي', txt_color=None, bg_color=None):
    w, h = 640, 480
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    avatar_path = avatar if (avatar and os.path.exists(avatar)) else DEFAULT_AVATAR
    
    # تحديد الألوان حسب النمط
    if style == 'كرتوني':
        bg_rgb = color_to_rgb(bg_color or '#FFE066')
        txt_rgb = color_to_rgb(txt_color or '#FF5733')
        font_size = 40
        font_name = "Comic Sans MS"
    elif style == 'سينمائي':
        bg_rgb = color_to_rgb(bg_color or '#1A1A1A')
        txt_rgb = color_to_rgb(txt_color or '#F5F5DC')
        font_size = 36
        font_name = "Georgia"
    elif style == 'أغنية':
        bg_rgb = color_to_rgb(bg_color or '#2C3E50')
        txt_rgb = color_to_rgb(txt_color or '#F1C40F')
        font_size = 38
        font_name = "Arial"
    else:
        bg_rgb = color_to_rgb(bg_color or 'black')
        txt_rgb = color_to_rgb(txt_color or 'white')
        font_size = 30
        font_name = "Arial"
    
    bg_clip = ColorClip(size=(w,h), color=bg_rgb, duration=duration)
    clips = [bg_clip]
    
    # تأثير سينمائي
    if style == 'سينمائي':
        bar_height = 60
        top_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', 0))
        bottom_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', h - bar_height))
        clips.extend([top_bar, bottom_bar])
    
    # تقطيع النص
    words = text.split()
    seg = duration / len(words) if words else duration
    txt_clips = []
    for i, word in enumerate(words):
        clip = TextClip(font=font_name, text=word, font_size=font_size, color=txt_rgb,
                        bg_color=(0,0,0,0.5), size=(w-100, None), method='caption'
                       ).with_position(('center', h-150)).with_start(i*seg).with_duration(seg)
        txt_clips.append(clip)
    clips.extend(txt_clips)
    
    # الصورة الرمزية
    if avatar_path and style != 'سينمائي':
        try:
            av_clip = VideoClip.from_image(avatar_path, duration=duration).resized(height=150)
            av_clip = av_clip.with_position(('center', 50))
            clips.append(av_clip)
        except:
            pass
    
    final = CompositeVideoClip(clips).with_audio(audio_clip)
    final.write_videofile(out_path, fps=24, codec='libx264', audio_codec='aac')
    return out_path

# ============================
# واجهة HTML (كما هي مع إضافة خيارات النمط)
# ============================
HTML = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><title>توليد فيديو من النص - أنماط متعددة</title>
<style>
body{font-family:Tahoma;background:linear-gradient(135deg,#667eea,#764ba2);padding:20px;}
.container{max-width:900px;margin:auto;background:#fff;border-radius:20px;overflow:hidden;}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:30px;text-align:center;}
.content{padding:30px;}
.form-group{margin-bottom:20px;}
label{display:block;font-weight:bold;margin-bottom:8px;}
textarea,select,input{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:10px;font-size:16px;}
.row{display:grid;grid-template-columns:1fr 1fr;gap:15px;}
button{width:100%;padding:15px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:10px;font-size:18px;cursor:pointer;}
.loading{display:none;text-align:center;padding:20px;background:#f8f9fa;border-radius:10px;margin-top:20px;}
.spinner{border:4px solid #f3f3f3;border-top:4px solid #667eea;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:auto;}
@keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}
.result{display:none;margin-top:20px;padding:20px;background:#d4edda;border-radius:10px;text-align:center;}
.error{display:none;background:#f8d7da;color:#721c24;border-radius:10px;padding:15px;margin-top:20px;}
.info{background:#e7f3ff;padding:15px;border-radius:10px;margin-top:20px;font-size:14px;color:#004085;}
@media(max-width:600px){.row{grid-template-columns:1fr;}}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>🎬 تحويل النص إلى فيديو</h1><p>اختر النمط الذي تريده: كرتوني، سينمائي، عادي، أو أغنية</p></div>
<div class="content">
<div class="form-group"><label>📝 النص</label><textarea id="text" rows="4" placeholder="اكتب النص هنا..."></textarea></div>
<div class="row">
<div class="form-group"><label>🎨 النمط</label><select id="style">
<option value="عادي">عادي</option>
<option value="كرتوني">كرتوني</option>
<option value="سينمائي">سينمائي</option>
<option value="أغنية">أغنية</option>
</select></div>
<div class="form-group"><label>🖼️ الصورة الرمزية</label><select id="avatar"><option value="default">افتراضي</option><option value="none">إخفاء</option></select></div>
</div>
<div class="row">
<div class="form-group"><label>🎬 نوع التزامن</label><select id="type"><option value="static">نص ثابت</option><option value="synced">متزامن مع الصوت</option></select></div>
<div class="form-group"><label>⏱️ المدة (ثواني) - للنص الثابت</label><input type="number" id="duration" value="5" min="3" max="30"></div>
</div>
<div class="row">
<div class="form-group"><label>🔊 تحويل النص إلى صوت</label><select id="tts"><option value="true">نعم</option><option value="false">لا</option></select></div>
<div class="form-group"><label>🎨 لون الخلفية (اختياري)</label><input type="text" id="bg_color" placeholder="مثل: #FF0000 أو red"></div>
</div>
<div class="row">
<div class="form-group"><label>✏️ لون النص (اختياري)</label><input type="text" id="txt_color" placeholder="مثل: #FFFFFF أو white"></div>
<div></div>
</div>
<div id="eleven" style="display:none;"><div class="form-group"><label>🎙️ مفتاح ElevenLabs (اختياري لجودة صوت أفضل)</label><input type="password" id="key" placeholder="API Key"></div></div>
<button id="generate">🚀 إنشاء الفيديو</button>
<div class="loading" id="loading"><div class="spinner"></div><p>جاري إنشاء الفيديو... قد يستغرق بضع ثوانٍ</p></div>
<div class="result" id="result"></div>
<div class="error" id="error"></div>
<div class="info">💡 نصيحة: للفيديوهات الطويلة أو المعقدة، قد يستغرق المعالجة وقتاً أطول قليلاً.</div>
</div></div>
<script>
const ttsSel=document.getElementById('tts'); const elevenDiv=document.getElementById('eleven');
ttsSel.addEventListener('change',()=>{elevenDiv.style.display=ttsSel.value==='true'?'block':'none';});
document.getElementById('generate').onclick=async()=>{
const text=document.getElementById('text').value.trim();
if(!text){showError('أدخل النص');return;}
const data={
text:text,
style:document.getElementById('style').value,
bg_color:document.getElementById('bg_color').value || null,
text_color:document.getElementById('txt_color').value || null,
avatar:document.getElementById('avatar').value,
video_type:document.getElementById('type').value,
duration:parseFloat(document.getElementById('duration').value),
use_tts:ttsSel.value==='true',
use_elevenlabs:ttsSel.value==='true' && document.getElementById('key').value!=='',
elevenlabs_api_key:document.getElementById('key').value||null
};
showLoading(true);hideResult();hideError();
try{
const res=await fetch('/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const json=await res.json();
if(json.success){showResult(json.video_url);}else{showError(json.error||'خطأ');}
}catch(e){showError('خطأ في الاتصال');}
finally{showLoading(false);}
};
function showLoading(s){document.getElementById('loading').style.display=s?'block':'none';document.getElementById('generate').disabled=s;}
function showResult(url){const div=document.getElementById('result');div.innerHTML=`<p>✅ تم الإنشاء</p><a href="${url}" download>📥 تحميل الفيديو</a><br><br><video width="100%" controls><source src="${url}" type="video/mp4"></video>`;div.style.display='block';}
function hideResult(){document.getElementById('result').style.display='none';}
function showError(msg){const e=document.getElementById('error');e.innerHTML=`❌ ${msg}`;e.style.display='block';}
function hideError(){document.getElementById('error').style.display='none';}
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    if not data or not data.get('text'):
        return jsonify({'error': 'لا يوجد نص'}), 400

    text = data['text']
    style = data.get('style', 'عادي')
    use_tts = data.get('use_tts', True)
    use_eleven = data.get('use_elevenlabs', False)
    key = data.get('elevenlabs_api_key')
    avatar = None if data.get('avatar') == 'none' else DEFAULT_AVATAR
    bg_color = data.get('bg_color')
    txt_color = data.get('text_color')
    vid_type = data.get('video_type', 'static')
    duration = float(data.get('duration', 5))

    vid_id = str(uuid.uuid4())
    audio_path = os.path.join(OUTPUT_DIR, f'audio_{vid_id}.mp3')
    video_path = os.path.join(OUTPUT_DIR, f'video_{vid_id}.mp4')

    try:
        if use_tts:
            generate_audio(text, audio_path, use_eleven, key)
            if vid_type == 'synced':
                create_video_synced(text, audio_path, video_path, avatar, style, txt_color, bg_color)
            else:
                create_video_simple(text, video_path, duration, avatar, style, txt_color, bg_color)
                # إضافة الصوت للفيديو الثابت
                vid = VideoClip.from_file(video_path)
                aud = AudioFileClip(audio_path).with_duration(vid.duration)
                final = vid.with_audio(aud)
                final.write_videofile(video_path, codec='libx264', audio_codec='aac')
        else:
            create_video_simple(text, video_path, duration, avatar, style, txt_color, bg_color)

        url = url_for('download', filename=os.path.basename(video_path), _external=True)
        return jsonify({'success': True, 'video_url': url})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({'error': 'ملف غير موجود'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
