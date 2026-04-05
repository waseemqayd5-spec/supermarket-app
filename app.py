import os
import sys
import uuid
from flask import Flask, request, jsonify, send_file, render_template_string, url_for

# ==================================================
# استيراد المكتبات
# ==================================================
try:
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip, ImageClip
except:
    print("ثبت المكتبة: pip install moviepy")
    sys.exit()

try:
    from gtts import gTTS
except:
    print("ثبت المكتبة: pip install gtts")
    sys.exit()

try:
    from PIL import Image, ImageDraw, ImageFont
except:
    print("ثبت المكتبة: pip install pillow")
    sys.exit()

# ==================================================
# إعداد Flask
# ==================================================
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUT_DIR = os.path.join(STATIC_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==================================================
# تحويل النص إلى صوت
# ==================================================
def generate_audio(text, path):
    tts = gTTS(text=text, lang="ar")
    tts.save(path)
    return path

# ==================================================
# إنشاء فيديو بسيط
# ==================================================
def create_video(text, video_path, audio_path=None):

    width = 1280
    height = 720
    duration = 6

    background = ColorClip(size=(width, height), color=(0,0,0), duration=duration)

    text_clip = TextClip(
        text,
        fontsize=60,
        color="white",
        method="caption",
        size=(width-200,None),
        align="center"
    ).set_position("center").set_duration(duration)

    final = CompositeVideoClip([background, text_clip])

    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path)
        final = final.set_audio(audio)

    final.write_videofile(video_path, fps=24, codec="libx264", audio_codec="aac")

# ==================================================
# واجهة الموقع
# ==================================================
HTML = """
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>تحويل النص إلى فيديو</title>
<style>
body{
font-family:Arial;
background:#111;
color:white;
text-align:center;
padding:40px
}

textarea{
width:90%;
height:150px;
font-size:18px;
padding:10px
}

button{
padding:15px 30px;
font-size:20px;
margin-top:20px;
background:#4CAF50;
border:none;
color:white;
cursor:pointer
}

video{
margin-top:30px;
width:80%
}
</style>
</head>

<body>

<h1>🎬 تحويل النص إلى فيديو</h1>

<textarea id="text" placeholder="اكتب كلمات الأغنية هنا"></textarea>

<br>

<button onclick="makeVideo()">إنشاء الفيديو</button>

<div id="result"></div>

<script>

async function makeVideo(){

let text=document.getElementById("text").value

let res=await fetch("/generate",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({text:text})
})

let data=await res.json()

if(data.success){

document.getElementById("result").innerHTML=
`
<p>تم إنشاء الفيديو</p>
<a href="${data.url}" download>تحميل الفيديو</a>
<br>
<video controls src="${data.url}"></video>
`

}else{

alert(data.error)

}

}

</script>

</body>
</html>
"""

# ==================================================
# الصفحة الرئيسية
# ==================================================
@app.route("/")
def index():
    return render_template_string(HTML)

# ==================================================
# توليد الفيديو
# ==================================================
@app.route("/generate", methods=["POST"])
def generate():

    data = request.get_json()
    text = data.get("text")

    if not text:
        return jsonify({"error":"اكتب النص"}),400

    video_id = str(uuid.uuid4())

    video_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")
    audio_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp3")

    try:

        generate_audio(text,audio_path)

        create_video(text,video_path,audio_path)

        url = url_for("download", filename=os.path.basename(video_path))

        return jsonify({
            "success":True,
            "url":url
        })

    except Exception as e:

        return jsonify({"error":str(e)})

# ==================================================
# تحميل الفيديو
# ==================================================
@app.route("/download/<filename>")
def download(filename):

    path = os.path.join(OUTPUT_DIR, filename)

    return send_file(path, as_attachment=True)

# ==================================================
# تشغيل السيرفر
# ==================================================
if __name__ == "__main__":

    print("server running http://127.0.0.1:5000")

    app.run(debug=True)
