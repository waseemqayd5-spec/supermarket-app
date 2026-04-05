import os
import sys
import uuid
import time
import requests
from flask import Flask, request, jsonify, send_file, render_template_string

# ============================
# محاولة استيراد المكتبات الأساسية
# ============================
try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: moviepy not installed. Install with: pip install moviepy")

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("Warning: gTTS not installed. Install with: pip install gtts")

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("Warning: Pillow not installed. Install with: pip install pillow")

# ============================
# إعداد Gemini API (Google AI)
# ============================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", None)
# إذا لم يتم تعيين المفتاح، حاول استخدام Gemini عبر مكتبة google-generativeai
try:
    import google.generativeai as genai
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        print("Gemini API configured successfully.")
    else:
        GEMINI_AVAILABLE = False
        print("GEMINI_API_KEY not set. Gemini video generation disabled.")
except ImportError:
    GEMINI_AVAILABLE = False
    print("google-generativeai not installed. Install with: pip install google-generativeai")

# ============================
# إعداد Flask
# ============================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
OUTPUT_DIR = os.path.join(STATIC_DIR, 'output')
AVATARS_DIR = os.path.join(STATIC_DIR, 'avatars')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AVATARS_DIR, exist_ok=True)

# صورة رمزية افتراضية
def create_default_avatar():
    path = os.path.join(AVATARS_DIR, 'default.png')
    if not os.path.exists(path) and PILLOW_AVAILABLE:
        img = Image.new('RGB', (400,400), (73,109,137))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        d.text((100,180), "AI Avatar", fill=(255,255,255), font=font)
        img.save(path)
    return path if os.path.exists(path) else None

DEFAULT_AVATAR = create_default_avatar()

# ============================
# دوال مساعدة لتحويل الألوان
# ============================
def color_to_rgb(color):
    if color is None:
        return (0,0,0)
    if isinstance(color, tuple):
        return color
    if isinstance(color, str):
        color = color.strip().lower()
        named = {
            'black':(0,0,0), 'white':(255,255,255), 'red':(255,0,0),
            'green':(0,255,0), 'blue':(0,0,255), 'yellow':(255,255,0),
            '#FFE066':(255,224,102), '#FF5733':(255,87,51), '#1A1A1A':(26,26,26),
            '#F5F5DC':(245,245,220), '#2C3E50':(44,62,80), '#F1C40F':(241,196,15)
        }
        if color in named:
            return named[color]
        if color.startswith('#'):
            color = color[1:]
        if len(color)==6:
            return (int(color[0:2],16), int(color[2:4],16), int(color[4:6],16))
    return (0,0,0)

def get_font_name(style):
    # نعيد اسم الخط (قد لا يكون موجوداً، سيعمل MoviePy بالافتراضي)
    fonts = {
        'كرتوني': 'Comic Sans MS',
        'سينمائي': 'Georgia',
        'أغنية': 'Arial',
        'عادي': 'Arial'
    }
    return fonts.get(style, 'Arial')

# ============================
# توليد الفيديو باستخدام Gemini (Veo)
# ============================
def generate_video_with_gemini(prompt_text, output_path):
    """محاولة توليد فيديو من النص باستخدام نموذج Veo من Google (إذا كان متاحاً)"""
    if not GEMINI_AVAILABLE:
        return None
    try:
        # استخدام نموذج Veo (يتطلب تفعيل خاص)
        model = genai.GenerativeModel('veo-3.1-generate-preview')
        operation = model.generate_videos(prompt=prompt_text)
        # انتظار النتيجة (قد يستغرق دقائق)
        while not operation.done():
            time.sleep(5)
        result = operation.result()
        # حفظ الفيديو
        if result.generated_videos:
            video_data = result.generated_videos[0].video_data
            with open(output_path, 'wb') as f:
                f.write(video_data)
            return output_path
    except Exception as e:
        print(f"Gemini video generation failed: {e}")
    return None

# ============================
# توليد الفيديو بالطريقة التقليدية (MoviePy + gTTS)
# ============================
def generate_audio(text, out_path):
    if GTTS_AVAILABLE:
        tts = gTTS(text=text, lang='ar')
        tts.save(out_path)
        return out_path
    return None

def create_video_local(text, out_path, duration=5, style='عادي', txt_color=None, bg_color=None, audio_path=None):
    if not MOVIEPY_AVAILABLE:
        return None
    w, h = 640, 480
    # تحديد الألوان
    if style == 'كرتوني':
        bg_rgb = color_to_rgb(bg_color or '#FFE066')
        txt_rgb = color_to_rgb(txt_color or '#FF5733')
        font_size = 40
    elif style == 'سينمائي':
        bg_rgb = color_to_rgb(bg_color or '#1A1A1A')
        txt_rgb = color_to_rgb(txt_color or '#F5F5DC')
        font_size = 36
    elif style == 'أغنية':
        bg_rgb = color_to_rgb(bg_color or '#2C3E50')
        txt_rgb = color_to_rgb(txt_color or '#F1C40F')
        font_size = 38
    else:
        bg_rgb = color_to_rgb(bg_color or 'black')
        txt_rgb = color_to_rgb(txt_color or 'white')
        font_size = 30

    font_name = get_font_name(style)
    bg_clip = ColorClip(size=(w,h), color=bg_rgb, duration=duration)
    clips = [bg_clip]

    # تأثير سينمائي
    if style == 'سينمائي':
        bar_h = 60
        top = ColorClip(size=(w,bar_h), color=(0,0,0), duration=duration).with_position(('center',0))
        bottom = ColorClip(size=(w,bar_h), color=(0,0,0), duration=duration).with_position(('center',h-bar_h))
        clips.extend([top, bottom])

    # النص
    txt_clip = TextClip(font=font_name, text=text, font_size=font_size, color=txt_rgb,
                        bg_color=(0,0,0,0.5), size=(w-100, None),
                        method='caption', text_align='center'
                       ).with_position(('center', h-150)).with_duration(duration)
    clips.append(txt_clip)

    final = CompositeVideoClip(clips)
    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path).with_duration(final.duration)
        final = final.with_audio(audio)
    final.write_videofile(out_path, fps=24, codec='libx264', audio_codec='aac')
    return out_path

# ============================
# واجهة HTML مضمنة
# ============================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>توليد فيديو من النص - Gemini AI</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box;}
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
    <div class="header">
        <h1>🎬 تحويل النص إلى فيديو</h1>
        <p>باستخدام Google Gemini AI + تقنيات الذكاء الاصطناعي</p>
    </div>
    <div class="content">
        <div class="form-group">
            <label>📝 النص المراد تحويله إلى فيديو</label>
            <textarea id="text" rows="5" placeholder="اكتب قصتك أو فكرتك هنا..."></textarea>
        </div>
        <div class="row">
            <div class="form-group">
                <label>🎨 نمط الفيديو</label>
                <select id="style">
                    <option value="عادي">عادي</option>
                    <option value="كرتوني">كرتوني</option>
                    <option value="سينمائي">سينمائي</option>
                    <option value="أغنية">أغنية</option>
                </select>
            </div>
            <div class="form-group">
                <label>🔊 تحويل النص إلى صوت</label>
                <select id="use_tts">
                    <option value="true">نعم</option>
                    <option value="false">لا</option>
                </select>
            </div>
        </div>
        <div class="row">
            <div class="form-group">
                <label>🎨 لون الخلفية (اختياري)</label>
                <input type="text" id="bg_color" placeholder="مثل: #000000 أو black">
            </div>
            <div class="form-group">
                <label>✏️ لون النص (اختياري)</label>
                <input type="text" id="txt_color" placeholder="مثل: #FFFFFF أو white">
            </div>
        </div>
        <div class="form-group">
            <label>⏱️ المدة (ثواني) - للطريقة التقليدية فقط</label>
            <input type="number" id="duration" value="5" min="3" max="30">
        </div>
        <button id="generateBtn">🚀 إنشاء الفيديو باستخدام Gemini AI</button>
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>جاري إنشاء الفيديو... قد يستغرق بضع دقائق إذا تم استخدام Gemini Veo</p>
        </div>
        <div class="result" id="result"></div>
        <div class="error" id="error"></div>
        <div class="info">
            💡 ملاحظة: إذا لم تكن خدمة Gemini Veo متاحة لحسابك، سيتم إنشاء الفيديو تلقائياً بالطريقة التقليدية (نص+صوت+خلفية).
        </div>
    </div>
</div>
<script>
    const generateBtn = document.getElementById('generateBtn');
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');

    generateBtn.onclick = async () => {
        const text = document.getElementById('text').value.trim();
        if (!text) {
            showError('الرجاء إدخال النص');
            return;
        }
        const data = {
            text: text,
            style: document.getElementById('style').value,
            use_tts: document.getElementById('use_tts').value === 'true',
            bg_color: document.getElementById('bg_color').value || null,
            text_color: document.getElementById('txt_color').value || null,
            duration: parseFloat(document.getElementById('duration').value)
        };
        showLoading(true);
        hideResult();
        hideError();
        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const json = await response.json();
            if (json.success) {
                showResult(json.video_url);
            } else {
                showError(json.error || 'حدث خطأ أثناء إنشاء الفيديو');
            }
        } catch (err) {
            showError('خطأ في الاتصال بالخادم: ' + err.message);
        } finally {
            showLoading(false);
        }
    };
    function showLoading(show) {
        loadingDiv.style.display = show ? 'block' : 'none';
        generateBtn.disabled = show;
    }
    function showResult(url) {
        resultDiv.innerHTML = `<p>✅ تم إنشاء الفيديو بنجاح!</p>
                               <a href="${url}" download>📥 تحميل الفيديو</a><br><br>
                               <video width="100%" controls><source src="${url}" type="video/mp4"></video>`;
        resultDiv.style.display = 'block';
    }
    function hideResult() { resultDiv.style.display = 'none'; }
    function showError(msg) {
        errorDiv.innerHTML = `❌ ${msg}`;
        errorDiv.style.display = 'block';
    }
    function hideError() { errorDiv.style.display = 'none'; }
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
    duration = float(data.get('duration', 5))

    video_id = str(uuid.uuid4())
    video_path = os.path.join(OUTPUT_DIR, f'video_{video_id}.mp4')
    audio_path = os.path.join(OUTPUT_DIR, f'audio_{video_id}.mp3') if use_tts else None

    # محاولة 1: استخدام Gemini Veo (إذا كان متاحاً)
    if GEMINI_AVAILABLE:
        print("Attempting to generate video with Gemini Veo...")
        gemini_video = generate_video_with_gemini(text, video_path)
        if gemini_video:
            url = url_for('download', filename=os.path.basename(video_path), _external=True)
            return jsonify({'success': True, 'video_url': url})

    # محاولة 2: الطريقة التقليدية (MoviePy + gTTS)
    if not MOVIEPY_AVAILABLE:
        return jsonify({'error': 'MoviePy غير مثبت على الخادم. يرجى تثبيته.'}), 500

    try:
        if use_tts and GTTS_AVAILABLE:
            generate_audio(text, audio_path)
        else:
            audio_path = None
        create_video_local(text, video_path, duration, style, txt_color, bg_color, audio_path)
        url = url_for('download', filename=os.path.basename(video_path), _external=True)
        return jsonify({'success': True, 'video_url': url})
    except Exception as e:
        print(f"Error in generate: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({'error': 'الملف غير موجود'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
