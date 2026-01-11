from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND
import yaml
import os
import random
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional

QUIZ_DIR = "quizzes"
USERS_FILE = "users.json"
DB_FILE = "quiz_app.db"

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            quiz_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            percentage REAL NOT NULL,
            timestamp TEXT NOT NULL,
            time_taken INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()


def load_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)


def verify_user(username: str, password: str):
    users = load_users()
    for user in users['users']:
        if user['username'] == username and user['password'] == password:
            return user
    return None


def get_current_user(request: Request):
    username = request.session.get('username')
    if not username:
        return None
    
    users = load_users()
    for user in users['users']:
        if user['username'] == username:
            return user
    return None


def save_quiz_attempt(username: str, quiz_name: str, score: int, total: int, time_taken: int = 0):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    percentage = (score / total) * 100 if total > 0 else 0
    timestamp = datetime.now().isoformat()
    
    # Default time_taken to 0 if None to avoid database constraint issues
    if time_taken is None:
        time_taken = 0
    
    cursor.execute('''
        INSERT INTO quiz_attempts (username, quiz_name, score, total, percentage, timestamp, time_taken)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (username, quiz_name, score, total, percentage, timestamp, time_taken))
    
    conn.commit()
    conn.close()


def get_user_progress(username: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT quiz_name, score, total, percentage, timestamp, time_taken
        FROM quiz_attempts
        WHERE username = ?
        ORDER BY timestamp DESC
    ''', (username,))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{
        'quiz_name': row[0],
        'score': row[1],
        'total': row[2], 
        'percentage': row[3],
        'timestamp': row[4],
        'time_taken': row[5]
    } for row in results]


def get_children_progress(admin_username: str):
    users = load_users()
    children = [u['username'] for u in users['users'] if u.get('parent') == admin_username]
    
    all_progress = {}
    for child in children:
        all_progress[child] = get_user_progress(child)
    
    return all_progress


# Initialize database on startup
init_db()


def load_quiz(filename: str):
    path = os.path.join(QUIZ_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = verify_user(username, password)
    if user:
        request.session['username'] = username
        request.session['role'] = user['role']
        return RedirectResponse(url="/", status_code=HTTP_302_FOUND)
    else:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    quizzes = sorted(f for f in os.listdir(QUIZ_DIR) if f.endswith(".yaml"))
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "quizzes": quizzes, "user": user},
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    if user['role'] == 'admin':
        children_progress = get_children_progress(user['username'])
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "user": user,
            "children_progress": children_progress
        })
    else:
        progress = get_user_progress(user['username'])
        return templates.TemplateResponse("user_dashboard.html", {
            "request": request,
            "user": user,
            "progress": progress
        })


def shuffle_singlechoice(question):
    keys = ["A", "B", "C", "D"]
    valid_keys = [k for k in keys if k in question]
    random.shuffle(valid_keys)
    
    original_correct = question["Correct"]
    new_correct_index = valid_keys.index(original_correct)
    new_correct = keys[new_correct_index]
    
    shuffled = {}
    for i, key in enumerate(valid_keys):
        shuffled[keys[i]] = question[key]
    
    question.update(shuffled)
    question["Correct"] = new_correct
    question["shuffled_keys"] = keys[:len(valid_keys)]
    
    return question

def shuffle_multiplechoice(question):
    answers = question["Answers"].copy()
    original_correct = question["Correct"].copy()
    
    indexed_answers = list(enumerate(answers))
    random.shuffle(indexed_answers)
    
    shuffled_answers = [ans for i, ans in indexed_answers]
    
    new_correct_indices = []
    for correct_ans in original_correct:
        for new_idx, (orig_idx, ans) in enumerate(indexed_answers):
            if ans == correct_ans:
                new_correct_indices.append(new_idx)
                break
    
    question["Answers"] = shuffled_answers
    question["Correct"] = new_correct_indices
    
    return question

def select_and_shuffle_questions(questions):
    # Create a list of (original_index, question) tuples
    indexed_questions = list(enumerate(questions))
    random.shuffle(indexed_questions)
    
    # Select maximum 10 questions
    if len(indexed_questions) > 10:
        indexed_questions = indexed_questions[:10]
    
    # Return just the questions and the mapping
    shuffled_questions = [q for idx, q in indexed_questions]
    original_indices = [idx for idx, q in indexed_questions]
    
    return shuffled_questions, original_indices

@app.get("/quiz/{quiz_name}", response_class=HTMLResponse)
def quiz(request: Request, quiz_name: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    quiz = load_quiz(quiz_name)
    questions = quiz.get("Question", [])
    if not isinstance(questions, list):
        questions = [questions]

    # Randomly select and shuffle questions
    questions, original_indices = select_and_shuffle_questions(questions)

    for question in questions:
        if question["Type"] == "singlechoice":
            shuffle_singlechoice(question)
        elif question["Type"] == "multiplechoice":
            shuffle_multiplechoice(question)

    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "quiz_name": quiz_name,
            "title": quiz.get("Quiz", "Quiz"),
            "questions": questions,
            "original_indices": original_indices,
            "user": user,
        },
    )


@app.post("/quiz/{quiz_name}/submit", response_class=HTMLResponse)
async def submit(request: Request, quiz_name: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    quiz = load_quiz(quiz_name)
    questions = quiz.get("Question", [])
    if not isinstance(questions, list):
        questions = [questions]

    form = await request.form()
    
    # Get the original indices from the form to reconstruct the same shuffled order
    original_indices_str = str(form.get("original_indices", ""))
    if original_indices_str:
        original_indices = [int(idx) for idx in original_indices_str.split(',')]
        # Reconstruct the same shuffled questions
        shuffled_questions = [questions[idx] for idx in original_indices]
    else:
        # Fallback: apply the same random selection (shouldn't happen normally)
        shuffled_questions, original_indices = select_and_shuffle_questions(questions)

    # Apply answer shuffling to the same questions that were displayed
    for question in shuffled_questions:
        if question["Type"] == "singlechoice":
            shuffle_singlechoice(question)
        elif question["Type"] == "multiplechoice":
            shuffle_multiplechoice(question)

    score = 0
    total = len(shuffled_questions)
    incorrect_answers = []

    for i, q in enumerate(shuffled_questions):
        qtype = q["Type"]
        correct = q["Correct"]
        is_correct = False

        if qtype == "singlechoice":
            # Get the original correct answer from the form data
            original_correct = str(form.get(f"q{i}_correct", ""))
            user_answer = str(form.get(f"q{i}", ""))
            if user_answer == original_correct:
                score += 1
                is_correct = True
            else:
                # Store incorrect answer details
                incorrect_answers.append({
                    'question': q.get('Question', f'Question {i+1}'),
                    'user_answer': q.get(user_answer, 'No answer selected'),
                    'correct_answer': q.get(original_correct, 'Unknown'),
                    'question_type': 'singlechoice'
                })

        elif qtype == "multiplechoice":
            # Get the original correct answers from the form data
            original_correct_str = str(form.get(f"q{i}_correct", ""))
            if original_correct_str:
                original_correct = original_correct_str.split(',')
                selected = [str(item) for item in form.getlist(f"q{i}")]
                if sorted(selected) == sorted(original_correct):
                    score += 1
                    is_correct = True
                else:
                    # Store incorrect answer details
                    correct_answers_text = []
                    user_answers_text = []
                    
                    for idx in original_correct:
                        try:
                            idx_int = int(idx)
                            if idx_int < len(q.get("Answers", [])):
                                correct_answers_text.append(q.get("Answers", [])[idx_int])
                        except ValueError:
                            continue
                    
                    for idx in selected:
                        try:
                            idx_int = int(idx)
                            if idx_int < len(q.get("Answers", [])):
                                user_answers_text.append(q.get("Answers", [])[idx_int])
                        except ValueError:
                            continue
                    
                    incorrect_answers.append({
                        'question': q.get('Question', f'Question {i+1}'),
                        'user_answer': ', '.join(user_answers_text) if user_answers_text else 'No answer selected',
                        'correct_answer': ', '.join(correct_answers_text) if correct_answers_text else 'Unknown',
                        'question_type': 'multiplechoice'
                    })

        elif qtype == "word":
            answer = str(form.get(f"q{i}", "")).strip()
            valid = [str(c) for c in correct]
            if answer in valid:
                score += 1
                is_correct = True
            else:
                # Store incorrect answer details
                incorrect_answers.append({
                    'question': q.get('Question', f'Question {i+1}'),
                    'user_answer': answer if answer else 'No answer provided',
                    'correct_answer': ', '.join(str(c) for c in correct),
                    'question_type': 'word'
                })

    # Save the quiz attempt
    save_quiz_attempt(user['username'], quiz_name, score, total)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "score": score,
            "total": total,
            "user": user,
            "incorrect_answers": incorrect_answers,
        },
    )
