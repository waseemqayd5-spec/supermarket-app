import os
import uuid
import time
from flask import Flask, request, jsonify, send_file, render_template_string

# --- 1. 导入必要的库 ---
try:
    from moviepy import VideoClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
    from gtts import gTTS
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
except ImportError as e:
    print(f"启动失败，缺少必要库: {e}")
    print("请确保运行了安装命令: apt-get update && apt-get install -y ffmpeg && pip install flask gTTS moviepy Pillow")
    exit(1)

# --- 2. 初始化 Flask 应用 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# 创建必要的文件夹
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'static', 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 3. 核心视频生成函数 ---
def create_text_animation_video(text, output_path, duration=10, bg_color='#2c3e50', text_color='white'):
    """
    使用 MoviePy 创建带有文字动画的视频
    """
    # 视频参数
    w, h = 1280, 720  # 16:9 高清分辨率
    fps = 24

    # 1. 生成音频 (Text-to-Speech)
    audio_path = output_path.replace('.mp4', '_audio.mp3')
    tts = gTTS(text=text, lang='ar')  # 使用阿拉伯语，可修改为 'en', 'zh-cn' 等
    tts.save(audio_path)
    audio_clip = AudioFileClip(audio_path)
    final_duration = max(duration, audio_clip.duration)  # 确保视频时长至少和音频一样长

    # 2. 创建动态字幕 (水平滚动动画)
    # 使用 lambda 函数定义文字位置，实现从右向左的滚动效果
    text_clip = (TextClip(font="Arial", text=text, font_size=70, color=text_color,
                          bg_color=(0,0,0,0.6), size=(w*2, None), method='caption', text_align='center')
                 .with_position(lambda t: (max(0, w - int(w * t / final_duration)), h/2))
                 .with_duration(final_duration))

    # 3. 创建背景 (纯色背景 + 简单光晕效果)
    # 创建一个渐变背景，使其更有质感
    bg_clip = ColorClip(size=(w, h), color=bg_color, duration=final_duration)
    # 添加一个简单的光晕效果：创建一个半透明的、更大的圆形并缓慢缩放
    glow_size = 300
    glow_center = (w//2, h//2)
    glow_clip = (ColorClip(size=(glow_size, glow_size), color=(255,255,255))
                 .with_opacity(0.1)
                 .with_position(lambda t: (glow_center[0] + 50*np.sin(t), glow_center[1] + 50*np.cos(t)))
                 .with_duration(final_duration))

    # 4. 合成所有元素
    final_clip = CompositeVideoClip([bg_clip, glow_clip, text_clip])
    final_clip = final_clip.with_audio(audio_clip)

    # 5. 输出视频文件
    final_clip.write_videofile(output_path, fps=fps, codec='libx264', audio_codec='aac', threads=4)

    # 清理临时音频文件
    if os.path.exists(audio_path):
        os.remove(audio_path)

    return output_path

# --- 4. 网页前端 (HTML + CSS + JS) ---
# 为了单文件部署，我们将 HTML 代码内嵌在 Python 字符串中
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>AI 文本转视频 - 一键生成短视频</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 32px;
            box-shadow: 0 25px 45px -12px rgba(0,0,0,0.3);
            max-width: 800px;
            width: 100%;
            padding: 2rem;
            transition: all 0.3s ease;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }
        .sub {
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
            border-bottom: 1px solid #eee;
            padding-bottom: 1rem;
        }
        textarea {
            width: 100%;
            padding: 15px;
            font-size: 1rem;
            border: 2px solid #e0e0e0;
            border-radius: 24px;
            font-family: inherit;
            resize: vertical;
            transition: border-color 0.2s;
        }
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .row {
            display: flex;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        .form-group {
            flex: 1;
            min-width: 150px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #444;
        }
        select, input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 24px;
            font-size: 0.95rem;
            background: white;
            cursor: pointer;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px 28px;
            font-size: 1.1rem;
            font-weight: bold;
            border-radius: 40px;
            width: 100%;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 10px;
        }
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px -5px rgba(102, 126, 234, 0.5);
        }
        button:disabled {
            background: #aaa;
            cursor: not-allowed;
        }
        .loading {
            display: none;
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 32px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .result {
            display: none;
            margin-top: 30px;
            text-align: center;
        }
        video {
            width: 100%;
            border-radius: 20px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.2);
            margin-top: 15px;
        }
        .error {
            display: none;
            background: #fee2e2;
            color: #b91c1c;
            padding: 15px;
            border-radius: 24px;
            margin-top: 20px;
            text-align: center;
        }
        footer {
            text-align: center;
            margin-top: 30px;
            font-size: 0.8rem;
            color: #aaa;
        }
        @media (max-width: 600px) {
            .card { padding: 1.5rem; }
            .row { flex-direction: column; gap: 15px; }
        }
    </style>
</head>
<body>
<div class="card">
    <h1>✨ AI 文本转视频 ✨</h1>
    <div class="sub">将你的文字，变成带有音乐和动态字幕的短视频</div>

    <div class="form-group">
        <label>📝 输入你的文本内容</label>
        <textarea id="textInput" rows="5" placeholder="例如：欢迎来到AI世界！这是一个由人工智能生成的视频，展示科技与创意的结合。"></textarea>
    </div>

    <div class="row">
        <div class="form-group">
            <label>🎨 背景主题</label>
            <select id="bgColor">
                <option value="#2c3e50">深蓝 (现代)</option>
                <option value="#1a1a2e">暗黑 (酷炫)</option>
                <option value="#ff6b6b">活力红 (热情)</option>
                <option value="#4ecdc4">清新绿 (自然)</option>
            </select>
        </div>
        <div class="form-group">
            <label>🎬 视频时长 (秒)</label>
            <input type="number" id="duration" value="8" min="5" max="30" step="1">
        </div>
    </div>

    <button id="generateBtn">🚀 立即生成视频 🚀</button>

    <div class="loading" id="loading">
        <div class="spinner"></div>
        <p>🤖 AI 正在努力创作中，这可能需要几十秒时间，请稍等...</p>
    </div>

    <div class="result" id="result">
        <h3>✅ 生成成功！</h3>
        <video id="videoPlayer" controls>
            您的浏览器不支持 video 标签。
        </video>
        <a id="downloadLink" href="#" download="ai_video.mp4" style="display: inline-block; margin-top: 15px; background: #10b981; color: white; padding: 10px 20px; border-radius: 30px; text-decoration: none;">⬇️ 下载视频 ⬇️</a>
    </div>

    <div class="error" id="error"></div>
    <footer>⚡ 基于 gTTS + MoviePy | 视频生成后自动保存 | 无需任何 API Key</footer>
</div>

<script>
    const generateBtn = document.getElementById('generateBtn');
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');
    const videoPlayer = document.getElementById('videoPlayer');
    const downloadLink = document.getElementById('downloadLink');

    generateBtn.onclick = async () => {
        const text = document.getElementById('textInput').value.trim();
        if (!text) {
            showError('❌ 请先输入文本内容！');
            return;
        }
        const duration = parseFloat(document.getElementById('duration').value);
        const bgColor = document.getElementById('bgColor').value;

        showLoading(true);
        hideResult();
        hideError();

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, duration: duration, bg_color: bgColor })
            });
            const data = await response.json();
            if (data.success) {
                showResult(data.video_url);
            } else {
                showError(data.error || '生成失败，请重试。');
            }
        } catch (err) {
            console.error(err);
            showError('网络错误，无法连接到服务器。');
        } finally {
            showLoading(false);
        }
    };

    function showLoading(show) {
        loadingDiv.style.display = show ? 'block' : 'none';
        generateBtn.disabled = show;
    }
    function showResult(videoUrl) {
        videoPlayer.src = videoUrl;
        downloadLink.href = videoUrl;
        resultDiv.style.display = 'block';
    }
    function hideResult() { resultDiv.style.display = 'none'; }
    function showError(msg) {
        errorDiv.innerText = msg;
        errorDiv.style.display = 'block';
        setTimeout(() => { errorDiv.style.display = 'none'; }, 5000);
    }
    function hideError() { errorDiv.style.display = 'none'; }
</script>
</body>
</html>
"""

# --- 5. Flask 路由与后端逻辑 ---
@app.route('/')
def index():
    """渲染主页面"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate_video():
    """
    处理视频生成请求
    接收 JSON: { "text": "...", "duration": 8, "bg_color": "#2c3e50" }
    返回 JSON: { "success": true, "video_url": "/static/output/xxx.mp4" }
    """
    data = request.get_json()
    if not data or not data.get('text'):
        return jsonify({'error': '缺少文本参数'}), 400

    raw_text = data['text']
    duration = int(data.get('duration', 8))
    bg_color = data.get('bg_color', '#2c3e50')

    # 生成唯一文件名
    video_id = str(uuid.uuid4())
    output_filename = f'video_{video_id}.mp4'
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    try:
        # 调用核心函数创建视频
        create_text_animation_video(
            text=raw_text,
            output_path=output_path,
            duration=duration,
            bg_color=bg_color
        )
        video_url = f'/static/output/{output_filename}'
        return jsonify({'success': True, 'video_url': video_url})
    except Exception as e:
        print(f"视频生成错误: {e}")
        # 如果生成失败，尝试删除可能产生的半成品文件
        if os.path.exists(output_path):
            os.remove(output_path)
        return jsonify({'error': f'视频生成失败: {str(e)}'}), 500

# --- 6. 启动应用 (用于本地调试) ---
if __name__ == '__main__':
    # Render 会自动设置 PORT 环境变量
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
