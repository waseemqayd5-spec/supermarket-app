import os
import uuid 
import time
from flask import Flask, render_template, request, jsonify, send_file, url_for
from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
from moviepy.video.fx import Resize
from gtts import gTTS
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ==============================
# 1. إعداد التطبيق والمجلدات
# ==============================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max limit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
OUTPUT_DIR = os.path.join(STATIC_DIR, 'output')
AVATARS_DIR = os.path.join(STATIC_DIR, 'avatars')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AVATARS_DIR, exist_ok=True)

# إنشاء صورة افتراضية (Avatar) بشكل تلقائي إذا لم تكن موجودة
def create_default_avatar():
    default_path = os.path.join(AVATARS_DIR, 'default.png')
    if not os.path.exists(default_path):
        img = Image.new('RGB', (400, 400), color=(73, 109, 137))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except IOError:
            font = ImageFont.load_default()
        d.text((100, 180), "AI Avatar", fill=(255, 255, 255), font=font)
        img.save(default_path)
    return default_path

DEFAULT_AVATAR_PATH = create_default_avatar()

# ==============================
# 2. دوال مساعدة لإنشاء الفيديو
# ==============================
def generate_audio(text, output_path, use_elevenlabs=False, elevenlabs_api_key=None):
    """
    تحويل النص إلى ملف صوتي.
    إذا تم توفير مفتاح ElevenLabs، يمكن استخدامه للحصول على جودة أفضل.
    """
    if use_elevenlabs and elevenlabs_api_key:
        try:
            from elevenlabs import generate, set_api_key, Voice, VoiceSettings
            set_api_key(elevenlabs_api_key)
            audio_data = generate(
                text=text,
                voice=Voice(
                    voice_id='EXAVITQu4vrTQcpA88OZ',  # voice "Sarah"
                    settings=VoiceSettings(stability=0.35, similarity_boost=0.75)
                )
            )
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            return output_path
        except Exception as e:
            print(f"ElevenLabs error: {e}. Falling back to gTTS.")
            # في حالة الخطأ، نستخدم gTTS كبديل
            pass

    # استخدام gTTS مجاناً
    tts = gTTS(text=text, lang='ar')
    tts.save(output_path)
    return output_path

def create_video_from_text(text, output_path, duration=5, avatar_path=None, bg_color='black', text_color='white'):
    """
    إنشاء فيديو بسيط يعرض النص على خلفية ثابتة مع صورة Avatar اختيارية.
    """
    video_width, video_height = 640, 480
    avatar = avatar_path if avatar_path and os.path.exists(avatar_path) else DEFAULT_AVATAR_PATH

    # خلفية الفيديو
    background_clip = ColorClip(size=(video_width, video_height), color=bg_color, duration=duration)

    # إضافة النص
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

    # إضافة الصورة الرمزية (Avatar) إذا كانت موجودة
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
    return output_path

def create_video_with_audio(text, audio_path, output_path, avatar_path=None, bg_color='black', text_color='white'):
    """
    إنشاء فيديو متكامل مع ملف صوتي من النص، بحيث يتزامن النص المكتوب مع الصوت.
    """
    video_width, video_height = 640, 480
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    avatar = avatar_path if avatar_path and os.path.exists(avatar_path) else DEFAULT_AVATAR_PATH

    background_clip = ColorClip(size=(video_width, video_height), color=bg_color, duration=duration)

    # تقطيع النص إلى أجزاء لمزامنة عرضه مع الصوت (تقريبية)
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
    return output_path

# ==============================
# 3. واجهات الـ API
# ==============================
@app.route('/')
def index():
    """الصفحة الرئيسية للتطبيق"""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_video():
    """
    نقطة النهاية الرئيسية لإنشاء الفيديو.
    تستقبل النص والإعدادات، وتقوم بإنشاء الفيديو ثم إرجاع رابط التحميل.
    """
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
    video_type = data.get('video_type', 'static')  # static or synced

    # إنشاء معرف فريد للفيديو
    video_id = str(uuid.uuid4())
    audio_path = os.path.join(OUTPUT_DIR, f'audio_{video_id}.mp3')
    video_path = os.path.join(OUTPUT_DIR, f'video_{video_id}.mp4')

    try:
        if use_tts:
            # إنشاء الملف الصوتي
            generate_audio(text, audio_path, use_elevenlabs, elevenlabs_api_key)

            if video_type == 'synced':
                create_video_with_audio(text, audio_path, video_path, avatar_path, bg_color, text_color)
            else:
                duration = float(data.get('duration', 5))
                create_video_from_text(text, video_path, duration, avatar_path, bg_color, text_color)
                # إضافة الصوت إلى الفيديو في حالة النوع الثابت
                video_clip = VideoClip.from_file(video_path)
                audio_clip = AudioFileClip(audio_path).with_duration(video_clip.duration)
                final_clip = video_clip.with_audio(audio_clip)
                final_clip.write_videofile(video_path, codec='libx264', audio_codec='aac')
        else:
            # إنشاء فيديو بدون صوت
            duration = float(data.get('duration', 5))
            create_video_from_text(text, video_path, duration, avatar_path, bg_color, text_color)

        # إنشاء رابط التحميل
        video_url = url_for('download_video', filename=os.path.basename(video_path), _external=True)
        return jsonify({
            'success': True,
            'video_url': video_url,
            'message': 'تم إنشاء الفيديو بنجاح!'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_video(filename):
    """تحميل الفيديو المطلوب"""
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'الملف غير موجود'}), 404

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """حذف الفيديوهات والملفات الصوتية القديمة (أكثر من ساعة)"""
    now = time.time()
    deleted_count = 0
    for filename in os.listdir(OUTPUT_DIR):
        file_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.isfile(file_path):
            if now - os.path.getmtime(file_path) > 3600:
                os.remove(file_path)
                deleted_count += 1
    return jsonify({'message': f'تم حذف {deleted_count} ملف قديم'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
