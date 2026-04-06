import os
import sys
import uuid
import time
from flask import Flask, request, jsonify, send_file, render_template_string

# ============================================
# 1. استيراد المكتبات مع التحقق
# ============================================
try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("ERROR: moviepy not installed")
    sys.exit(1)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("ERROR: gTTS not installed")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("ERROR: Pillow not installed")
    sys.exit(1)

# ============================================
# 2. إعداد Flask
# ============================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
OUTPUT_DIR = os.path.join(STATIC_DIR, 'output')
AVATARS_DIR = os.path.join(STATIC_DIR, 'avatars')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AVATARS_DIR, exist_ok=True)

# ============================================
# 3. دوال مساعدة
# ============================================
def color_to_rgb(color):
    if color is None:
        return (0,0,0)
    if isinstance(color, tuple):
        return color
    if isinstance(color, str):
        c = color.strip().lower()
        named = {
            'اسود':(0,0,0), 'ابيض':(255,255,255), 'احمر':(255,0,0),
            'اخضر':(0,255,0), 'ازرق':(0,0,255), 'اصفر':(255,255,0),
            'برتقالي':(255,165,0), 'وردي':(255,192,203), 'بني':(165,42,42),
            'رمادي':(128,128,128), 'ذهبي':(255,215,0), 'فضي':(192,192,192),
            'بنفسجي':(128,0,128), 'فيروزي':(64,224,208),
            'black':(0,0,0), 'white':(255,255,255), 'red':(255,0,0)
        }
        if c in named:
            return named[c]
        if c.startswith('#'):
            c = c[1:]
            if len(c) == 6:
                return (int(c[0:2],16), int(c[2:4],16), int(c[4:6],16))
    return (0,0,0)

def get_font_for_style(style):
    return 'DejaVuSans'  # خط آمن على Linux

def create_default_avatar():
    path = os.path.join(AVATARS_DIR, 'default.png')
    if not os.path.exists(path) and PILLOW_AVAILABLE:
        img = Image.new('RGB', (400,400), (73,109,137))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 40)
        except:
            font = ImageFont.load_default()
        d.text((100,180), "AI Avatar", fill=(255,255,255), font=font)
        img.save(path)
    return path if os.path.exists(path) else None

DEFAULT_AVATAR = create_default_avatar()

def generate_audio(text, out_path):
    if GTTS_AVAILABLE:
        tts = gTTS(text=text, lang='ar')
        tts.save(out_path)
        return out_path
    return None

def create_video_simple(text, out_path, duration=5, style='عادي', txt_color=None, bg_color=None, audio_path=None):
    w, h = 640, 480
    bg_rgb = color_to_rgb(bg_color)
    txt_rgb = color_to_rgb(txt_color)

    if style == 'كرتوني':
        if bg_color is None: bg_rgb = color_to_rgb('#FFE066')
        if txt_color is None: txt_rgb = color_to_rgb('#FF5733')
        font_size = 40
    elif style == 'سينمائي':
        if bg_color is None: bg_rgb = color_to_rgb('#1A1A1A')
        if txt_color is None: txt_rgb = color_to_rgb('#F5F5DC')
        font_size = 36
    elif style == 'أغنية':
        if bg_color is None: bg_rgb = color_to_rgb('#2C3E50')
        if txt_color is None: txt_rgb = color_to_rgb('#F1C40F')
        font_size = 38
    else:
        if bg_color is None: bg_rgb = color_to_rgb('اسود')
        if txt_color is None: txt_rgb = color_to_rgb('ابيض')
        font_size = 30

    font_name = get_font_for_style(style)
    bg_clip = ColorClip(size=(w,h), color=bg_rgb, duration=duration)
    clips = [bg_clip]

    if style == 'سينمائي':
        bar_h = 60
        top = ColorClip(size=(w,bar_h), color=(0,0,0), duration=duration).with_position(('center',0))
        bottom = ColorClip(size=(w,bar_h), color=(0,0,0), duration=duration).with_position(('center',h-bar_h))
        clips.extend([top, bottom])

    txt_clip = TextClip(
        font=font_name, text=text, font_size=font_size, color=txt_rgb,
        bg_color=(0,0,0,0.5), size=(w-100, None),
        method='caption', text_align='center'
    ).with_position(('center', h-150)).with_duration(duration)
    clips.append(txt_clip)

    if DEFAULT_AVATAR and style != 'سينمائي':
        try:
            av = VideoClip.from_image(DEFAULT_AVATAR, duration=duration).resized(height=150)
            av = av.with_position(('center', 50))
            clips.append(av)
        except:
            pass

    final = CompositeVideoClip(clips)
    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path).with_duration(final.duration)
        final = final.with_audio(audio)

    final.write_videofile(out_path, fps=24, codec='libx264', audio_codec='aac')
    return out_path

def create_video_synced(text, audio_path, out_path, style='عادي', txt_color=None, bg_color=None):
    w, h = 640, 480
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    bg_rgb = color_to_rgb(bg_color)
    txt_rgb = color_to_rgb(txt_color)

    if style == 'كرتوني':
        if bg_color is None: bg_rgb = color_to_rgb('#FFE066')
        if txt_color is None: txt_rgb = color_to_rgb('#FF5733')
        font_size = 40
    elif style == 'سينمائي':
        if bg_color is None: bg_rgb = color_to_rgb('#1A1A1A')
        if txt_color is None: txt_rgb = color_to_rgb('#F5F5DC')
        font_size = 36
    elif style == 'أغنية':
        if bg_color is None: bg_rgb = color_to_rgb('#2C3E50')
        if txt_color is None: txt_rgb = color_to_rgb('#F1C40F')
        font_size = 38
    else:
        if bg_color is None: bg_rgb = color_to_rgb('اسود')
        if txt_color is None: txt_rgb = color_to_rgb('ابيض')
        font_size = 30

    font_name = get_font_for_style(style)
    bg_clip = ColorClip(size=(w,h), color=bg_rgb, duration=duration)
    clips = [bg_clip]

    if style == 'سينمائي':
        bar_h = 60
        top = ColorClip(size=(w,bar_h), color=(0,0,0), duration=duration).with_position(('center',0))
        bottom = ColorClip(size=(w,bar_h), color=(0,0,0), duration=duration).with_position(('center',h-bar_h))
        clips.extend([top, bottom])

    words = text.split()
    seg = duration / len(words) if words else duration
    for i, wd in enumerate(words):
        clip = TextClip(
            font=font_name, text=wd, font_size=font_size, color=txt_rgb,
            bg_color=(0,0,0,0.5), size=(w-100, None), method='caption'
        ).with_position(('center', h-150)).with_start(i*seg).with_duration(seg)
        clips.append(clip)

    if DEFAULT_AVATAR and style != 'سينمائي':
        try:
            av = VideoClip.from_image(DEFAULT_AVATAR, duration=duration).resized(height=150)
            av = av.with_position(('center', 50))
            clips.append(av)
        except:
            pass

    final = CompositeVideoClip(clips).with_audio(audio_clip)
    final.write_videofile(out_path, fps=24, codec='libx264', audio_codec='aac')
    return out_path

# ============================================
# 4. واجهة HTML (مضمنة)
# ============================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مولد الفيديو الذكي</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Tahoma;background:linear-gradient(135deg,#1e3c72,#2a5298);padding:20px}
.container{max-width:950px;margin:auto;background:#fff;border-radius:30px;overflow:hidden}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:35px;text-align:center}
.content{padding:35px}
.form-group{margin-bottom:25px}
label{display:block;font-weight:bold;margin-bottom:10px}
textarea,select,input{width:100%;padding:14px;border:2px solid #e2e8f0;border-radius:16px;font-size:16px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:20px}
button{width:100%;padding:16px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:40px;font-size:18px;cursor:pointer}
.loading{display:none;text-align:center;padding:30px;background:#f1f5f9;border-radius:24px;margin-top:25px}
.spinner{border:4px solid #e2e8f0;border-top:4px solid #667eea;border-radius:50%;width:45px;height:45px;animation:spin 0.8s linear infinite;margin:0 auto 15px}
@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
.result{display:none;margin-top:25px;padding:25px;background:#d1fae5;border-radius:24px;text-align:center}
.error{display:none;background:#fee2e2;color:#b91c1c;padding:18px;border-radius:20px;margin-top:20px;text-align:center}
.info{background:#e0f2fe;padding:18px;border-radius:20px;margin-top:25px;font-size:14px;text-align:center}
@media(max-width:650px){.row{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>🎬 صانع الفيديو الذكي</h1><p>حوّل نصك إلى فيديو متحرك أو أغنية</p></div>
<div class="content">
<div class="form-group"><label>📝 النص</label><textarea id="text" rows="4" placeholder="اكتب قصتك أو أغنية..."></textarea></div>
<div class="row">
<div class="form-group"><label>🎨 النمط</label><select id="style"><option value="عادي">عادي</option><option value="كرتوني">كرتوني</option><option value="سينمائي">سينمائي</option><option value="أغنية">أغنية</option></select></div>
<div class="form-group"><label>🔊 صوت</label><select id="use_tts"><option value="true">نعم</option><option value="false">لا</option></select></div>
</div>
<div class="row">
<div class="form-group"><label>🎨 لون الخلفية</label><select id="bg_color"><option value="">افتراضي</option><option value="أسود">أسود</option><option value="أبيض">أبيض</option><option value="أحمر">أحمر</option><option value="أزرق">أزرق</option></select></div>
<div class="form-group"><label>✏️ لون النص</label><select id="txt_color"><option value="">افتراضي</option><option value="أبيض">أبيض</option><option value="أسود">أسود</option><option value="أصفر">أصفر</option></select></div>
</div>
<div class="row">
<div class="form-group"><label>⏱️ المدة (ثواني)</label><input type="number" id="duration" value="6" min="3" max="45"></div>
<div class="form-group"><label>🎬 التزامن</label><select id="sync_type"><option value="static">نص ثابت</option><option value="synced">نص متحرك مع الصوت</option></select></div>
</div>
<button id="generateBtn">✨ إنشاء الفيديو ✨</button>
<div class="loading" id="loading"><div class="spinner"></div><p>جاري الإنشاء...</p></div>
<div class="result" id="result"></div>
<div class="error" id="error"></div>
<div class="info">💡 يعمل بدون مفاتيح API.</div>
</div></div>
<script>
const genBtn=document.getElementById('generateBtn');
const loadingDiv=document.getElementById('loading');
const resultDiv=document.getElementById('result');
const errorDiv=document.getElementById('error');
genBtn.onclick=async()=>{
const text=document.getElementById('text').value.trim();
if(!text){showError('أدخل النص');return;}
const data={
text:text,
style:document.getElementById('style').value,
use_tts:document.getElementById('use_tts').value==='true',
bg_color:document.getElementById('bg_color').value||null,
text_color:document.getElementById('txt_color').value||null,
duration:parseFloat(document.getElementById('duration').value),
sync_type:document.getElementById('sync_type').value
};
showLoading(true);hideResult();hideError();
try{
const res=await fetch('/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const json=await res.json();
if(json.success)showResult(json.video_url);
else showError(json.error||'خطأ');
}catch(e){showError('فشل الاتصال');}
finally{showLoading(false);}
};
function showLoading(s){loadingDiv.style.display=s?'block':'none';genBtn.disabled=s;}
function showResult(url){resultDiv.innerHTML=`<p>✅ تم الإنشاء</p><a href="${url}" download>📥 تحميل الفيديو</a><br><video width="100%" controls src="${url}"></video>`;resultDiv.style.display='block';}
function hideResult(){resultDiv.style.display='none';}
function showError(msg){errorDiv.innerHTML=`❌ ${msg}`;errorDiv.style.display='block';}
function hideError(){errorDiv.style.display='none';}
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    if not data or not data.get('text'):
        return jsonify({'error': 'لا يوجد نص'}), 400

    text = data['text']
    style = data.get('style', 'عادي')
    use_tts = data.get('use_tts', True)
    bg_color = data.get('bg_color')
    txt_color = data.get('text_color')
    duration = float(data.get('duration', 6))
    sync_type = data.get('sync_type', 'static')

    vid_id = str(uuid.uuid4())
    video_path = os.path.join(OUTPUT_DIR, f'video_{vid_id}.mp4')
    audio_path = os.path.join(OUTPUT_DIR, f'audio_{vid_id}.mp3') if use_tts else None

    try:
        if use_tts and GTTS_AVAILABLE:
            generate_audio(text, audio_path)
        if sync_type == 'synced' and audio_path and os.path.exists(audio_path):
            create_video_synced(text, audio_path, video_path, style, txt_color, bg_color)
        else:
            create_video_simple(text, video_path, duration, style, txt_color, bg_color, audio_path)
        url = url_for('download', filename=os.path.basename(video_path), _external=True)
        return jsonify({'success': True, 'video_url': url})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({'error': 'غير موجود'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
