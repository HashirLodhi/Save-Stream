from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import threading
from io import BytesIO
import subprocess
import logging
import time
import uuid

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
DEFAULT_FORMAT = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
FALLBACK_FORMAT = 'best[ext=mp4]/best'

# Download status tracker
download_status = {
    'progress': 0,
    'status': 'Ready',
    'filename': '',
    'complete': False,
    'data': None,
    'thumbnail': '',
    'title': '',
    'duration': ''
}

def is_ffmpeg_available():
    """Check if FFmpeg is installed by running ffmpeg -version"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def get_video_info(url):
    """Get video information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': info.get('formats', [])
            }
    except Exception as e:
        logging.error(f"Info error: {str(e)}")
        return None

def format_duration(seconds):
    """Convert duration in seconds to HH:MM:SS format"""
    if not seconds:
        return "00:00"
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

def download_video(url):
    download_status.update({
        'progress': 0,
        'status': 'Starting download...',
        'filename': '',
        'complete': False,
        'data': None
    })
    
    use_format = DEFAULT_FORMAT if is_ffmpeg_available() else FALLBACK_FORMAT
    temp_file = f'temp_video_{uuid.uuid4().hex}.mp4'
    
    ydl_opts = {
        'format': use_format,
        'progress_hooks': [progress_hook],
        'outtmpl': temp_file,
        'quiet': True,
        'noplaylist': True,
        'retries': 10,
        'socket_timeout': 30,
        'http_headers': {
            'Range': None,
        },
    }
    
    try:
        logging.info(f"Attempting to download: {url}")
        logging.info(f"Current working directory: {os.getcwd()}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = f"{info['title'].replace('/', '_').replace(':', '_').replace(' ', '_')}.mp4"
            
            if os.path.exists(temp_file):
                with open(temp_file, 'rb') as f:
                    video_buffer = BytesIO(f.read())
                os.remove(temp_file)
                
                download_status.update({
                    'progress': 100,
                    'status': 'Download complete!',
                    'filename': filename,
                    'complete': True,
                    'data': video_buffer.getvalue(),
                    'title': info.get('title', ''),
                    'duration': format_duration(info.get('duration', 0)),
                    'thumbnail': info.get('thumbnail', '')
                })
            else:
                raise Exception("Temporary file not found")
                
    except Exception as e:
        logging.error(f"Download error: {str(e)}")
        download_status.update({
            'status': f'Error: {str(e)}',
            'complete': False
        })

def progress_hook(d):
    if d['status'] == 'downloading':
        try:
            percent = float(d.get('_percent_str', '0').strip('%'))
            speed = d.get('_speed_str', 'Unknown speed').strip()
            eta = d.get('_eta_str', 'Unknown').strip()
            download_status['progress'] = min(percent, 100)
            download_status['status'] = f'Downloading: {percent:.1f}% ({speed}) - ETA: {eta}'
        except ValueError:
            logging.warning("Invalid progress data received")

def base_template(content, active_page):
    """Base template with shared navbar, styles, and footer"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>StreamSave - Video Downloader</title>
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #14b8a6;
                --primary-dark: #0f766e;
                --accent: #a5f3fc;
                --secondary: #4b5563;
                --dark: #0f172a;
                --light: #f8fafc;
            }}
            body {{
                font-family: 'Inter', sans-serif;
                background: linear-gradient(135deg, var(--light) 0%, #e2e8f0 100%);
                color: var(--dark);
                line-height: 1.6;
            }}
            .navbar {{
                background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 1rem;
            }}
            .card {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.4s;
            }}
            .card:hover {{
                transform: translateY(-6px);
                box-shadow: 0 16px 48px rgba(0, 0, 0, 0.2);
            }}
            .btn-primary {{
                background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
                color: white;
                padding: 0.75rem 1.5rem;
                border-radius: 8px;
                font-weight: 600;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            .btn-primary:hover {{
                background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
                transform: scale(1.05);
                box-shadow: 0 8px 24px rgba(20, 184, 166, 0.4);
            }}
            .btn-download {{
                background: linear-gradient(135deg, #22c55e 0%, #15803d 100%);
                color: white;
                padding: 0.75rem 1.5rem;
                border-radius: 8px;
                font-weight: 600;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            .btn-download:hover {{
                background: linear-gradient(135deg, #16a34a 0%, #14532d 100%);
                transform: scale(1.05);
                box-shadow: 0 8px 24px rgba(34, 197, 94, 0.4);
            }}
            .progress-container {{
                height: 10px;
                background: #e2e8f0;
                border-radius: 5px;
                overflow: hidden;
            }}
            .progress-bar {{
                height: 100%;
                background: linear-gradient(90deg, var(--primary) 0%, var(--accent) 100%);
                transition: width 0.5s ease-in-out;
            }}
            .video-preview {{
                border-radius: 12px;
                overflow: hidden;
                position: relative;
                background: #e2e8f0;
            }}
            .video-preview::before {{
                content: '';
                display: block;
                padding-top: 56.25%;
            }}
            .video-preview img {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: opacity 0.3s ease;
            }}
            .play-icon {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 60px;
                height: 60px;
                background: rgba(255, 255, 255, 0.9);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: var(--primary);
                font-size: 24px;
                transition: transform 0.3s ease, opacity 0.3s;
            }}
            .play-icon:hover {{
                transform: translate(-50%, -50%) scale(1.15);
                opacity: 0.9;
            }}
            .feature-icon {{
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, rgba(20, 184, 166, 0.1) 0%, rgba(165, 243, 252, 0.1) 100%);
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: var(--primary);
                font-size: 24px;
                margin-bottom: 1rem;
                transition: transform 0.3s ease;
            }}
            .feature-card:hover .feature-icon {{
                transform: scale(1.1) rotate(10deg);
            }}
            .animate-pulse {{
                animation: pulse 1.5s infinite;
            }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.6; }}
                100% {{ opacity: 1; }}
            }}
            .tooltip {{
                position: relative;
                display: inline-block;
            }}
            .tooltip .tooltiptext {{
                visibility: hidden;
                width: 200px;
                background: var(--dark);
                color: white;
                text-align: center;
                border-radius: 8px;
                padding: 8px;
                position: absolute;
                z-index: 10;
                bottom: 130%;
                left: 50%;
                transform: translateX(-50%) translateY(10px);
                opacity: 0;
                transition: opacity 0.3s, transform 0.3s;
                font-size: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            }}
            .tooltip:hover .tooltiptext {{
                visibility: visible;
                opacity: 1;
                transform: translateX(-50%) translateY(0);
            }}
            .footer {{
                background: linear-gradient(135deg, var(--dark) 0%, #1e293b 100%);
            }}
            .nav-link {{
                position: relative;
                transition: color 0.3s ease;
            }}
            .nav-link.active {{
                color: var(--accent);
                font-weight: 700;
            }}
            .nav-link::after {{
                content: '';
                position: absolute;
                width: 0;
                height: 2px;
                bottom: -2px;
                left: 0;
                background-color: var(--accent);
                transition: width 0.3s ease;
            }}
            .nav-link:hover::after {{
                width: 100%;
            }}
            input::placeholder {{
                color: var(--secondary);
                opacity: 0.7;
            }}
            h2, h3, h4 {{
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            }}
            .accordion-toggle {{
                display: none;
            }}
            .accordion-content {{
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.3s ease-out;
            }}
            .accordion-toggle:checked ~ .accordion-content {{
                max-height: 500px;
            }}
            .accordion-label {{
                cursor: pointer;
                display: block;
                padding: 1rem;
                background: #f1f5f9;
                border-radius: 8px;
                transition: background 0.3s;
            }}
            .accordion-label:hover {{
                background: #e2e8f0;
            }}
            @media (max-width: 640px) {{
                .container {{
                    padding: 0.5rem;
                }}
                .btn-primary, .btn-download {{
                    width: 100%;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body class="min-h-screen">
        <!-- Navigation -->
        <nav class="navbar text-white py-4 px-6 sticky top-0 z-50">
            <div class="container mx-auto flex justify-between items-center">
                <div class="flex items-center space-x-3">
                    <i class="fas fa-download text-2xl"></i>
                    <h1 class="text-2xl font-bold tracking-tight">StreamSave</h1>
                </div>
                <div class="flex items-center space-x-6">
                    <a href="/" class="nav-link text-sm font-medium {'active' if active_page == 'home' else ''}">Home</a>
                    <a href="/features" class="nav-link text-sm font-medium {'active' if active_page == 'features' else ''}">Features</a>
                    <a href="/faq" class="nav-link text-sm font-medium {'active' if active_page == 'faq' else ''}">FAQ</a>
                </div>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="py-12 px-4">
            <div class="container mx-auto">
                {content}
            </div>
        </main>

        <!-- Footer -->
        <footer class="footer text-white py-12">
            <div class="container mx-auto px-6">
                <div class="flex flex-col md:flex-row justify-between items-center">
                    <div class="mb-6 md:mb-0 text-center md:text-left">
                        <h2 class="text-2xl font-bold flex items-center">
                            <i class="fas fa-download mr-2"></i> StreamSave
                        </h2>
                        <p class="text-gray-400 mt-2">© 2025 StreamSave. All Rights Reserved.</p>
                    </div>
                </div>
            </div>
        </footer>
    </body>
    </html>
    """

@app.route('/')
def home():
    content = """
    <!-- Hero Section -->
    <section class="text-center mb-16">
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900 mb-4 tracking-tight">Download Any Video in Seconds</h2>
        <p class="text-lg text-secondary max-w-2xl mx-auto">Experience fast, secure, and high-quality video downloads with StreamSave. Save your favorite videos in MP4 and more.</p>
    </section>

    <!-- Download Card -->
    <section class="mb-16">
        <div class="card p-8">
            <h3 class="text-2xl font-semibold mb-6 text-gray-900">Enter Video URL</h3>
            
            <div class="flex flex-col md:flex-row gap-4 mb-8">
                <input 
                    type="text" 
                    id="videoUrl" 
                    class="flex-grow p-4 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary shadow-sm" 
                    placeholder="Paste any video link here (e.g., https://www.youtube.com/watch?v=...)"
                >
                <button 
                    id="downloadBtn" 
                    class="btn-primary"
                >
                    <i class="fas fa-download mr-2"></i>Download
                </button>
            </div>
            
            <!-- Video Info Preview -->
            <div id="videoPreview" class="hidden mb-8">
                <div class="flex flex-col md:flex-row gap-6">
                    <div class="video-preview md:w-1/3">
                        <img id="videoThumbnail" src="" alt="Video thumbnail">
                        <div class="play-icon">
                            <i class="fas fa-play"></i>
                        </div>
                    </div>
                    <div class="md:w-2/3">
                        <h4 id="videoTitle" class="text-xl font-semibold mb-2 text-gray-900"></h4>
                        <p id="videoDuration" class="text-secondary mb-4"></p>
                        <div class="flex items-center space-x-4">
                            <div class="tooltip">
                                <span class="px-3 py-1 bg-teal-100 text-teal-800 rounded-full text-sm font-medium">
                                    <i class="fas fa-hd mr-1"></i> HD
                                </span>
                                <span class="tooltiptext">High Quality Video (720p-1080p)</span>
                            </div>
                            <div class="tooltip">
                                <span class="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                                    <i class="fas fa-bolt mr-1"></i> Fast
                                </span>
                                <span class="tooltiptext">Lightning-Fast Download Speeds</span>
                            </div>
                            <div class="tooltip">
                                <span class="px-3 py-1 bg-cyan-100 text-cyan-800 rounded-full text-sm font-medium">
                                    <i class="fas fa-shield-alt mr-1"></i> Secure
                                </span>
                                <span class="tooltiptext">Safe & Ad-Free Downloads</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Progress Section -->
            <div id="progressSection" class="hidden">
                <div class="mb-4 flex justify-between items-center">
                    <span id="status" class="font-medium text-gray-700"></span>
                    <span id="progressPercent" class="font-medium text-gray-700">0%</span>
                </div>
                <div class="progress-container mb-4">
                    <div id="progressBar" class="progress-bar" style="width: 0%"></div>
                </div>
                
                <div class="flex justify-between text-sm text-secondary">
                    <span id="speedInfo">Speed: --</span>
                    <span id="etaInfo">ETA: --</span>
                </div>
            </div>
            
            <!-- Download Complete Section -->
            <div id="completeSection" class="hidden text-center mt-8">
                <div class="mb-6">
                    <i class="fas fa-check-circle text-green-500 text-5xl mb-4 animate-pulse"></i>
                    <h4 class="text-2xl font-semibold mb-2 text-gray-900">Download Complete!</h4>
                    <p class="text-secondary mb-4">Your video is ready to save.</p>
                </div>
                <a 
                    id="downloadLink" 
                    class="btn-download inline-block"
                >
                    <i class="fas fa-file-download mr-2"></i>Save Video
                </a>
            </div>
        </div>
    </section>
    
    <!-- Features Section -->
    <section class="mb-16">
        <h3 class="text-3xl font-semibold mb-8 text-center text-gray-900">Why Choose StreamSave?</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="card p-6 text-center feature-card">
                <div class="feature-icon mx-auto">
                    <i class="fas fa-tachometer-alt"></i>
                </div>
                <h4 class="text-xl font-semibold mb-2 text-gray-900">Blazing Fast</h4>
                <p class="text-secondary">Download videos at lightning speed with our optimized servers.</p>
            </div>
            <div class="card p-6 text-center feature-card">
                <div class="feature-icon mx-auto">
                    <i class="fas fa-film"></i>
                </div>
                <h4 class="text-xl font-semibold mb-2 text-gray-900">Multiple Formats</h4>
                <p class="text-secondary">Choose from MP4, MP3, WEBM, and more for your downloads.</p>
            </div>
            <div class="card p-6 text-center feature-card">
                <div class="feature-icon mx-auto">
                    <i class="fas fa-lock"></i>
                </div>
                <h4 class="text-xl font-semibold mb-2 text-gray-900">Secure & Private</h4>
                <p class="text-secondary">100% safe downloads with no ads or registration required.</p>
            </div>
        </div>
    </section>
    
    <!-- How To Section -->
    <section class="mb-16">
        <h3 class="text-3xl font-semibold mb-8 text-center text-gray-900">How It Works</h3>
        <div class="card p-8">
            <ol class="list-decimal list-inside space-y-4 text-secondary">
                <li class="font-medium">Copy the URL of your desired video.</li>
                <li class="font-medium">Paste the URL into the input field above.</li>
                <li class="font-medium">Click the "Download" button to start processing.</li>
                <li class="font-medium">Click "Save Video" once the download is ready.</li>
            </ol>
        </div>
    </section>

    <script>
        const videoUrl = document.getElementById('videoUrl');
        const downloadBtn = document.getElementById('downloadBtn');
        const status = document.getElementById('status');
        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const speedInfo = document.getElementById('speedInfo');
        const etaInfo = document.getElementById('etaInfo');
        const downloadLink = document.getElementById('downloadLink');
        const videoPreview = document.getElementById('videoPreview');
        const videoThumbnail = document.getElementById('videoThumbnail');
        const videoTitle = document.getElementById('videoTitle');
        const videoDuration = document.getElementById('videoDuration');
        const progressSection = document.getElementById('progressSection');
        const completeSection = document.getElementById('completeSection');
        
        let checkInterval;
        let videoInfo = null;
        
        function debounce(func, wait) {
            let timeout;
            return function() {
                const context = this, args = arguments;
                clearTimeout(timeout);
                timeout = setTimeout(() => func.apply(context, args), wait);
            };
        }
        
        videoUrl.addEventListener('input', debounce(async function() {
            const url = videoUrl.value.trim();
            
            if (!url) {
                videoPreview.classList.add('hidden');
                return;
            }
            
            try {
                const response = await fetch('/check_url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                
                if (!response.ok) throw new Error('Invalid URL');
                
                const data = await response.json();
                
                if (data.valid) {
                    videoInfo = data.info;
                    videoThumbnail.src = data.info.thumbnail;
                    videoTitle.textContent = data.info.title;
                    videoDuration.textContent = `Duration: ${data.info.duration}`;
                    videoPreview.classList.remove('hidden');
                } else {
                    videoPreview.classList.add('hidden');
                    showStatus('Invalid URL', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                videoPreview.classList.add('hidden');
                showStatus('Error validating URL', 'error');
            }
        }, 1000));
        
        downloadBtn.addEventListener('click', startDownload);
        
        async function startDownload() {
            const url = videoUrl.value.trim();
            
            if (!url) {
                showStatus('Please enter a valid URL', 'error');
                return;
            }
            
            try {
                downloadBtn.disabled = true;
                downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processing...';
                progressSection.classList.remove('hidden');
                completeSection.classList.add('hidden');
                videoPreview.classList.add('hidden');
                
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                
                if (!response.ok) throw new Error('Failed to start download');
                
                checkInterval = setInterval(checkProgress, 2000);
            } catch (error) {
                showStatus(`Error: ${error.message}`, 'error');
                resetDownloadButton();
            }
        }
        
        async function checkProgress() {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                
                progressBar.style.width = `${data.progress}%`;
                progressPercent.textContent = `${Math.round(data.progress)}%`;
                
                const statusParts = data.status.split(' - ');
                if (statusParts.length > 1) {
                    const speedMatch = statusParts[0].match(/\((.*)\)/);
                    const etaMatch = statusParts[1].match(/ETA: (.*)/);
                    
                    if (speedMatch) speedInfo.textContent = `Speed: ${speedMatch[1]}`;
                    if (etaMatch) etaInfo.textContent = `ETA: ${etaMatch[1]}`;
                }
                
                showStatus(data.status.split(' - ')[0], 'info');
                
                if (data.complete || data.status.startsWith('Error')) {
                    clearInterval(checkInterval);
                    resetDownloadButton();
                    progressSection.classList.add('hidden');
                    
                    if (data.complete) {
                        completeSection.classList.remove('hidden');
                        if (data.filename) {
                            downloadLink.href = `/get_video`;
                            downloadLink.download = data.filename;
                        }
                    } else {
                        showStatus(data.status, 'error');
                    }
                }
            } catch (error) {
                console.error('Error:', error);
                clearInterval(checkInterval);
                showStatus('Error checking status', 'error');
                resetDownloadButton();
            }
        }
        
        function resetDownloadButton() {
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = '<i class="fas fa-download mr-2"></i>Download';
        }
        
        function showStatus(message, type) {
            status.textContent = message;
            status.className = 'font-medium';
            
            if (type === 'error') {
                status.classList.add('text-red-600');
            } else if (type === 'success') {
                status.classList.add('text-green-600');
            } else {
                status.classList.add('text-teal-600');
            }
        }
    </script>
    """
    return base_template(content, 'home')

@app.route('/features')
def features():
    content = """
    <!-- Hero Section -->
    <section class="text-center mb-16">
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900 mb-4 tracking-tight">Explore StreamSave Features</h2>
        <p class="text-lg text-secondary max-w-2xl mx-auto">Discover the powerful capabilities that make StreamSave the ultimate video downloader.</p>
    </section>

    <!-- Features Section -->
    <section class="mb-16">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="card p-6 text-center feature-card">
                <div class="feature-icon mx-auto">
                    <i class="fas fa-tachometer-alt"></i>
                </div>
                <h4 class="text-xl font-semibold mb-2 text-gray-900">High-Speed Downloads</h4>
                <p class="text-secondary">Leverage our optimized servers to download videos in seconds, even for large files.</p>
            </div>
            <div class="card p-6 text-center feature-card">
                <div class="feature-icon mx-auto">
                    <i class="fas fa-film"></i>
                </div>
                <h4 class="text-xl font-semibold mb-2 text-gray-900">Versatile Formats</h4>
                <p class="text-secondary">Support for MP4, MP3, WEBM, and more, ensuring compatibility with all your devices.</p>
            </div>
            <div class="card p-6 text-center feature-card">
                <div class="feature-icon mx-auto">
                    <i class="fas fa-shield-alt"></i>
                </div>
                <h4 class="text-xl font-semibold mb-2 text-gray-900">Secure & Ad-Free</h4>
                <p class="text-secondary">Enjoy a safe downloading experience with no ads, malware, or registration required.</p>
            </div>
        </div>
    </section>

    <!-- Call to Action -->
    <section class="text-center">
        <h3 class="text-3xl font-semibold mb-6 text-gray-900">Ready to Download?</h3>
        <a href="/" class="btn-primary inline-block">
            <i class="fas fa-download mr-2"></i>Start Downloading Now
        </a>
    </section>
    """
    return base_template(content, 'features')

@app.route('/faq')
def faq():
    content = """
    <!-- Hero Section -->
    <section class="text-center mb-16">
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900 mb-4 tracking-tight">Frequently Asked Questions</h2>
        <p class="text-lg text-secondary max-w-2xl mx-auto">Find answers to common questions about using StreamSave for video downloads.</p>
    </section>

    <!-- FAQ Section -->
    <section class="mb-16">
        <div class="card p-8">
            <div class="space-y-4">
                <div>
                    <input type="checkbox" id="faq1" class="accordion-toggle hidden">
                    <label for="faq1" class="accordion-label font-medium text-gray-900">
                        Is StreamSave free to use?
                    </label>
                    <div class="accordion-content text-secondary px-4 pb-4">
                        <p>Yes, StreamSave is completely free to use with no hidden fees or subscriptions required.</p>
                    </div>
                </div>
                <div>
                    <input type="checkbox" id="faq2" class="accordion-toggle hidden">
                    <label for="faq2" class="accordion-label font-medium text-gray-900">
                        What video formats are supported?
                    </label>
                    <div class="accordion-content text-secondary px-4 pb-4">
                        <p>StreamSave supports multiple formats including MP4, MP3, WEBM, and more, depending on the source video.</p>
                    </div>
                </div>
                <div>
                    <input type="checkbox" id="faq3" class="accordion-toggle hidden">
                    <label for="faq3" class="accordion-label font-medium text-gray-900">
                        Is it safe to download videos with StreamSave?
                    </label>
                    <div class="accordion-content text-secondary px-4 pb-4">
                        <p>Absolutely, StreamSave ensures a secure, ad-free experience with no malware or data collection.</p>
                    </div>
                </div>
                <div>
                    <input type="checkbox" id="faq4" class="accordion-toggle hidden">
                    <label for="faq4" class="accordion-label font-medium text-gray-900">
                        Can I download videos from platforms other than YouTube?
                    </label>
                    <div class="accordion-content text-secondary px-4 pb-4">
                        <p>StreamSave supports various platforms, provided the video URL is accessible and compatible with our downloader.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>
    """
    return base_template(content, 'faq')

@app.route('/check_url', methods=['POST'])
def check_url():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'valid': False, 'error': 'URL is required'}), 400
    
    try:
        info = get_video_info(url)
        if info:
            return jsonify({
                'valid': True,
                'info': {
                    'title': info['title'],
                    'thumbnail': info['thumbnail'],
                    'duration': format_duration(info['duration'])
                }
            })
        return jsonify({'valid': False, 'error': 'Unable to fetch video info'}), 400
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return jsonify({'valid': False, 'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def start_download():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    thread = threading.Thread(target=download_video, args=(url,))
    thread.start()
    
    return jsonify({'message': 'Download started'}), 200

@app.route('/status')
def get_status():
    status = {
        'progress': download_status['progress'],
        'status': download_status['status'],
        'filename': download_status['filename'],
        'complete': download_status['complete'],
        'thumbnail': download_status['thumbnail'],
        'title': download_status['title'],
        'duration': download_status['duration']
    }
    return jsonify(status)

@app.route('/get_video')
def get_video():
    if not download_status['complete'] or not download_status['data']:
        return jsonify({'error': 'Video not ready'}), 404
    
    return send_file(
        BytesIO(download_status['data']),
        mimetype='video/mp4',
        as_attachment=True,
        download_name=download_status['filename']
    )

if __name__ == '__main__':
    ffmpeg_status = "available" if is_ffmpeg_available() else "not available"
    logging.info(f"FFmpeg is {ffmpeg_status}. Using {'advanced' if ffmpeg_status == 'available' else 'simple'} download mode.")
    app.run(debug=True, port=5000)
