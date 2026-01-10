# Quiz App with User Authentication

A fast and simple quiz application with user authentication and progress tracking for your family.

## 🎯 Features

- **User Authentication**: Hardcoded users (Mate, Maja, drunyd admin)
- **Progress Tracking**: SQLite database to store quiz attempts
- **Parent Dashboard**: Admin can track kids' quiz history and performance
- **Child Dashboard**: Kids can view their own progress and achievements
- **Session Management**: Secure login/logout functionality
- **Responsive Design**: Works on desktop and mobile devices

## 👥 User Accounts

### Children
- **Username**: Mate, **Password**: mate123
- **Username**: Maja, **Password**: maja123

### Admin (Parent)
- **Username**: drunyd, **Password**: admin123

## 🚀 Quick Start

1. **Setup virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start the server**:
   ```bash
   source venv/bin/activate
   uvicorn app:app --host 0.0.0.0 --port 8001
   ```

3. **Access the app**:
   - Open browser: http://localhost:8001/login
   - Login with any of the user accounts above

## 📊 How It Works

### For Kids (Mate & Maja)
1. Login with their credentials
2. Select and take quizzes from the main page
3. View their progress on the dashboard
4. See achievements and performance statistics

### For Admin (drunyd)
1. Login with admin credentials
2. Access admin dashboard to track both children's progress
3. View detailed quiz history, scores, and trends
4. Monitor learning progress over time

## 🗂️ File Structure

```
paqui/
├── app.py                    # Main FastAPI application
├── users.json               # Hardcoded user accounts
├── quiz_app.db             # SQLite database for progress
├── requirements.txt        # Python dependencies
├── templates/             # HTML templates
│   ├── login.html         # Login page
│   ├── index.html         # Quiz selection
│   ├── quiz.html          # Quiz interface
│   ├── result.html        # Results display
│   ├── admin_dashboard.html # Parent dashboard
│   └── user_dashboard.html # Child dashboard
├── quizzes/              # YAML quiz files
│   └── sample.yaml       # Sample quiz
└── static/               # CSS and static assets
```

## 🔧 Technical Details

### Backend
- **FastAPI**: Modern Python web framework
- **SQLite**: Lightweight database for progress tracking
- **Session Management**: Secure user sessions
- **Jinja2**: Template engine for HTML rendering

### Frontend
- **Bootstrap 5**: Responsive UI framework
- **MDBootstrap**: Enhanced UI components
- **Google Fonts**: Modern typography (Poppins)

### Data Storage
- **users.json**: Hardcoded user accounts (username, password, role, parent)
- **quiz_app.db**: SQLite database with quiz_attempts table

## 📈 Progress Tracking

The application tracks:
- Quiz completion history
- Scores and percentages
- Timestamp of attempts
- Performance trends
- Achievements and milestones

## 🛠️ Adding New Users

To add more children, edit `users.json`:

```json
{
  "users": [
    {
      "username": "NewChild",
      "password": "password123",
      "role": "child",
      "parent": "drunyd"
    }
  ]
}
```

## 🎮 Quiz Format

Quizzes are stored in YAML format in the `quizzes/` directory. Each quiz supports:
- **singlechoice**: Multiple choice with one correct answer
- **multiplechoice**: Multiple choice with multiple correct answers  
- **word**: Text input answers

Example:
```yaml
Quiz: "Sample Quiz"
Question:
  - Type: singlechoice
    Text: "What is 2 + 2?"
    A: "3"
    B: "4"
    C: "5"
    D: "6"
    Correct: "B"
```

## 🔒 Security

- Simple password-based authentication (suitable for family use)
- Session-based authentication
- No sensitive data exposure
- Child-friendly interface

## 📱 Mobile Support

The application is fully responsive and works on:
- Desktop computers
- Tablets
- Mobile phones

## 🎯 Future Enhancements

- Password hashing for better security
- More quiz types and features
- Progress export functionality
- Multi-language support
- Email notifications for parents

## 🤝 How to Use

1. **Start Learning**: Kids log in and take quizzes
2. **Track Progress**: Admin views children's performance
3. **Celebrate Success**: Achievements and milestones
4. **Monitor Growth**: Detailed analytics over time

Enjoy watching your children learn and grow with the quiz app! 🎉