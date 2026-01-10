from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yaml
import os
import random

QUIZ_DIR = "quizzes"

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def load_quiz(filename: str):
    path = os.path.join(QUIZ_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    quizzes = sorted(f for f in os.listdir(QUIZ_DIR) if f.endswith(".yaml"))
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "quizzes": quizzes},
    )


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
        },
    )


@app.post("/quiz/{quiz_name}/submit", response_class=HTMLResponse)
async def submit(request: Request, quiz_name: str):
    quiz = load_quiz(quiz_name)
    questions = quiz.get("Question", [])
    if not isinstance(questions, list):
        questions = [questions]

    form = await request.form()
    
    # Get the original indices from the form to reconstruct the same shuffled order
    original_indices_str = form.get("original_indices", "")
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

    for i, q in enumerate(shuffled_questions):
        qtype = q["Type"]
        correct = q["Correct"]

        if qtype == "singlechoice":
            # Get the original correct answer from the form data
            original_correct = form.get(f"q{i}_correct")
            if form.get(f"q{i}") == original_correct:
                score += 1

        elif qtype == "multiplechoice":
            # Get the original correct answers from the form data
            original_correct_str = form.get(f"q{i}_correct")
            if original_correct_str:
                original_correct = original_correct_str.split(',')
                selected = form.getlist(f"q{i}")
                if sorted(selected) == sorted(original_correct):
                    score += 1

        elif qtype == "word":
            answer = form.get(f"q{i}", "").strip()
            valid = [str(c) for c in correct]
            if answer in valid:
                score += 1

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "score": score,
            "total": total,
        },
    )
