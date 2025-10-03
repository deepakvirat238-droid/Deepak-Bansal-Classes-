import streamlit as st
import sqlite3
import pandas as pd
import pdfplumber
import pytesseract
from PIL import Image
import re
import time
import io
import random
import plotly.graph_objects as go
from datetime import datetime, timedelta
import base64
import os

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('selectionway.db', check_same_thread=False)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT)''')
    
    # Courses table
    c.execute('''CREATE TABLE IF NOT EXISTS courses
                 (id INTEGER PRIMARY KEY, name TEXT, description TEXT, materials_count INTEGER, students_count INTEGER)''')
    
    # Enrollments table
    c.execute('''CREATE TABLE IF NOT EXISTS enrollments
                 (user_id INTEGER, course_id INTEGER, enroll_date TEXT, batch_date TEXT, validity_days INTEGER)''')
    
    # Study materials table
    c.execute('''CREATE TABLE IF NOT EXISTS study_materials
                 (id INTEGER PRIMARY KEY, course_id INTEGER, name TEXT, file_type TEXT, upload_date TEXT)''')
    
    # Quiz results table
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_results
                 (id INTEGER PRIMARY KEY, user_id INTEGER, score INTEGER, total_questions INTEGER, time_taken INTEGER, quiz_date TEXT)''')
    
    conn.commit()
    conn.close()

def add_sample_data():
    conn = sqlite3.connect('selectionway.db', check_same_thread=False)
    c = conn.cursor()
    
    # Add sample user
    c.execute("INSERT OR IGNORE INTO users VALUES (1, 'Deepak', 'deepak@example.com', '6388974650')")
    
    # Add sample courses
    courses = [
        (1, 'Current Affairs', 'Daily current affairs updates', 25, 150),
        (2, 'UPSC Pre+Mains', 'Complete UPSC preparation', 150, 89),
        (3, 'Banking Exams', 'Banking and SSC preparation', 80, 45),
        (4, 'General Studies', 'Comprehensive GS material', 120, 200)
    ]
    c.executemany("INSERT OR IGNORE INTO courses VALUES (?, ?, ?, ?, ?)", courses)
    
    # Add sample enrollments
    enrollments = [
        (1, 1, '2024-09-20', '2024-10-03', 730),
        (1, 2, '2024-09-20', '2024-10-03', 730)
    ]
    c.executemany("INSERT OR IGNORE INTO enrollments VALUES (?, ?, ?, ?, ?)", enrollments)
    
    # Add sample study materials
    materials = [
        (1, 1, 'Polity Notes.pdf', 'PDF', '2024-09-20'),
        (2, 1, 'Current Affairs Oct.pdf', 'PDF', '2024-09-25'),
        (3, 2, 'Geography Ebook.pdf', 'PDF', '2024-09-22'),
        (4, 2, 'History Notes.pdf', 'PDF', '2024-09-21'),
        (5, 3, 'Quantitative Aptitude.pdf', 'PDF', '2024-09-20')
    ]
    c.executemany("INSERT OR IGNORE INTO study_materials VALUES (?, ?, ?, ?, ?)", materials)
    
    conn.commit()
    conn.close()

init_db()
add_sample_data()

# ==================== PDF QUIZ FUNCTIONS ====================
def extract_text_from_pdf(pdf_file):
    """Extract text from PDF with OCR support"""
    text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += page_text + "\n"
                else:
                    try:
                        image = page.to_image()
                        img_bytes = io.BytesIO()
                        image.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        ocr_text = pytesseract.image_to_string(Image.open(img_bytes))
                        text += ocr_text + "\n"
                    except:
                        continue
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
    return text

def fast_parse_pdf_content(text):
    """Ultra-fast PDF parsing with optimized regex"""
    questions = []
    raw_questions = re.split(r'(?i)(?:Q|Question\s*)\d+[\.\)\s:-]+', text)
    
    for i, block in enumerate(raw_questions[1:21], 1):  # Limit to 20 questions for speed
        if not block.strip():
            continue
        try:
            question_text = re.split(r'(?i)A\)|Answer:', block)[0].strip()[:300]
            
            options = {}
            for match in re.finditer(r'([A-D])\)\s*([^\n]+)', block):
                options[match.group(1)] = match.group(2).strip()
            
            answer_match = re.search(r'(?i)Answer:\s*([A-D])', block)
            correct_answer = answer_match.group(1) if answer_match else 'A'
            
            questions.append({
                "id": i,
                "question": question_text,
                "options": options or {'A': 'Option A', 'B': 'Option B', 'C': 'Option C', 'D': 'Option D'},
                "correct_answer": correct_answer,
                "difficulty": random.choice(["Easy", "Medium", "Hard"]),
                "time_spent": 0,
                "attempts": 0
            })
        except:
            continue
    
    return questions

def generate_ai_explanation(question, correct_answer, options):
    """Generate AI explanation for questions"""
    explanations = {
        "grammar": "This question tests grammatical rules.",
        "vocabulary": "This vocabulary question requires word understanding.",
        "comprehension": "This tests reading comprehension skills.",
        "logic": "This requires analytical thinking.",
        "general": "This evaluates fundamental knowledge."
    }
    
    question_lower = question.lower()
    if any(word in question_lower for word in ['synonym', 'antonym', 'word', 'meaning']):
        exp_type = "vocabulary"
    elif any(word in question_lower for word in ['tense', 'grammar', 'sentence', 'verb']):
        exp_type = "grammar"
    elif any(word in question_lower for word in ['passage', 'read', 'comprehension']):
        exp_type = "comprehension"
    elif any(word in question_lower for word in ['logic', 'reason', 'deduce', 'infer']):
        exp_type = "logic"
    else:
        exp_type = "general"
    
    return f"""
**AI Analysis:** This is a {exp_type} question.

**Why {correct_answer} is correct:**
- It follows the rules of {exp_type}
- Other options contain common mistakes

**Tip:** Practice more {exp_type} questions.
"""

def autoplay_audio(sound_type):
    """Play sound based on answer correctness"""
    if not st.session_state.get('sound_enabled', True):
        return
        
    if sound_type == "correct":
        sound_file = """
        <audio autoplay>
        <source src="https://assets.mixkit.co/sfx/preview/mixkit-correct-answer-tone-2870.mp3" type="audio/mpeg">
        </audio>
        """
    else:
        sound_file = """
        <audio autoplay>
        <source src="https://assets.mixkit.co/sfx/preview/mixkit-wrong-answer-fail-notification-946.mp3" type="audio/mpeg">
        </audio>
        """
    st.markdown(sound_file, unsafe_allow_html=True)

# ==================== LEARNING PLATFORM FUNCTIONS ====================
def get_user_courses(user_id=1):
    """Get courses enrolled by user"""
    conn = sqlite3.connect('selectionway.db', check_same_thread=False)
    query = """
    SELECT c.id, c.name, c.description, c.materials_count, e.batch_date, e.validity_days 
    FROM courses c 
    JOIN enrollments e ON c.id = e.course_id 
    WHERE e.user_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    return df

def get_all_courses():
    """Get all available courses"""
    conn = sqlite3.connect('selectionway.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM courses", conn)
    conn.close()
    return df

def get_study_materials(course_id):
    """Get study materials for a course"""
    conn = sqlite3.connect('selectionway.db', check_same_thread=False)
    query = "SELECT * FROM study_materials WHERE course_id = ?"
    df = pd.read_sql_query(query, conn, params=(course_id,))
    conn.close()
    return df

def enroll_user_in_course(user_id, course_id):
    """Enroll user in a course"""
    conn = sqlite3.connect('selectionway.db', check_same_thread=False)
    c = conn.cursor()
    
    # Check if already enrolled
    c.execute("SELECT * FROM enrollments WHERE user_id = ? AND course_id = ?", (user_id, course_id))
    if not c.fetchone():
        enroll_date = datetime.now().strftime("%Y-%m-%d")
        batch_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")  # Start after 7 days
        c.execute("INSERT INTO enrollments VALUES (?, ?, ?, ?, ?)", 
                 (user_id, course_id, enroll_date, batch_date, 730))
        conn.commit()
    
    conn.close()

# ==================== STREAMLIT APP ====================
def main():
    st.set_page_config(
        page_title="SelectionWay - Learning Platform", 
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Enhanced CSS
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: 700;
        background: linear-gradient(45deg, #2E86AB, #4BB3FD);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .course-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #007bff;
        transition: transform 0.3s ease;
    }
    .course-card:hover {
        transform: translateY(-5px);
    }
    .bubble-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    .question-bubble {
        background: white;
        border: 2px solid #e9ecef;
        border-radius: 50%;
        width: 80px;
        height: 80px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.3s ease;
        font-weight: bold;
    }
    .question-bubble.current {
        border-color: #007bff;
        background: #007bff;
        color: white;
        transform: scale(1.1);
    }
    .question-bubble.answered {
        border-color: #28a745;
        background: #28a745;
        color: white;
    }
    .question-bubble.marked {
        border-color: #ffc107;
        background: #ffc107;
        color: black;
    }
    .sidebar-toggle {
        position: fixed;
        left: 10px;
        top: 10px;
        z-index: 999;
        background: #007bff;
        color: white;
        border: none;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        font-size: 1.5rem;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    .sound-toggle {
        position: fixed;
        right: 10px;
        top: 10px;
        z-index: 999;
        background: #6c757d;
        color: white;
        border: none;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        cursor: pointer;
    }
    .timer-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 1
    if 'user_name' not in st.session_state:
        st.session_state.user_name = "Deepak"
    if 'sound_enabled' not in st.session_state:
        st.session_state.sound_enabled = True
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    if 'quiz_data' not in st.session_state:
        st.session_state.quiz_data = {}
    
    # Sidebar Toggle
    st.markdown("""
    <button class="sidebar-toggle" onclick="toggleSidebar()">☰</button>
    <button class="sound-toggle" onclick="toggleSound()">🔊</button>
    
    <script>
    function toggleSidebar() {
        // This will be handled by Streamlit buttons
    }
    function toggleSound() {
        // This will be handled by Streamlit
    }
    </script>
    """, unsafe_allow_html=True)
    
    # Main Navigation
    st.sidebar.title("🎓 SelectionWay")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigate to:", [
        "🏠 Home Dashboard", 
        "📝 PDF Quiz Maker", 
        "📚 My Courses", 
        "🕐 My Batches",
        "📥 Study Materials",
        "📊 Progress Report"
    ])
    
    # Sound Toggle in Sidebar
    st.sidebar.markdown("---")
    sound_status = "🔊 Sound On" if st.session_state.sound_enabled else "🔇 Sound Off"
    if st.sidebar.button(sound_status, use_container_width=True):
        st.session_state.sound_enabled = not st.session_state.sound_enabled
        st.rerun()
    
    # Page Routing
    if page == "🏠 Home Dashboard":
        show_home_dashboard()
    elif page == "📝 PDF Quiz Maker":
        show_pdf_quiz_maker()
    elif page == "📚 My Courses":
        show_my_courses()
    elif page == "🕐 My Batches":
        show_my_batches()
    elif page == "📥 Study Materials":
        show_study_materials()
    elif page == "📊 Progress Report":
        show_progress_report()

# ==================== PAGE FUNCTIONS ====================
def show_home_dashboard():
    st.markdown('<div class="main-header">🎓 Welcome to SelectionWay</div>', unsafe_allow_html=True)
    
    # User greeting
    st.markdown(f"# Hello, {st.session_state.user_name}!")
    
    # Quick Stats
    col1, col2, col3, col4 = st.columns(4)
    
    user_courses = get_user_courses(st.session_state.user_id)
    all_courses = get_all_courses()
    
    with col1:
        st.metric("Enrolled Courses", len(user_courses))
    with col2:
        st.metric("Available Courses", len(all_courses))
    with col3:
        st.metric("Study Materials", sum(user_courses['materials_count']))
    with col4:
        st.metric("Days Remaining", "730")
    
    st.markdown("---")
    
    # Enrolled Courses
    st.subheader("📚 My Enrolled Courses")
    if not user_courses.empty:
        for _, course in user_courses.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="course-card">
                    <h3>{course['name']}</h3>
                    <p>{course['description']}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span>📖 {course['materials_count']} Study Materials</span>
                        <span>🕐 Batch starts: {course['batch_date']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("You haven't enrolled in any courses yet. Visit 'My Courses' to enroll!")
    
    # Quick Actions
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📝 Create New Quiz", use_container_width=True):
            st.session_state.current_page = "PDF Quiz Maker"
            st.rerun()
    with col2:
        if st.button("📚 Browse Courses", use_container_width=True):
            st.session_state.current_page = "My Courses"
            st.rerun()
    with col3:
        if st.button("📥 Study Materials", use_container_width=True):
            st.session_state.current_page = "Study Materials"
            st.rerun()

def show_pdf_quiz_maker():
    st.markdown('<div class="main-header">📝 PDF to Quiz Converter</div>', unsafe_allow_html=True)
    
    # File upload
    uploaded_file = st.file_uploader("📁 Upload PDF File", type="pdf")
    
    if uploaded_file:
        if st.button("🚀 Convert to Quiz", type="primary"):
            with st.spinner("🔄 Converting PDF to quiz..."):
                text = extract_text_from_pdf(uploaded_file)
                questions = fast_parse_pdf_content(text)
                
                if questions:
                    st.session_state.quiz_data = {
                        'questions': questions,
                        'user_answers': {},
                        'current_q': 0,
                        'quiz_started': True,
                        'start_time': time.time(),
                        'question_start_time': time.time(),
                        'quiz_completed': False,
                        'marked_review': set(),
                        'show_ai_explanation': {}
                    }
                    st.success(f"✅ {len(questions)} questions generated!")
                else:
                    st.error("❌ No questions found in PDF")
    
    # Quiz Interface
    if st.session_state.quiz_data.get('questions'):
        render_quiz_interface()

def render_quiz_interface():
    quiz_data = st.session_state.quiz_data
    questions = quiz_data['questions']
    current_q = quiz_data['current_q']
    
    # Timer
    if quiz_data['quiz_started'] and not quiz_data['quiz_completed']:
        elapsed_time = time.time() - quiz_data['start_time']
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        
        st.markdown(f"""
        <div class="timer-container">
            <div style="font-size: 1.2rem; font-weight: 600;">⏱️ Practice Time</div>
            <div style="font-size: 2rem; font-weight: 700; font-family: monospace;">
                {minutes:02d}:{seconds:02d}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Quick Navigation Grid
    st.subheader("🎯 Quick Navigation")
    cols = st.columns(10)
    for idx in range(min(10, len(questions))):
        with cols[idx]:
            is_answered = idx in quiz_data['user_answers']
            is_current = idx == current_q
            is_marked = idx in quiz_data['marked_review']
            
            btn_text = f"Q{idx+1}"
            if is_marked:
                btn_text = f"📌{idx+1}"
            
            btn_type = "primary" if is_current else "secondary"
            if st.button(btn_text, key=f"nav_{idx}", use_container_width=True, type=btn_type):
                quiz_data['current_q'] = idx
                quiz_data['question_start_time'] = time.time()
                st.rerun()
    
    # Current Question
    if not quiz_data['quiz_completed']:
        question = questions[current_q]
        user_answer = quiz_data['user_answers'].get(current_q)
        
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 15px; margin: 1rem 0; color: white;">
            <h3>Question {current_q + 1} of {len(questions)}</h3>
            <div style="font-size: 1.2rem; font-weight: 600;">{question['question']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Options
        for opt_letter, opt_text in question['options'].items():
            is_selected = user_answer == opt_letter
            if st.button(
                f"{opt_letter}) {opt_text}",
                key=f"opt_{current_q}_{opt_letter}",
                use_container_width=True,
                type="primary" if is_selected else "secondary"
            ):
                quiz_data['user_answers'][current_q] = opt_letter
                if opt_letter == question['correct_answer']:
                    autoplay_audio("correct")
                else:
                    autoplay_audio("wrong")
                st.rerun()
        
        # Navigation
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("⏮️ Previous", disabled=current_q == 0):
                quiz_data['current_q'] = max(0, current_q - 1)
                quiz_data['question_start_time'] = time.time()
                st.rerun()
        with col2:
            if st.button("📌 Mark", type="secondary"):
                if current_q in quiz_data['marked_review']:
                    quiz_data['marked_review'].remove(current_q)
                else:
                    quiz_data['marked_review'].add(current_q)
                st.rerun()
        with col3:
            if current_q < len(questions) - 1:
                if st.button("Next ▶", type="primary"):
                    quiz_data['current_q'] += 1
                    quiz_data['question_start_time'] = time.time()
                    st.rerun()
            else:
                if st.button("Finish 🏁", type="primary"):
                    quiz_data['quiz_completed'] = True
                    st.rerun()
    
    else:
        # Results
        show_quiz_results()

def show_quiz_results():
    quiz_data = st.session_state.quiz_data
    questions = quiz_data['questions']
    
    correct_count = 0
    for idx, q in enumerate(questions):
        if quiz_data['user_answers'].get(idx) == q['correct_answer']:
            correct_count += 1
    
    score_percent = (correct_count / len(questions)) * 100
    total_time = time.time() - quiz_data['start_time']
    
    st.balloons()
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #00b09b, #96c93d); color: white; padding: 3rem; border-radius: 20px; text-align: center;">
        <h1>🏆 Quiz Completed!</h1>
        <h2>Score: {correct_count}/{len(questions)}</h2>
        <h1>{score_percent:.1f}%</h1>
        <p>Time Taken: {int(total_time//60):02d}:{int(total_time%60):02d}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔄 Take Another Quiz", use_container_width=True):
        st.session_state.quiz_data = {}
        st.rerun()

def show_my_courses():
    st.markdown('<div class="main-header">📚 Available Courses</div>', unsafe_allow_html=True)
    
    courses_df = get_all_courses()
    user_courses = get_user_courses(st.session_state.user_id)
    enrolled_course_ids = user_courses['id'].tolist()
    
    for _, course in courses_df.iterrows():
        is_enrolled = course['id'] in enrolled_course_ids
        
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"""
                <div class="course-card">
                    <h3>{course['name']}</h3>
                    <p>{course['description']}</p>
                    <div style="display: flex; gap: 2rem; margin-top: 1rem;">
                        <span>📖 {course['materials_count']} Materials</span>
                        <span>👥 {course['students_count']} Students</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if is_enrolled:
                    st.success("✅ Enrolled")
                    if st.button("📖 Study", key=f"study_{course['id']}"):
                        st.session_state.selected_course = course['id']
                        st.session_state.current_page = "Study Materials"
                        st.rerun()
                else:
                    if st.button("🎯 Enroll Now", key=f"enroll_{course['id']}", type="primary"):
                        enroll_user_in_course(st.session_state.user_id, course['id'])
                        st.success("✅ Successfully enrolled!")
                        st.rerun()

def show_my_batches():
    st.markdown('<div class="main-header">🕐 My Batches</div>', unsafe_allow_html=True)
    
    user_courses = get_user_courses(st.session_state.user_id)
    
    if not user_courses.empty:
        for _, batch in user_courses.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="course-card">
                    <h3>🎯 {batch['name']}</h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                        <div>
                            <strong>Start Date</strong><br>
                            📅 {batch['batch_date']}
                        </div>
                        <div>
                            <strong>Validity</strong><br>
                            ⏳ {batch['validity_days']} days
                        </div>
                        <div>
                            <strong>Materials</strong><br>
                            📚 {batch['materials_count']} files
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No active batches. Enroll in a course to get started!")

def show_study_materials():
    st.markdown('<div class="main-header">📥 Study Materials</div>', unsafe_allow_html=True)
    
    user_courses = get_user_courses(st.session_state.user_id)
    
    if not user_courses.empty:
        selected_course = st.selectbox("Select Course", user_courses['name'].tolist())
        
        course_id = user_courses[user_courses['name'] == selected_course]['id'].iloc[0]
        materials = get_study_materials(course_id)
        
        if not materials.empty:
            st.subheader(f"Study Materials for {selected_course}")
            
            for _, material in materials.iterrows():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**{material['name']}**")
                    st.write(f"Uploaded: {material['upload_date']}")
                
                with col2:
                    st.write(f"📄 {material['file_type']}")
                
                with col3:
                    if st.button("📥 Download", key=f"dl_{material['id']}"):
                        st.success(f"Downloading {material['name']}")
        else:
            st.info("No study materials available for this course yet.")
    else:
        st.info("Enroll in a course to access study materials!")

def show_progress_report():
    st.markdown('<div class="main-header">📊 Progress Report</div>', unsafe_allow_html=True)
    
    user_courses = get_user_courses(st.session_state.user_id)
    
    if not user_courses.empty:
        st.subheader("Course Progress")
        
        for _, course in user_courses.iterrows():
            progress = random.randint(20, 95)  # Simulated progress
            st.write(f"**{course['name']}**")
            st.progress(progress)
            st.write(f"Progress: {progress}%")
            st.markdown("---")
        
        # Quiz Performance
        st.subheader("Quiz Performance")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Quizzes Taken", "12")
        with col2:
            st.metric("Average Score", "78%")
        with col3:
            st.metric("Best Score", "95%")
        
        # Study Time
        st.subheader("Study Time")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Hours", "45")
        with col2:
            st.metric("Daily Average", "1.5h")
        with col3:
            st.metric("Current Streak", "7 days")
    
    else:
        st.info("Start learning to see your progress!")

if __name__ == "__main__":
    main()
