import os
import sys
import uuid
import time
from flask import Flask, request, jsonify, send_file, render_template_string

# ==================================================
# تأكد من استيراد المكتبات مع معالجة الأخطاء
# ==================================================
try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
except ImportError:
    print("ERROR: moviepy not installed. Run: pip install moviepy")
    sys.exit(1)

try:
    from gtts import gTTS
except ImportError:
    print("ERROR: gTTS not installed. Run: pip install gtts")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install pillow")
    sys.exit(1)

# ElevenLabs اختياري
try:
    from elevenlabs import generate, set_api_key, Voice, VoiceSettings
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    print("Warning: elevenlabs not installed. Voice will use gTTS only.")

# ==================================================
# إعداد التطبيق والمجلدات
# ==================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
OUTPUT_DIR = os.path.join(STATIC_DIR, 'output')
AVATARS_DIR = os.path.join(STATIC_DIR, 'avatars')

# إنشاء المجلدات مع التحقق من الصلاحيات
try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(AVATARS_DIR, exist_ok=True)
    print(f"Directories created: {OUTPUT_DIR}, {AVATARS_DIR}")
except Exception as e:
    print(f"ERROR creating directories: {e}")
    sys.exit(1)

# إنشاء صورة افتراضية (Avatar)
def create_default_avatar():
    default_path = os.path.join(AVATARS_DIR, 'default.png')
    if not os.path.exists(default_path):
        try:
            img = Image.new('RGB', (400, 400), color=(73, 109, 137))
            d = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except IOError:
                font = ImageFont.load_default()
            d.text((100, 180), "AI Avatar", fill=(255, 255, 255), font=font)
            img.save(default_path)
            print(f"Default avatar created at {default_path}")
        except Exception as e:
            print(f"Failed to create default avatar: {e}")
            return None
    return default_path

DEFAULT_AVATAR_PATH = create_default_avatar()
if DEFAULT_AVATAR_PATH is None:
    print("WARNING: No avatar will be used.")

# ==================================================
# دوال مساعدة لإنشاء الفيديو
# ==================================================
def generate_audio(text, output_path, use_elevenlabs=False, elevenlabs_api_key=None):
    if use_elevenlabs and elevenlabs_api_key and ELEVENLABS_AVAILABLE:
        try:
            set_api_key(elevenlabs_api_key)
            audio_data = generate(
                text=text,
                voice=Voice(
                    voice_id='EXAVITQu4vrTQcpA88OZ',
                    settings=VoiceSettings(stability=0.35, similarity_boost=0.75)
                )
            )
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            print(f"Audio generated with ElevenLabs: {output_path}")
            return output_path
        except Exception as e:
            print(f"ElevenLabs error: {e}. Falling back to gTTS.")
    # استخدام gTTS
    tts = gTTS(text=text, lang='ar')
    tts.save(output_path)
    print(f"Audio generated with gTTS: {output_path}")
    return output_path

def create_video_from_text(text, output_path, duration=5, avatar_path=None, bg_color='black', text_color='white'):
    video_width, video_height = 640, 480
    avatar = avatar_path if avatar_path and os.path.exists(avatar_path) else DEFAULT_AVATAR_PATH

    background_clip = ColorClip(size=(video_width, video_height), color=bg_color, duration=duration)

    text_clip = TextClip(
        font="Arial",
        text=text,
        font_size=30,
        color=text_color,
        bg_color='rgba(0,0,0,0.6)',
        size=(video_width - 100, None),
        method='caption',
        text_align='center'
    ).with_position(('center', video_height - 150)).with_duration(duration)

    clips = [background_clip, text_clip]
    if avatar:
        try:
            avatar_clip = VideoClip.from_image(avatar, duration=duration)
            avatar_clip = avatar_clip.resized(height=150)
            avatar_clip = avatar_clip.with_position(('center', 50))
            clips.append(avatar_clip)
        except Exception as e:
            print(f"Failed to add avatar: {e}")

    final_video = CompositeVideoClip(clips)
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    print(f"Video created (static text): {output_path}")
    return output_path

def create_video_with_audio(text, audio_path, output_path, avatar_path=None, bg_color='black', text_color='white'):
    video_width, video_height = 640, 480
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    avatar = avatar_path if avatar_path and os.path.exists(avatar_path) else DEFAULT_AVATAR_PATH

    background_clip = ColorClip(size=(video_width, video_height), color=bg_color, duration=duration)

    words = text.split()
    segment_duration = duration / len(words) if words else duration
    text_clips = []
    for i, word in enumerate(words):
        clip = TextClip(
            font="Arial",
            text=word,
            font_size=30,
            color=text_color,
            bg_color='rgba(0,0,0,0.6)',
            size=(video_width - 100, None),
            method='caption'
        ).with_position(('center', video_height - 150)).with_start(i * segment_duration).with_duration(segment_duration)
        text_clips.append(clip)

    clips = [background_clip] + text_clips
    if avatar:
        try:
            avatar_clip = VideoClip.from_image(avatar, duration=duration)
            avatar_clip = avatar_clip.resized(height=150)
            avatar_clip = avatar_clip.with_position(('center', 50))
            clips.append(avatar_clip)
        except Exception as e:
            print(f"Failed to add avatar: {e}")

    final_video = CompositeVideoClip(clips)
    final_video = final_video.with_audio(audio_clip)
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    print(f"Video created (synced text): {output_path}")
    return output_path

# ==================================================
# واجهة HTML مضمنة (نفس السابق ولكن مختصر قليلاً)
# ==================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>توليد فيديو من النص - الذكاء الاصطناعي</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .content { padding: 30px; }
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
        }
        textarea, select, input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            font-family: inherit;
            transition: border-color 0.3s;
        }
        textarea:focus, select:focus, input:focus {
            outline: none;
            border-color: #667eea;
        }
        textarea { resize: vertical; min-height: 120px; }
        .row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-top: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .result {
            display: none;
            margin-top: 20px;
            padding: 20px;
            background: #d4edda;
            border-radius: 10px;
            text-align: center;
        }
        .result a {
            color: #155724;
            font-weight: bold;
            text-decoration: none;
        }
        .result a:hover { text-decoration: underline; }
        .error {
            background: #f8d7da;
            color: #721c24;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
            display: none;
        }
        .info {
            background: #e7f3ff;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-size: 14px;
            color: #004085;
        }
        @media (max-width: 600px) {
            .row { grid-template-columns: 1fr; }
            .content { padding: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 تحويل النص إلى فيديو</h1>
            <p>بتقنيات الذكاء الاصطناعي</p>
        </div>
        <div class="content">
            <div class="form-group">
                <label>📝 النص المراد تحويله</label>
                <textarea id="textInput" placeholder="اكتب النص هنا..."></textarea>
            </div>
            <div class="row">
                <div class="form-group">
                    <label>🎨 لون الخلفية</label>
                    <select id="bgColor">
                        <option value="black">أسود</option>
                        <option value="white">أبيض</option>
                        <option value="navy">أزرق داكن</option>
                        <option value="darkgreen">أخضر داكن</option>
                        <option value="purple">بنفسجي</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>✏️ لون النص</label>
                    <select id="textColor">
                        <option value="white">أبيض</option>
                        <option value="black">أسود</option>
                        <option value="yellow">أصفر</option>
                        <option value="cyan">سماوي</option>
                    </select>
                </div>
            </div>
            <div class="row">
                <div class="form-group">
                    <label>🖼️ الصورة الرمزية</label>
                    <select id="avatar">
                        <option value="default">عرض الصورة الافتراضية</option>
                        <option value="none">إخفاء الصورة</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>🎬 نوع الفيديو</label>
                    <select id="videoType">
                        <option value="static">نص ثابت (أسهل)</option>
                        <option value="synced">نص متزامن مع الصوت</option>
                    </select>
                </div>
            </div>
            <div class="row">
                <div class="form-group">
                    <label>⏱️ المدة (ثواني) - للنص الثابت فقط</label>
                    <input type="number" id="duration" value="5" min="3" max="30">
                </div>
                <div class="form-group">
                    <label>🔊 تحويل النص إلى صوت</label>
                    <select id="useTts">
                        <option value="true">نعم</option>
                        <option value="false">لا</option>
                    </select>
                </div>
            </div>
            <div id="elevenlabsSection" style="display: none;">
                <div class="form-group">
                    <label>🎙️ ElevenLabs API Key (للحصول على جودة صوت أفضل)</label>
                    <input type="password" id="elevenlabsKey" placeholder="أدخل مفتاح API الخاص بك">
                </div>
                <div class="info">
                    💡 احصل على مفتاح مجاني من <a href="https://elevenlabs.io" target="_blank">elevenlabs.io</a>
                </div>
            </div>
            <button id="generateBtn">🚀 إنشاء الفيديو</button>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>جاري إنشاء الفيديو... قد يستغرق هذا بضع ثوانٍ</p>
            </div>
            <div class="result" id="result"></div>
            <div class="error" id="error"></div>
        </div>
    </div>

    <script>
        const useTtsSelect = document.getElementById('useTts');
        const elevenlabsSection = document.getElementById('elevenlabsSection');
        
        useTtsSelect.addEventListener('change', function() {
            elevenlabsSection.style.display = this.value === 'true' ? 'block' : 'none';
        });

        document.getElementById('generateBtn').addEventListener('click', async function() {
            const text = document.getElementById('textInput').value.trim();
            if (!text) {
                showError('الرجاء إدخال النص');
                return;
            }

            const data = {
                text: text,
                bg_color: document.getElementById('bgColor').value,
                text_color: document.getElementById('textColor').value,
                avatar: document.getElementById('avatar').value,
                video_type: document.getElementById('videoType').value,
                duration: parseFloat(document.getElementById('duration').value),
                use_tts: document.getElementById('useTts').value === 'true',
                use_elevenlabs: document.getElementById('useTts').value === 'true' && document.getElementById('elevenlabsKey').value !== '',
                elevenlabs_api_key: document.getElementById('elevenlabsKey').value || null
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
                const result = await response.json();
                if (result.success) {
                    showResult(result.video_url);
                } else {
                    showError(result.error || 'حدث خطأ أثناء إنشاء الفيديو');
                }
            } catch (error) {
                showError('خطأ في الاتصال بالخادم: ' + error.message);
            } finally {
                showLoading(false);
            }
        });

        function showLoading(show) {
            document.getElementById('loading').style.display = show ? 'block' : 'none';
            document.getElementById('generateBtn').disabled = show;
        }
        function showResult(videoUrl) {
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = `<p>✅ تم إنشاء الفيديو بنجاح!</p>
                                   <a href="${videoUrl}" download>📥 تحميل الفيديو</a>
                                   <br><br>
                                   <video width="100%" controls>
                                       <source src="${videoUrl}" type="video/mp4">
                                       متصفحك لا يدعم تشغيل الفيديو
                                   </video>`;
            resultDiv.style.display = 'block';
        }
        function hideResult() { document.getElementById('result').style.display = 'none'; }
        function showError(message) {
            const errorDiv = document.getElementById('error');
            errorDiv.innerHTML = `<p>❌ ${message}</p>`;
            errorDiv.style.display = 'block';
        }
        function hideError() { document.getElementById('error').style.display = 'none'; }
    </script>
</body>
</html>
"""

# ==================================================
# نقاط النهاية (Routes)
# ==================================================
@app.route('/')
def index():
    print("Serving index page")
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate_video():
    print("Received /generate request")
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'الرجاء إدخال النص'}), 400

    text = data['text']
    use_tts = data.get('use_tts', True)
    use_elevenlabs = data.get('use_elevenlabs', False)
    elevenlabs_api_key = data.get('elevenlabs_api_key', None)
    avatar_option = data.get('avatar', 'default')
    avatar_path = None if avatar_option == 'none' else DEFAULT_AVATAR_PATH
    bg_color = data.get('bg_color', 'black')
    text_color = data.get('text_color', 'white')
    video_type = data.get('video_type', 'static')

    video_id = str(uuid.uuid4())
    audio_path = os.path.join(OUTPUT_DIR, f'audio_{video_id}.mp3')
    video_path = os.path.join(OUTPUT_DIR, f'video_{video_id}.mp4')

    try:
        if use_tts:
            generate_audio(text, audio_path, use_elevenlabs, elevenlabs_api_key)
            if video_type == 'synced':
                create_video_with_audio(text, audio_path, video_path, avatar_path, bg_color, text_color)
            else:
                duration = float(data.get('duration', 5))
                create_video_from_text(text, video_path, duration, avatar_path, bg_color, text_color)
                # إضافة الصوت إلى الفيديو الثابت
                video_clip = VideoClip.from_file(video_path)
                audio_clip = AudioFileClip(audio_path).with_duration(video_clip.duration)
                final_clip = video_clip.with_audio(audio_clip)
                final_clip.write_videofile(video_path, codec='libx264', audio_codec='aac')
        else:
            duration = float(data.get('duration', 5))
            create_video_from_text(text, video_path, duration, avatar_path, bg_color, text_color)

        video_url = url_for('download_video', filename=os.path.basename(video_path), _external=True)
        return jsonify({'success': True, 'video_url': video_url, 'message': 'تم إنشاء الفيديو بنجاح!'})
    except Exception as e:
        print(f"Error in /generate: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_video(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'الملف غير موجود'}), 404

@app.route('/cleanup', methods=['POST'])
def cleanup():
    now = time.time()
    deleted_count = 0
    for filename in os.listdir(OUTPUT_DIR):
        file_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > 3600:
            os.remove(file_path)
            deleted_count += 1
    return jsonify({'message': f'تم حذف {deleted_count} ملف قديم'})

# ==================================================
# تشغيل الخادم (مع منفذ ثابت وطباعة تأكيد)
# ==================================================
if __name__ == '__main__':
    # استخدام المنفذ 10000 مباشرة (كما تطلبه Render)
    port = 10000
    # أو يمكن قراءته من متغير البيئة PORT إذا وُجد
    if 'PORT' in os.environ:
        port = int(os.environ['PORT'])
    
    print(f"Starting Flask server on 0.0.0.0:{port}")
    print(f"Open http://localhost:{port} in your browser")
    
    # Run with debug=False and use_reloader=False لتجنب مشاكل المنافذ
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
