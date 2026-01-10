from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yaml
import os

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


@app.get("/quiz/{quiz_name}", response_class=HTMLResponse)
def quiz(request: Request, quiz_name: str):
    quiz = load_quiz(quiz_name)
    questions = quiz.get("Question", [])
    if not isinstance(questions, list):
        questions = [questions]

    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "quiz_name": quiz_name,
            "title": quiz.get("Quiz", "Quiz"),
            "questions": questions,
        },
    )


@app.post("/quiz/{quiz_name}/submit", response_class=HTMLResponse)
async def submit(request: Request, quiz_name: str):
    quiz = load_quiz(quiz_name)
    questions = quiz.get("Question", [])
    if not isinstance(questions, list):
        questions = [questions]

    form = await request.form()

    score = 0
    total = len(questions)

    for i, q in enumerate(questions):
        qtype = q["Type"]
        correct = q["Correct"]

        if qtype == "singlechoice":
            if form.get(f"q{i}") == correct:
                score += 1

        elif qtype == "multiplechoice":
            selected = form.getlist(f"q{i}")
            if sorted(selected) == sorted(correct):
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
