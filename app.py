import os
import sys
import uuid
import time
from flask import Flask, request, jsonify, send_file, render_template_string

# ==================================================
# استيراد المكتبات الأساسية مع التحقق من وجودها
# ==================================================
try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("ERROR: moviepy not installed. Run: pip install moviepy")
    sys.exit(1)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("ERROR: gTTS not installed. Run: pip install gtts")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("ERROR: Pillow not installed. Run: pip install pillow")
    sys.exit(1)

# ==================================================
# إعداد Flask والمجلدات
# ==================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
OUTPUT_DIR = os.path.join(STATIC_DIR, 'output')
AVATARS_DIR = os.path.join(STATIC_DIR, 'avatars')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AVATARS_DIR, exist_ok=True)

# ==================================================
# دالة إنشاء صورة رمزية افتراضية (Avatar)
# ==================================================
def create_default_avatar():
    path = os.path.join(AVATARS_DIR, 'default.png')
    if not os.path.exists(path):
        img = Image.new('RGB', (400, 400), color=(73, 109, 137))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        draw.text((100, 180), "AI Avatar", fill=(255, 255, 255), font=font)
        img.save(path)
    return path

DEFAULT_AVATAR = create_default_avatar()

# ==================================================
# دوال تحويل الألوان من نص إلى RGB (لـ moviepy)
# ==================================================
def color_to_rgb(color):
    """تحويل اسم اللون أو رمز Hex إلى tuple (R,G,B)"""
    if color is None:
        return (0, 0, 0)
    if isinstance(color, tuple):
        return color
    if isinstance(color, str):
        color = color.strip().lower()
        named_colors = {
            'black': (0,0,0), 'white': (255,255,255), 'red': (255,0,0),
            'green': (0,255,0), 'blue': (0,0,255), 'yellow': (255,255,0),
            'navy': (0,0,128), 'darkgreen': (0,100,0), 'purple': (128,0,128),
            'orange': (255,165,0), 'pink': (255,192,203), 'brown': (165,42,42),
            '#FFE066': (255,224,102), '#FF5733': (255,87,51), '#1A1A1A': (26,26,26),
            '#F5F5DC': (245,245,220), '#2C3E50': (44,62,80), '#F1C40F': (241,196,15)
        }
        if color in named_colors:
            return named_colors[color]
        if color.startswith('#'):
            color = color[1:]
        if len(color) == 6:
            return (int(color[0:2],16), int(color[2:4],16), int(color[4:6],16))
        if len(color) == 3:
            return (int(color[0]*2,16), int(color[1]*2,16), int(color[2]*2,16))
    return (0,0,0)

# ==================================================
# دالة الحصول على اسم الخط المناسب للنمط
# ==================================================
def get_font_for_style(style):
    fonts = {
        'كرتوني': 'Comic Sans MS',
        'سينمائي': 'Georgia',
        'أغنية': 'Arial',
        'عادي': 'Arial'
    }
    return fonts.get(style, 'Arial')

# ==================================================
# دالة تحويل النص إلى ملف صوتي (باستخدام gTTS)
# ==================================================
def generate_audio(text, output_path):
    if GTTS_AVAILABLE:
        tts = gTTS(text=text, lang='ar')
        tts.save(output_path)
        return output_path
    return None

# ==================================================
# دالة إنشاء فيديو بنص ثابت + خلفية + صوت اختياري
# ==================================================
def create_video_simple(text, output_path, duration=5, style='عادي', txt_color=None, bg_color=None, audio_path=None):
    w, h = 640, 480
    
    # تحديد الألوان والأحجام حسب النمط
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
    else:  # عادي
        bg_rgb = color_to_rgb(bg_color or 'black')
        txt_rgb = color_to_rgb(txt_color or 'white')
        font_size = 30
    
    font_name = get_font_for_style(style)
    
    # خلفية الفيديو
    background = ColorClip(size=(w, h), color=bg_rgb, duration=duration)
    clips = [background]
    
    # تأثير السينما (شريط أسود أعلى وأسفل)
    if style == 'سينمائي':
        bar_height = 60
        top_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', 0))
        bottom_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', h - bar_height))
        clips.extend([top_bar, bottom_bar])
    
    # النص الرئيسي
    text_clip = TextClip(
        font=font_name,
        text=text,
        font_size=font_size,
        color=txt_rgb,
        bg_color=(0,0,0,0.6),
        size=(w - 100, None),
        method='caption',
        text_align='center'
    ).with_position(('center', h - 150)).with_duration(duration)
    clips.append(text_clip)
    
    # إضافة الصورة الرمزية (اختيارية، لا تظهر في النمط السينمائي)
    if DEFAULT_AVATAR and style != 'سينمائي':
        try:
            avatar_clip = VideoClip.from_image(DEFAULT_AVATAR, duration=duration).resized(height=150)
            avatar_clip = avatar_clip.with_position(('center', 50))
            clips.append(avatar_clip)
        except:
            pass
    
    final_video = CompositeVideoClip(clips)
    
    # إضافة الصوت إذا وُجد
    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path).with_duration(final_video.duration)
        final_video = final_video.with_audio(audio)
    
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    return output_path

# ==================================================
# دالة إنشاء فيديو بنص متزامن مع الصوت (كلمة كلمة)
# ==================================================
def create_video_synced(text, audio_path, output_path, style='عادي', txt_color=None, bg_color=None):
    w, h = 640, 480
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    # نفس الألوان والخطوط
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
    
    font_name = get_font_for_style(style)
    
    background = ColorClip(size=(w, h), color=bg_rgb, duration=duration)
    clips = [background]
    
    if style == 'سينمائي':
        bar_height = 60
        top_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', 0))
        bottom_bar = ColorClip(size=(w, bar_height), color=(0,0,0), duration=duration).with_position(('center', h - bar_height))
        clips.extend([top_bar, bottom_bar])
    
    # تقطيع النص إلى كلمات
    words = text.split()
    seg_duration = duration / len(words) if words else duration
    for i, word in enumerate(words):
        word_clip = TextClip(
            font=font_name,
            text=word,
            font_size=font_size,
            color=txt_rgb,
            bg_color=(0,0,0,0.5),
            size=(w - 100, None),
            method='caption'
        ).with_position(('center', h - 150)).with_start(i * seg_duration).with_duration(seg_duration)
        clips.append(word_clip)
    
    if DEFAULT_AVATAR and style != 'سينمائي':
        try:
            avatar_clip = VideoClip.from_image(DEFAULT_AVATAR, duration=duration).resized(height=150)
            avatar_clip = avatar_clip.with_position(('center', 50))
            clips.append(avatar_clip)
        except:
            pass
    
    final_video = CompositeVideoClip(clips).with_audio(audio_clip)
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    return output_path

# ==================================================
# واجهة HTML (مضمنة) – جميلة وسهلة الاستخدام
# ==================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مولد الفيديو الذكي - تحويل النص إلى فيديو</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 950px;
            margin: 0 auto;
            background: rgba(255,255,255,0.95);
            border-radius: 30px;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 35px;
            text-align: center;
        }
        .header h1 { font-size: 32px; margin-bottom: 10px; letter-spacing: -0.5px; }
        .header p { opacity: 0.9; font-size: 16px; }
        .content { padding: 35px; }
        .form-group { margin-bottom: 25px; }
        label { display: block; font-weight: 700; margin-bottom: 10px; color: #1e293b; font-size: 15px; }
        textarea, select, input {
            width: 100%;
            padding: 14px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 16px;
            font-size: 16px;
            font-family: inherit;
            transition: all 0.2s;
            background: #f8fafc;
        }
        textarea:focus, select:focus, input:focus {
            outline: none;
            border-color: #667eea;
            background: white;
        }
        textarea { resize: vertical; min-height: 140px; }
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        button {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 40px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 10px;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 20px 25px -12px rgba(102,126,234,0.5);
        }
        button:disabled {
            opacity: 0.6;
            transform: none;
            cursor: not-allowed;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 30px;
            background: #f1f5f9;
            border-radius: 24px;
            margin-top: 25px;
        }
        .spinner {
            border: 4px solid #e2e8f0;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 45px;
            height: 45px;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .result {
            display: none;
            margin-top: 25px;
            padding: 25px;
            background: #d1fae5;
            border-radius: 24px;
            text-align: center;
        }
        .result a {
            display: inline-block;
            background: #10b981;
            color: white;
            padding: 12px 24px;
            border-radius: 40px;
            text-decoration: none;
            margin: 15px 0;
        }
        .error {
            display: none;
            background: #fee2e2;
            color: #b91c1c;
            padding: 18px;
            border-radius: 20px;
            margin-top: 20px;
            text-align: center;
        }
        .info {
            background: #e0f2fe;
            padding: 18px;
            border-radius: 20px;
            margin-top: 25px;
            font-size: 14px;
            color: #0369a1;
            text-align: center;
        }
        @media (max-width: 650px) { .row { grid-template-columns: 1fr; } .content { padding: 25px; } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🎬 صانع الفيديو الذكي</h1>
        <p>حوّل أفكارك النصية إلى فيديو احترافي بدون أي API خارجي</p>
    </div>
    <div class="content">
        <div class="form-group">
            <label>📝 النص الذي تريد تحويله إلى فيديو</label>
            <textarea id="text" rows="4" placeholder="مثال: في يوم من الأيام، كان هناك طفل صغير يحب استكشاف العالم..."></textarea>
        </div>
        <div class="row">
            <div class="form-group">
                <label>🎨 النمط البصري</label>
                <select id="style">
                    <option value="عادي">📄 عادي (كلاسيكي)</option>
                    <option value="كرتوني">🎈 كرتوني (مرح وجذاب)</option>
                    <option value="سينمائي">🎞️ سينمائي (فيلمي)</option>
                    <option value="أغنية">🎵 أغنية (ألوان دافئة)</option>
                </select>
            </div>
            <div class="form-group">
                <label>🔊 تحويل النص إلى صوت (تلقائي)</label>
                <select id="use_tts">
                    <option value="true">✅ نعم، أضف صوتاً</option>
                    <option value="false">❌ لا، فيديو صامت</option>
                </select>
            </div>
        </div>
        <div class="row">
            <div class="form-group">
                <label>🎨 لون الخلفية (اختياري)</label>
                <input type="text" id="bg_color" placeholder="مثل: black أو #FF0000">
            </div>
            <div class="form-group">
                <label>✏️ لون النص (اختياري)</label>
                <input type="text" id="txt_color" placeholder="مثل: white أو #FFFF00">
            </div>
        </div>
        <div class="row">
            <div class="form-group">
                <label>⏱️ مدة الفيديو (ثواني) - للنص الثابت فقط</label>
                <input type="number" id="duration" value="6" min="3" max="45">
            </div>
            <div class="form-group">
                <label>🎬 نوع التزامن</label>
                <select id="sync_type">
                    <option value="static">نص ثابت (أسرع)</option>
                    <option value="synced">نص متحرك مع الصوت (كلمة كلمة)</option>
                </select>
            </div>
        </div>
        <button id="generateBtn">✨ إنشاء الفيديو الآن ✨</button>
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>جاري إنشاء الفيديو... قد يستغرق 10-30 ثانية حسب طول النص</p>
        </div>
        <div class="result" id="result"></div>
        <div class="error" id="error"></div>
        <div class="info">
            💡 هذا الموقع يعمل بدون أي مفاتيح API خارجية. يستخدم تقنيات مفتوحة المصدر (MoviePy + gTTS) لإنشاء فيديوهات عالية الجودة. يمكنك تشغيله محلياً أو نشره على Render.
        </div>
    </div>
</div>
<script>
    const genBtn = document.getElementById('generateBtn');
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');

    genBtn.onclick = async () => {
        const text = document.getElementById('text').value.trim();
        if (!text) {
            showError('يرجى كتابة النص أولاً.');
            return;
        }
        const data = {
            text: text,
            style: document.getElementById('style').value,
            use_tts: document.getElementById('use_tts').value === 'true',
            bg_color: document.getElementById('bg_color').value || null,
            text_color: document.getElementById('txt_color').value || null,
            duration: parseFloat(document.getElementById('duration').value),
            sync_type: document.getElementById('sync_type').value
        };
        showLoading(true);
        hideResult();
        hideError();
        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const json = await response.json();
            if (json.success) {
                showResult(json.video_url);
            } else {
                showError(json.error || 'حدث خطأ أثناء التوليد');
            }
        } catch (err) {
            showError('فشل الاتصال بالخادم: ' + err.message);
        } finally {
            showLoading(false);
        }
    };
    function showLoading(show) {
        loadingDiv.style.display = show ? 'block' : 'none';
        genBtn.disabled = show;
    }
    function showResult(url) {
        resultDiv.innerHTML = `<p>✅ تم إنشاء الفيديو بنجاح!</p>
                               <a href="${url}" download>📥 تحميل الفيديو (MP4)</a>
                               <br><br>
                               <video width="100%" controls autoplay muted>
                                   <source src="${url}" type="video/mp4">
                                   متصفحك لا يدعم عرض الفيديو.
                               </video>`;
        resultDiv.style.display = 'block';
    }
    function hideResult() { resultDiv.style.display = 'none'; }
    function showError(msg) { errorDiv.innerHTML = `❌ ${msg}`; errorDiv.style.display = 'block'; }
    function hideError() { errorDiv.style.display = 'none'; }
</script>
</body>
</html>
"""

# ==================================================
# نقاط النهاية (Routes)
# ==================================================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate_video():
    data = request.get_json()
    if not data or not data.get('text'):
        return jsonify({'error': 'الرجاء إدخال النص'}), 400

    text = data['text']
    style = data.get('style', 'عادي')
    use_tts = data.get('use_tts', True)
    bg_color = data.get('bg_color')
    txt_color = data.get('text_color')
    duration = float(data.get('duration', 6))
    sync_type = data.get('sync_type', 'static')

    video_id = str(uuid.uuid4())
    video_path = os.path.join(OUTPUT_DIR, f'video_{video_id}.mp4')
    audio_path = os.path.join(OUTPUT_DIR, f'audio_{video_id}.mp3') if use_tts else None

    try:
        # توليد الصوت إذا طلب المستخدم
        if use_tts and GTTS_AVAILABLE:
            generate_audio(text, audio_path)
        else:
            audio_path = None

        # اختيار نوع الفيديو
        if sync_type == 'synced' and audio_path and os.path.exists(audio_path):
            create_video_synced(text, audio_path, video_path, style, txt_color, bg_color)
        else:
            create_video_simple(text, video_path, duration, style, txt_color, bg_color, audio_path)

        video_url = url_for('download_video', filename=os.path.basename(video_path), _external=True)
        return jsonify({'success': True, 'video_url': video_url})

    except Exception as e:
        print(f"Error in /generate: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_video(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, mimetype='video/mp4')
    return jsonify({'error': 'الملف غير موجود'}), 404

# ==================================================
# تشغيل الخادم
# ==================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 تشغيل الخادم على http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
