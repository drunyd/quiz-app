from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
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
from urllib.parse import quote

QUIZ_DIR = os.environ.get("QUIZ_DIR", "quizzes")
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


def normalize_answer(text: str) -> str:
    """Remove all spaces and uppercase, for forgiving word matching."""
    return "".join(str(text).split()).upper()


def load_quiz(filename: str):
    path = os.path.join(QUIZ_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Web assets that may be served as a quiz's source material
SOURCE_EXTENSIONS = {
    ".html", ".htm", ".css", ".js",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf",
}


def get_quiz_source(quiz_path: str, quiz: Optional[dict] = None):
    """Return (source_path, source_url) for a quiz's Source attribute.

    Source is relative to QUIZ_DIR and is ignored (returns None, None) if the
    attribute is missing, escapes QUIZ_DIR, or points at a missing file.
    """
    if quiz is None:
        try:
            quiz = load_quiz(quiz_path)
        except (OSError, yaml.YAMLError):
            return None, None

    source = quiz.get("Source") if isinstance(quiz, dict) else None
    if not source:
        return None, None

    source = str(source).strip().replace("\\", "/").lstrip("/")
    if not source or ".." in source.split("/"):
        return None, None

    if not os.path.isfile(os.path.join(QUIZ_DIR, source)):
        return None, None

    return source, "/source/" + quote(source, safe="/")


def get_directory_contents(path: str = ""):
    """Get folders and quiz files at current directory level"""
    target_dir = os.path.join(QUIZ_DIR, path) if path else QUIZ_DIR
    
    if not os.path.exists(target_dir):
        return {"folders": [], "files": [], "parent_path": None, "current_path": "Unknown"}
    
    folders = []
    files = []
    
    for item in sorted(os.listdir(target_dir)):
        item_path = os.path.join(target_dir, item)
        rel_path = os.path.join(path, item) if path else item
        
        if os.path.isdir(item_path):
            # Count all quizzes in subdirectory and its subdirectories
            quiz_count = 0
            for root, dirs, files_in_dir in os.walk(item_path):
                quiz_count += len([f for f in files_in_dir if f.endswith('.yaml')])
            
            if quiz_count > 0:
                folders.append({
                    'name': item,
                    'path': rel_path,
                    'quiz_count': quiz_count
                })
        elif item.endswith('.yaml'):
            files.append({
                'name': item,
                'path': rel_path,
                'display_name': item.replace('.yaml', '').replace('.', ' ').title()
            })
    
    # Parent path for navigation
    parent_path = os.path.dirname(path) if path and path != "." else None
    
    return {
        "folders": folders,
        "files": files,
        "parent_path": parent_path,
        "current_path": path or "Quizzes"
    }


def get_breadcrumb_data(path: str = ""):
    """Generate breadcrumb navigation for current path"""
    if not path:
        return [{"name": "Quizzes", "path": ""}]
    
    parts = path.split('/')
    breadcrumb = [{"name": "Quizzes", "path": ""}]
    current_path = ""
    
    for part in parts:
        current_path = os.path.join(current_path, part) if current_path else part
        breadcrumb.append({"name": part, "path": current_path})
    
    return breadcrumb


WIKI_ROOT_SUFFIX = "_wiki"
WIKI_EXTENSIONS = (".html", ".htm")


def count_wiki_files(folder: str) -> int:
    """Count HTML source files under a folder, recursively."""
    total = 0
    for _root, _dirs, files in os.walk(folder):
        total += len([f for f in files if f.lower().endswith(WIKI_EXTENSIONS)])
    return total


def get_wiki_directory_contents(path: str = ""):
    """Browse the *_wiki source trees the same way quizzes are browsed."""
    if not path:
        folders = []
        if os.path.isdir(QUIZ_DIR):
            for item in sorted(os.listdir(QUIZ_DIR)):
                item_path = os.path.join(QUIZ_DIR, item)
                if not (os.path.isdir(item_path) and item.endswith(WIKI_ROOT_SUFFIX)):
                    continue
                wiki_count = count_wiki_files(item_path)
                if wiki_count:
                    folders.append({
                        'name': item,
                        'path': item,
                        'wiki_count': wiki_count,
                    })
        return {
            "folders": folders,
            "files": [],
            "parent_path": None,
            "current_path": "Wikis",
        }

    target_dir = os.path.join(QUIZ_DIR, path)
    if not os.path.isdir(target_dir):
        return {"folders": [], "files": [], "parent_path": None, "current_path": "Unknown"}

    folders = []
    files = []

    for item in sorted(os.listdir(target_dir)):
        item_path = os.path.join(target_dir, item)
        rel_path = os.path.join(path, item)

        if os.path.isdir(item_path):
            wiki_count = count_wiki_files(item_path)
            if wiki_count:
                folders.append({
                    'name': item,
                    'path': rel_path,
                    'wiki_count': wiki_count,
                })
        elif item.lower().endswith(WIKI_EXTENSIONS):
            files.append({
                'name': item,
                'path': rel_path,
                'display_name': item.rsplit('.', 1)[0].replace('.', ' ').title(),
            })

    parent_path = os.path.dirname(path) if path and path != "." else None

    return {
        "folders": folders,
        "files": files,
        "parent_path": parent_path,
        "current_path": path or "Wikis",
    }


def get_wiki_breadcrumb_data(path: str = ""):
    """Generate breadcrumb navigation for the wiki explorer."""
    breadcrumb = [{"name": "Wikis", "path": ""}]
    if not path:
        return breadcrumb

    current_path = ""
    for part in path.split('/'):
        current_path = os.path.join(current_path, part) if current_path else part
        breadcrumb.append({"name": part, "path": current_path})

    return breadcrumb


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
    """Redirect to browse root for file explorer"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    return RedirectResponse(url="/browse", status_code=HTTP_302_FOUND)


@app.get("/browse/{path:path}", response_class=HTMLResponse)
def browse(request: Request, path: str = ""):
    """Browse quizzes at specific directory level"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    contents = get_directory_contents(path)
    breadcrumb = get_breadcrumb_data(path)
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "contents": contents,
            "breadcrumb": breadcrumb,
            "user": user,
            "explorer_mode": True,
        },
    )


@app.get("/source/{source_path:path}")
def source_file(request: Request, source_path: str):
    """Serve a quiz's source material (wiki HTML plus any relative assets)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)

    root = os.path.realpath(QUIZ_DIR)
    target = os.path.realpath(os.path.join(root, source_path))

    if target != root and not target.startswith(root + os.sep):
        raise HTTPException(status_code=404)

    extension = os.path.splitext(target)[1].lower()
    if extension not in SOURCE_EXTENSIONS or not os.path.isfile(target):
        raise HTTPException(status_code=404)

    return FileResponse(target)


@app.get("/wikis", response_class=HTMLResponse)
def wikis_root(request: Request):
    """Browse the top-level wiki source folders."""
    return render_wikis(request, "")


@app.get("/wikis/{path:path}", response_class=HTMLResponse)
def wikis(request: Request, path: str = ""):
    """Browse wiki source folders and read their articles."""
    return render_wikis(request, path)


def render_wikis(request: Request, path: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)

    contents = get_wiki_directory_contents(path)
    breadcrumb = get_wiki_breadcrumb_data(path)

    return templates.TemplateResponse(
        "wikis.html",
        {
            "request": request,
            "contents": contents,
            "breadcrumb": breadcrumb,
            "user": user,
            "explorer_mode": True,
        },
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
    key_mapping = {}  # Store mapping from new key to original key
    for i, key in enumerate(valid_keys):
        shuffled[keys[i]] = question[key]
        key_mapping[keys[i]] = key  # Map new position to original key
    
    question.update(shuffled)
    question["Correct"] = new_correct
    question["shuffled_keys"] = keys[:len(valid_keys)]
    question["key_mapping"] = key_mapping  # Store the mapping for answer evaluation
    
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

def shuffle_pairing(question):
    """Shuffle both columns of a pairing question independently.

    Stores the display order in left_items/right_items and the correct
    right-hand pair index for each displayed left slot in pairing_correct.
    """
    pairs = question.get("Pairs") or []
    valid = [
        (idx, str(pair[0]), str(pair[1]))
        for idx, pair in enumerate(pairs)
        if isinstance(pair, (list, tuple)) and len(pair) >= 2
    ]

    left = [(idx, left_text) for idx, left_text, _right_text in valid]
    right = [(idx, right_text) for idx, _left_text, right_text in valid]
    random.shuffle(left)
    random.shuffle(right)

    question["left_items"] = [{"pair": idx, "text": text} for idx, text in left]
    question["right_items"] = [{"pair": idx, "text": text} for idx, text in right]
    question["pairing_correct"] = [str(idx) for idx, _text in left]

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


def prepare_questions(questions):
    """Select/shuffle questions and build per-type display state."""
    if not isinstance(questions, list):
        questions = [questions]

    questions, original_indices = select_and_shuffle_questions(questions)

    for question in questions:
        qtype = question.get("Type")
        if qtype == "singlechoice":
            shuffle_singlechoice(question)
        elif qtype == "multiplechoice":
            shuffle_multiplechoice(question)
        elif qtype == "pairing":
            shuffle_pairing(question)

    return questions, original_indices


@app.get("/quiz/{quiz_path:path}", response_class=HTMLResponse)
def quiz(request: Request, quiz_path: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    quiz = load_quiz(quiz_path)
    questions = quiz.get("Question", [])
    if not isinstance(questions, list):
        questions = [questions]

    source_path, source_url = get_quiz_source(quiz_path, quiz)

    # Randomly select and shuffle questions
    questions, original_indices = prepare_questions(questions)

    # Store the complete shuffled state as JSON
    import json
    shuffled_state = json.dumps([{
        'original_index': idx,
        'question': q
    } for idx, q in zip(original_indices, questions)])

    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "quiz_name": quiz_path,
            "title": quiz.get("Quiz", "Quiz"),
            "questions": questions,
            "original_indices": original_indices,
            "shuffled_state": shuffled_state,
            "source_url": source_url,
            "user": user,
        },
    )


@app.post("/quiz/{quiz_path:path}/submit", response_class=HTMLResponse)
async def submit(request: Request, quiz_path: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    
    form = await request.form()
    
    # Get the stored shuffled state from the form
    shuffled_state_str = str(form.get("shuffled_state", ""))
    import json
    
    if shuffled_state_str:
        try:
            shuffled_data = json.loads(shuffled_state_str)
            shuffled_questions = [item['question'] for item in shuffled_data]
        except (json.JSONDecodeError, KeyError):
            shuffled_questions = None
    else:
        shuffled_questions = None

    if shuffled_questions is None:
        # Fallback: reload and re-shuffle
        quiz = load_quiz(quiz_path)
        shuffled_questions, _ = prepare_questions(quiz.get("Question", []))

    score = 0
    total = len(shuffled_questions)
    incorrect_answers = []

    for i, q in enumerate(shuffled_questions):
        qtype = q["Type"]
        correct = q.get("Correct")
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
                # Now using the stored shuffled state, the mapping should be correct
                user_answer_text = q.get(user_answer, 'No answer selected') if user_answer else 'No answer selected'
                correct_answer_text = q.get(original_correct, 'Unknown') if original_correct else 'Unknown'
                
                incorrect_answers.append({
                    'question': q.get('Text', f'Question {i+1}'),
                    'user_answer': user_answer_text,
                    'correct_answer': correct_answer_text,
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
                        'question': q.get('Text', f'Question {i+1}'),
                        'user_answer': ', '.join(user_answers_text) if user_answers_text else 'No answer selected',
                        'correct_answer': ', '.join(correct_answers_text) if correct_answers_text else 'Unknown',
                        'question_type': 'multiplechoice'
                    })

        elif qtype == "word":
            raw_answer = str(form.get(f"q{i}", "")).strip()
            answer = normalize_answer(raw_answer)
            valid = [normalize_answer(c) for c in correct]
            if answer and answer in valid:
                score += 1
                is_correct = True
            else:
                # Store incorrect answer details
                incorrect_answers.append({
                    'question': q.get('Text', f'Question {i+1}'),
                    'user_answer': raw_answer if raw_answer else 'No answer provided',
                    'correct_answer': ', '.join(str(c) for c in correct),
                    'question_type': 'word'
                })

        elif qtype == "ordering":
            # Get the user's submitted order (list of items in their chosen order)
            user_order = form.getlist(f"q{i}")
            # Get the correct order from hidden field
            correct_order_str = str(form.get(f"q{i}_correct", ""))
            if correct_order_str:
                correct_order = correct_order_str.split('|||')
                if user_order == correct_order:
                    score += 1
                    is_correct = True
                else:
                    incorrect_answers.append({
                        'question': q.get('Text', f'Question {i+1}'),
                        'user_answer': ' → '.join(user_order) if user_order else 'No order provided',
                        'correct_answer': ' → '.join(correct_order),
                        'question_type': 'ordering'
                    })

        elif qtype == "pairing":
            user_choices = [str(v) for v in form.getlist(f"q{i}")]
            correct_choices = [str(v) for v in q.get("pairing_correct", [])]

            # Missing slots (unanswered) count as empty and therefore wrong
            while len(user_choices) < len(correct_choices):
                user_choices.append("")

            if correct_choices and user_choices == correct_choices:
                score += 1
                is_correct = True
            else:
                left_items = q.get("left_items", [])
                right_by_pair = {
                    str(item.get("pair")): item.get("text", "")
                    for item in q.get("right_items", [])
                }

                def format_pairing(choices):
                    parts = []
                    for slot_index, left in enumerate(left_items):
                        picked = choices[slot_index] if slot_index < len(choices) else ""
                        picked_text = right_by_pair.get(str(picked), "nincs pár")
                        parts.append(f"{left.get('text', '')} → {picked_text}")
                    return "; ".join(parts) if parts else "Nincs párosítás"

                incorrect_answers.append({
                    'question': q.get('Text', f'Question {i+1}'),
                    'user_answer': format_pairing(user_choices),
                    'correct_answer': format_pairing(correct_choices),
                    'question_type': 'pairing'
                })

    # Save the quiz attempt
    save_quiz_attempt(user['username'], quiz_path, score, total)

    source_path, source_url = get_quiz_source(quiz_path)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "score": score,
            "total": total,
            "user": user,
            "incorrect_answers": incorrect_answers,
            "quiz_name": quiz_path,
            "source_url": source_url,
        },
    )
