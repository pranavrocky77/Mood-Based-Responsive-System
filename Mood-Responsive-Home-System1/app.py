from flask import Flask, render_template, Response, request, jsonify, redirect, url_for
import cv2
import random
import time
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import serial
from deepface import DeepFace
import speech_recognition as sr
import yt_dlp
import pygame
import os
import datetime
import google.generativeai as genai  # Import the Gemini AI library

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # For session management

# Replace with your Gemini AI API key
GOOGLE_API_KEY = "AIzaSyBIbAIRmuY_BneISer7IL-2rnOvtnQXUgY"
genai.configure(api_key=GOOGLE_API_KEY)

# --- Database Setup ---
DATABASE = "users.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Gemini AI Chatbot ---
def chatbot_reply(message):
    try:
        model = genai.GenerativeModel('gemini-pro')  # Or 'gemini-1.5-pro'
        response = model.generate_content(message) #Prompt the model
        return response.text  # Extract the text response
    except Exception as e:
        print(f"Gemini AI Error: {e}")
        return "Sorry, I'm having trouble connecting to the AI. Please try again later."

# --- Arduino Communication ---
SERIAL_PORT = "COM5"
BAUD_RATE = 9600
arduino = None
try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"Connected to Arduino on {SERIAL_PORT}")
except serial.SerialException as e:
    print(f"Error: Could not connect to {SERIAL_PORT}: {e}")

# --- Camera ---
camera = cv2.VideoCapture(0)

# --- Mood Detection ---
mood_log = []
current_mood = "neutral"

def detect_mood():
    global current_mood
    emotions_detected = []
    start_time = time.time()
    while time.time() - start_time < 3:
        success, frame = camera.read()
        if not success:
            break
        try:
            result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            if result and isinstance(result, list):
                mood = result[0]['dominant_emotion']
                emotions_detected.append(mood)
        except Exception as e:
            print(f"DeepFace Error: {e}")
    if emotions_detected:
        most_common_mood = max(set(emotions_detected), key=emotions_detected.count)
        current_mood = most_common_mood
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        mood_log.append({"time": timestamp, "mood": current_mood})
        print(f"Final Mood (3 sec avg): {current_mood} at {timestamp}")
        return current_mood
    else:
        print("No face detected consistently.")
        return "neutral"

# --- YouTube Music ---
pygame.init()
pygame.mixer.init()
music_playing = False

def play_music_from_youtube(query):
    global music_playing
    pygame.mixer.quit()
    pygame.mixer.init()
    if os.path.exists("music.mp3"):
        try:
            os.remove("music.mp3")
            print("Old music file deleted.")
        except Exception as e:
            print(f"Error deleting old music file: {e}")
            return "Error deleting previous file."
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'extractaudio': True,
        'outtmpl': 'music.%(ext)s',
        'ffmpeg_location': r'C:\ffmpeg\ffmpeg-2025-02-06-git-6da82b4485-full_build\bin',  # Corrected: Use raw string
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_query = f"ytsearch:{query} audio"
        try:
            info = ydl.extract_info(search_query, download=True)
            if 'entries' in info and len(info['entries']) > 0:
                video_title = info['entries'][0]['title']
                downloaded_files = [f for f in os.listdir() if f.endswith('.mp3')]
                if not downloaded_files:
                    print("Download failed: No music file found.")
                    return "Download failed."
                os.rename(downloaded_files[0], 'music.mp3')
                time.sleep(1)
                pygame.mixer.init()
                pygame.mixer.music.load('music.mp3')
                pygame.mixer.music.play()
                music_playing = True
                print(f"Now Playing: {video_title}")
                return f"Now Playing: {video_title}"
            else:
                return "No music found."
        except Exception as e:
            print(f"Error: {e}")
            return "Music search failed."

def stop_music():
    global music_playing
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        pygame.mixer.init()
    time.sleep(1)
    def force_delete(file_path):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print("Music file deleted successfully.")
            except Exception as e:
                print(f"Error deleting music file: {e}")
    force_delete("music.mp3")
    music_playing = False
    return "Music stopped."

# --- Flask Routes ---
@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.json.get("username")
        email = request.json.get("email")
        password = request.json.get("password")
        if not username or not email or not password:
            return jsonify({"message": "All fields are required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                           (username, email, hashed_password))
            conn.commit()
            return jsonify({"message": "Signup successful!"}), 201
        except sqlite3.IntegrityError:
            return jsonify({"message": "Username or email already exists."}), 409
        finally:
            conn.close()

    return render_template("2signup.html")  # Serve the signup form

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.json.get("username")
        password = request.json.get("password")

        if not username or not password:
            return jsonify({"message": "Username and password are required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            return jsonify({"message": "Login successful!", "redirect": "/main"}), 200
        else:
            return jsonify({"message": "Invalid username or password."}), 401

    return render_template("2signup.html")  # Serve the login form

@app.route('/main')
def main_page():
    return render_template("main.html")

@app.route('/chatbot')
def chatbot_page():
    return render_template('chatbot.html')

@app.route('/')
def index():
    return render_template("1index.html")

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    user_message = data.get("message")
    if user_message:
        response = chatbot_reply(user_message)
        return jsonify({"response": response})
    return jsonify({"response": "Please send a valid message."})

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/change_light', methods=['POST'])
def change_light():
    global current_mood
    current_mood = detect_mood()
    mood_to_color = {
        "happy": "G",
        "sad": "B",
        "angry": "R",
        "surprise": "B",
        "fear": "R",
        "disgust": "G",
        "neutral": "W"
    }
    color_code = mood_to_color.get(current_mood, "W")

    if arduino:
        try:
            arduino.write(color_code.encode())
            print(f"Sent color: {color_code} for mood: {current_mood}")
            return jsonify({"mood": current_mood, "color": color_code})
        except serial.SerialException as e:
            print(f"Error writing to Arduino: {e}")
            return jsonify({"error": f"Arduino communication error: {e}"})

    return jsonify({"error": "Arduino not connected"})

@app.route('/get_mood_log', methods=['GET'])
def get_mood_log():
    return jsonify(mood_log)

@app.route('/normal_light', methods=['POST'])
def normal_light():
    global current_mood
    current_mood = "neutral"
    if arduino:
        try:
            arduino.write(b'W')
            return jsonify({"message": "Light reset to normal"})
        except serial.SerialException as e:
            print(f"Error writing to Arduino: {e}")
            return jsonify({"error": f"Arduino communication error: {e}"})
    return jsonify({"error": "Arduino not connected"})

@app.route('/close_cam', methods=['POST'])
def close_cam():
    global camera
    if camera.isOpened():
        camera.release()
        print("Webcam Closed")
    return jsonify({"message": "Webcam closed"})

@app.route('/open_cam', methods=['POST'])
def open_cam():
    global camera
    if not camera.isOpened():
        camera.open(0)
        print("Webcam Opened")
    return jsonify({"message": "Webcam opened"})

@app.route('/play_music', methods=['POST'])
def play_music():
    query = "relaxing music"  # Example query
    result = play_music_from_youtube(query)
    return jsonify({"message": result})

def generate_frames():
    while True:
        if not camera.isOpened():
            time.sleep(0.5)
            continue
        success, frame = camera.read()
        if not success:
            break

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"Mood: {current_mood}", (50, 50), font, 1, (0, 255, 0), 2, cv2.LINE_AA)
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)