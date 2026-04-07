import os
import uuid
import subprocess
import numpy as np
from flask import Flask, request, jsonify, send_file, render_template_string
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# إعداد المجلدات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'static', 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def color_to_bgr(color_name):
    """تحويل اسم اللون إلى قيمة BGR (لـ OpenCV)"""
    colors = {
        'اسود': (0,0,0), 'ابيض': (255,255,255), 'احمر': (0,0,255),
        'اخضر': (0,255,0), 'ازرق': (255,0,0), 'اصفر': (0,255,255),
        '#FFE066': (102,224,255), '#FF5733': (51,87,255), '#1A1A1A': (26,26,26),
        '#F5F5DC': (220,245,245), '#2C3E50': (80,62,44), '#F1C40F': (15,196,241)
    }
    c = color_name.strip().lower() if color_name else ''
    if c in colors:
        return colors[c]
    if c.startswith('#') and len(c)==7:
        return (int(c[5:7],16), int(c[3:5],16), int(c[1:3],16))  # BGR
    return (0,0,0)

def get_font_path():
    """إيجاد مسار خط مناسب في النظام"""
    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",  # Mac
        "C:\\Windows\\Fonts\\arial.ttf"         # Windows
    ]
    for font in possible_fonts:
        if os.path.exists(font):
            return font
    return None

def create_video_frames(text, output_video_path, duration=5, style='عادي', bg_color=None, txt_color=None, fps=24):
    """
    إنشاء فيديو عن طريق توليد إطارات (frames) باستخدام PIL و OpenCV.
    هذه الطريقة تتجنب مشاكل MoviePy تمامًا.
    """
    w, h = 640, 480
    duration = float(duration)
    total_frames = int(fps * duration)
    
    # تحديد الألوان
    if style == 'كرتوني':
        bg = color_to_bgr(bg_color or '#FFE066')
        txt_col = (51,87,255)  # برتقالي محمر
        font_size = 50
    elif style == 'سينمائي':
        bg = color_to_bgr(bg_color or '#1A1A1A')
        txt_col = (220,245,245)
        font_size = 45
    elif style == 'أغنية':
        bg = color_to_bgr(bg_color or '#2C3E50')
        txt_col = (15,196,241)
        font_size = 48
    else:
        bg = color_to_bgr(bg_color or 'اسود')
        txt_col = color_to_bgr(txt_color or 'ابيض')
        font_size = 40
    
    # تجهيز الخط
    font_path = get_font_path()
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # إنشاء الإطارات
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_video = cv2.VideoWriter(output_video_path, fourcc, fps, (w, h))
    
    for frame_idx in range(total_frames):
        # إنشاء صورة خلفية بلون bg
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:] = bg
        
        # تحويل إلى PIL للكتابة النصية العربية
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        # حساب حجم النص وتوسيطه
        bbox = draw.textbbox((0,0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (w - text_width) // 2
        y = h - 150 - text_height
        
        draw.text((x, y), text, font=font, fill=(txt_col[2], txt_col[1], txt_col[0]))
        
        # إضافة شريط سينمائي إن وجد
        if style == 'سينمائي':
            bar_height = 60
            draw.rectangle([(0,0), (w, bar_height)], fill=(0,0,0))
            draw.rectangle([(0,h-bar_height), (w, h)], fill=(0,0,0))
        
        # إضافة صورة رمزية (اختيارية)
        # يمكن إضافتها لاحقاً
        
        # تحويل PIL إلى OpenCV
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        out_video.write(frame)
    
    out_video.release()
    return output_video_path

def create_video_synced_frames(text, audio_path, output_video_path, style='عادي', bg_color=None, txt_color=None, fps=24):
    """
    فيديو متزامن مع الصوت: كل كلمة تظهر في توقيتها.
    نقرأ الصوت لنحصل على مدته، ثم نوزع الكلمات على الإطارات.
    """
    # الحصول على مدة الصوت باستخدام ffprobe
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip())
    
    w, h = 640, 480
    total_frames = int(fps * duration)
    
    # تحديد الألوان (نفس ما سبق)
    if style == 'كرتوني':
        bg = color_to_bgr(bg_color or '#FFE066')
        txt_col = (51,87,255)
        font_size = 50
    elif style == 'سينمائي':
        bg = color_to_bgr(bg_color or '#1A1A1A')
        txt_col = (220,245,245)
        font_size = 45
    elif style == 'أغنية':
        bg = color_to_bgr(bg_color or '#2C3E50')
        txt_col = (15,196,241)
        font_size = 48
    else:
        bg = color_to_bgr(bg_color or 'اسود')
        txt_col = color_to_bgr(txt_color or 'ابيض')
        font_size = 40
    
    font_path = get_font_path()
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # تقسيم النص إلى كلمات وتوزيعها على الإطارات
    words = text.split()
    if not words:
        words = [text]
    frames_per_word = max(1, total_frames // len(words))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_video = cv2.VideoWriter(output_video_path, fourcc, fps, (w, h))
    
    word_index = 0
    for frame_idx in range(total_frames):
        # تحديد الكلمة الحالية
        current_word = words[min(word_index, len(words)-1)]
        if frame_idx > 0 and frame_idx % frames_per_word == 0 and word_index < len(words)-1:
            word_index += 1
            current_word = words[word_index]
        
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:] = bg
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        bbox = draw.textbbox((0,0), current_word, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (w - text_width) // 2
        y = h - 150 - text_height
        draw.text((x, y), current_word, font=font, fill=(txt_col[2], txt_col[1], txt_col[0]))
        
        if style == 'سينمائي':
            bar_height = 60
            draw.rectangle([(0,0), (w, bar_height)], fill=(0,0,0))
            draw.rectangle([(0,h-bar_height), (w, h)], fill=(0,0,0))
        
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        out_video.write(frame)
    
    out_video.release()
    
    # دمج الصوت مع الفيديو باستخدام ffmpeg
    output_with_audio = output_video_path.replace('.mp4', '_with_audio.mp4')
    cmd = [
        'ffmpeg', '-y', '-i', output_video_path, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
        '-shortest', output_with_audio
    ]
    subprocess.run(cmd, capture_output=True)
    os.replace(output_with_audio, output_video_path)
    
    return output_video_path

def generate_audio(text, path):
    tts = gTTS(text=text, lang='ar')
    tts.save(path)
    return path

# HTML (نفس السابق تقريباً)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><title>مولد الفيديو الذكي - OpenCV</title>
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
<div class="header"><h1>🎬 صانع الفيديو الذكي (نسخة OpenCV)</h1><p>حوّل نصك إلى فيديو متحرك أو أغنية</p></div>
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
<div class="form-group"><label>⏱️ المدة (ثواني) - للنص الثابت</label><input type="number" id="duration" value="6" min="3" max="45" step="1"></div>
<div class="form-group"><label>🎬 التزامن</label><select id="sync_type"><option value="static">نص ثابت</option><option value="synced">نص متحرك مع الصوت</option></select></div>
</div>
<button id="generateBtn">✨ إنشاء الفيديو ✨</button>
<div class="loading" id="loading"><div class="spinner"></div><p>جاري الإنشاء... قد يستغرق 20-40 ثانية</p></div>
<div class="result" id="result"></div>
<div class="error" id="error"></div>
<div class="info">💡 هذه النسخة تستخدم OpenCV و FFmpeg مباشرة، وهي خالية تماماً من أخطاء MoviePy.</div>
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
            create_video_synced_frames(text, audio_path, video_path, style, bg_color, txt_color)
        else:
            create_video_frames(text, video_path, duration, style, bg_color, txt_color)
            # إذا كان هناك صوت ولم يكن متزامناً، ندمجه
            if use_tts and audio_path:
                # دمج الصوت مع الفيديو باستخدام ffmpeg
                temp_video = video_path.replace('.mp4', '_temp.mp4')
                os.rename(video_path, temp_video)
                cmd = [
                    'ffmpeg', '-y', '-i', temp_video, '-i', audio_path,
                    '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                    '-shortest', video_path
                ]
                subprocess.run(cmd, capture_output=True)
                os.remove(temp_video)
        
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
