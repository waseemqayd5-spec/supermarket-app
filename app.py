import os
import uuid
from flask import Flask, request, jsonify, send_file, render_template_string

# استيراد المكتبات مع معالجة الأخطاء
try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
except ImportError:
    print("ERROR: moviepy not installed. Run: pip install moviepy")
    exit(1)

try:
    from gtts import gTTS
except ImportError:
    print("ERROR: gTTS not installed")
    exit(1)

app = Flask(__name__)

# إعداد المجلدات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'static', 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def color_to_rgb(color):
    """تحويل اسم اللون إلى RGB tuple"""
    if not color:
        return (0,0,0)
    c = color.strip().lower()
    colors = {
        'اسود': (0,0,0), 'ابيض': (255,255,255), 'احمر': (255,0,0),
        'اخضر': (0,255,0), 'ازرق': (0,0,255), 'اصفر': (255,255,0),
        '#FFE066': (255,224,102), '#FF5733': (255,87,51), '#1A1A1A': (26,26,26),
        '#F5F5DC': (245,245,220), '#2C3E50': (44,62,80), '#F1C40F': (241,196,15)
    }
    if c in colors:
        return colors[c]
    if c.startswith('#') and len(c)==7:
        return (int(c[1:3],16), int(c[3:5],16), int(c[5:7],16))
    return (0,0,0)

def generate_audio(text, path):
    tts = gTTS(text=text, lang='ar')
    tts.save(path)
    return path

def create_video(text, output_path, duration=5, style='عادي', bg_color=None, txt_color=None, audio_path=None):
    """دالة مبسطة لإنشاء الفيديو - تضمن عدم وجود أخطاء float/int"""
    w, h = 640, 480
    # تحويل المدة إلى float (MoviePy تقبل float)
    dur = float(duration)
    
    # تعيين الألوان حسب النمط
    if style == 'كرتوني':
        bg = color_to_rgb(bg_color or '#FFE066')
        txt_col = color_to_rgb(txt_color or '#FF5733')
        font_size = 40
    elif style == 'سينمائي':
        bg = color_to_rgb(bg_color or '#1A1A1A')
        txt_col = color_to_rgb(txt_color or '#F5F5DC')
        font_size = 36
    elif style == 'أغنية':
        bg = color_to_rgb(bg_color or '#2C3E50')
        txt_col = color_to_rgb(txt_color or '#F1C40F')
        font_size = 38
    else:
        bg = color_to_rgb(bg_color or 'اسود')
        txt_col = color_to_rgb(txt_color or 'ابيض')
        font_size = 30

    # إنشاء الخلفية
    background = ColorClip(size=(w, h), color=bg, duration=dur)
    
    # إنشاء النص
    text_clip = TextClip(
        font="Arial",
        text=text,
        font_size=font_size,
        color=txt_col,
        bg_color=(0,0,0,0.5),
        size=(w-100, None),
        method='caption',
        text_align='center'
    ).with_position(('center', h-150)).with_duration(dur)
    
    # تجميع الفيديو
    video = CompositeVideoClip([background, text_clip])
    
    # إضافة الصوت إذا وجد
    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path).with_duration(dur)
        video = video.with_audio(audio)
    
    # حفظ الفيديو
    video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    return output_path

def create_video_synced(text, audio_path, output_path, style='عادي', bg_color=None, txt_color=None):
    """فيديو متزامن مع الصوت (كلمة كلمة) - بدون أخطاء float"""
    w, h = 640, 480
    audio = AudioFileClip(audio_path)
    dur = float(audio.duration)  # مدة الصوت
    
    # تعيين الألوان
    if style == 'كرتوني':
        bg = color_to_rgb(bg_color or '#FFE066')
        txt_col = color_to_rgb(txt_color or '#FF5733')
        font_size = 40
    elif style == 'سينمائي':
        bg = color_to_rgb(bg_color or '#1A1A1A')
        txt_col = color_to_rgb(txt_color or '#F5F5DC')
        font_size = 36
    elif style == 'أغنية':
        bg = color_to_rgb(bg_color or '#2C3E50')
        txt_col = color_to_rgb(txt_color or '#F1C40F')
        font_size = 38
    else:
        bg = color_to_rgb(bg_color or 'اسود')
        txt_col = color_to_rgb(txt_color or 'ابيض')
        font_size = 30
    
    background = ColorClip(size=(w, h), color=bg, duration=dur)
    clips = [background]
    
    # تقسيم النص إلى كلمات
    words = text.split()
    if not words:
        words = [text]
    seg_dur = dur / len(words)  # float
    
    for i, word in enumerate(words):
        word_clip = TextClip(
            font="Arial",
            text=word,
            font_size=font_size,
            color=txt_col,
            bg_color=(0,0,0,0.5),
            size=(w-100, None),
            method='caption'
        ).with_position(('center', h-150)).with_start(i * seg_dur).with_duration(seg_dur)
        clips.append(word_clip)
    
    final = CompositeVideoClip(clips).with_audio(audio)
    final.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    return output_path

# HTML الواجهة (نفس السابق)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><title>مولد الفيديو الذكي</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Tahoma;background:linear-gradient(135deg,#1e3c72,#2a5298);padding:20px}
.container{max-width:950px;margin:auto;background:#fff;border-radius:30px;overflow:hidden}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:35px;text-align:center}
.content{padding:35px}
.form-group{margin-bottom:25px}
label{display:block;font-weight:bold;margin-bottom:10px}
textarea,select,input{width:100%;padding:14px;border:2px solid #e2e8f0;border-radius:16px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:20px}
button{width:100%;padding:16px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:40px;font-size:18px;cursor:pointer}
.loading{display:none;text-align:center;padding:30px;background:#f1f5f9;border-radius:24px;margin-top:25px}
.spinner{border:4px solid #e2e8f0;border-top:4px solid #667eea;border-radius:50%;width:45px;height:45px;animation:spin 0.8s linear infinite;margin:0 auto}
@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
.result{display:none;margin-top:25px;padding:25px;background:#d1fae5;border-radius:24px;text-align:center}
.error{display:none;background:#fee2e2;color:#b91c1c;padding:18px;border-radius:20px;margin-top:20px}
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
<div class="form-group"><label>🎨 لون الخلفية</label><select id="bg_color"><option value="">افتراضي</option><option value="أسود">أسود</option><option value="أبيض">أبيض</option><option value="أحمر">أحمر</option></select></div>
<div class="form-group"><label>✏️ لون النص</label><select id="txt_color"><option value="">افتراضي</option><option value="أبيض">أبيض</option><option value="أسود">أسود</option></select></div>
</div>
<div class="row">
<div class="form-group"><label>⏱️ المدة (ثواني)</label><input type="number" id="duration" value="6" min="3" max="45" step="1"></div>
<div class="form-group"><label>🎬 التزامن</label><select id="sync_type"><option value="static">نص ثابت</option><option value="synced">نص متحرك مع الصوت</option></select></div>
</div>
<button id="generateBtn">✨ إنشاء الفيديو ✨</button>
<div class="loading" id="loading"><div class="spinner"></div><p>جاري الإنشاء...</p></div>
<div class="result" id="result"></div>
<div class="error" id="error"></div>
<div class="info">💡 يعمل بدون مفاتيح API. اختر "نص متحرك مع الصوت" لتحصل على فيديو أغنية.</div>
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
        if use_tts:
            generate_audio(text, audio_path)
        
        if sync_type == 'synced' and use_tts:
            create_video_synced(text, audio_path, video_path, style, bg_color, txt_color)
        else:
            create_video(text, video_path, duration, style, bg_color, txt_color, audio_path)
        
        video_url = url_for('download', filename=os.path.basename(video_path), _external=True)
        return jsonify({'success': True, 'video_url': video_url})
    except Exception as e:
        print(f"Error: {e}")
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
