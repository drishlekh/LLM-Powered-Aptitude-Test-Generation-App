  
import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv
import time
import random
import json
from collections import defaultdict
from agent import run_graph_agent
import markdown 

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key_here')

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SUBJECTS = ["Logical Reasoning", "Quantitative Aptitude", "Verbal Ability"]
SUBJECT_MAP = {"Logical Reasoning": "LR", "Quantitative Aptitude": "QA", "Verbal Ability": "VA"}



@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        selected_subjects = request.form.getlist('subjects')
        difficulty = request.form.get('difficulty', 'Medium')
        num_questions = min(int(request.form.get('num_questions', 5)), 30)
        timed_test = request.form.get('timed_test') == 'on'
        
        questions = []
        if selected_subjects:
            questions_per_subject = num_questions // len(selected_subjects)
            remaining_questions = num_questions % len(selected_subjects)
            
            for i, subject in enumerate(selected_subjects):
                q_count = questions_per_subject + (1 if i < remaining_questions else 0)
                if q_count > 0:
                    subject_questions = generate_questions(subject, difficulty, q_count)
                    for q in subject_questions:
                        q['subject'] = subject
                        q.setdefault('chapter', 'General')
                    questions.extend(subject_questions)
        
        random.shuffle(questions)
        
        session['questions'] = questions
        session['score'] = 0
        session['start_time'] = time.time()
        session['timed_test'] = timed_test
        session['user_answers'] = {}
        
        return redirect(url_for('quiz'))
    
    return render_template('index.html', subjects=SUBJECTS)


@app.route('/quiz')
def quiz():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    all_questions = session.get('questions', [])
    
    time_left = None
    if session.get('timed_test'):
        elapsed = time.time() - session['start_time']
        total_time = len(all_questions) * 60
        time_left = max(0, total_time - elapsed)

    return render_template('quiz.html', 
                           questions=all_questions,
                           total_questions=len(all_questions),
                           timed_test=session.get('timed_test', False),
                           time_left=time_left,
                           subject_map=SUBJECT_MAP)


@app.route('/check_answer', methods=['POST'])
def check_answer():
    if 'questions' not in session:
        return jsonify({'error': 'Session expired'}), 400
    
    data = request.get_json()
    selected_option = data.get('selected_option')
    question_index = data.get('question_index')

    all_questions = session.get('questions', [])
    
    if question_index is None or not (0 <= question_index < len(all_questions)):
        return jsonify({'error': 'Invalid question index'}), 400
        
    question = all_questions[question_index]
    is_correct = (selected_option == question['correct_answer'])
    
    session['user_answers'][str(question_index)] = {
        'user_answer': selected_option,
        'is_correct': is_correct
    }
    
    session.modified = True
    
    return jsonify({
        'is_correct': is_correct,
        'correct_answer': question['correct_answer'],
        'solution': question.get('solution', "Solution not available.")
    })


@app.route('/results')
def results():
    if 'questions' not in session:
        return redirect(url_for('index'))

    all_questions = session.get('questions', [])
    user_answers = session.get('user_answers', {})
    
    score = 0
    correct_count = 0
    incorrect_count = 0
    
    topic_breakdown = defaultdict(lambda: {'correct': 0, 'incorrect': 0, 'total': 0})

    for i, q in enumerate(all_questions):
        subject_abbr = SUBJECT_MAP.get(q.get('subject'), 'Unknown')
        topic = f"{subject_abbr} -> {q.get('chapter', 'General')}"
        topic_breakdown[topic]['total'] += 1
        
        answer_info = user_answers.get(str(i))
        if answer_info:
            if answer_info['is_correct']:
                correct_count += 1
                topic_breakdown[topic]['correct'] += 1
            else:
                incorrect_count += 1
                topic_breakdown[topic]['incorrect'] += 1

    score = correct_count
    total = len(all_questions)
    accuracy = (score / total * 100) if total > 0 else 0
    total_time_taken = time.time() - session.get('start_time', 0)

    report_data = {
        'student_name': 'User',
        'score': score,
        'total_questions': total,
        'accuracy': round(accuracy, 2),
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
        'unanswered_count': total - (correct_count + incorrect_count),
        'total_time_taken': round(total_time_taken),
        'topic_breakdown': dict(topic_breakdown)
    }

    session.clear()

    return render_template('results.html', 
                         score=score, 
                         total=total,
                         report_data_json=json.dumps(report_data))


@app.route('/report', methods=['POST'])
def report_page():
    report_data_str = request.form.get('report_data')
    if not report_data_str:
        return "Error: No report data found.", 400
        
    report_data = json.loads(report_data_str)

    # Call our agent to get the report as a Markdown string
    agent_response = run_graph_agent(report_data)
    
    # Convert the Markdown string from the agent into HTML
    report_html = markdown.markdown(agent_response.get("analysis", ""))
    
    # Pass the generated HTML to the template
    return render_template('report.html', 
                           report_data=report_data, 
                           report_html=report_html) # Pass HTML, not text

def generate_questions(subject, difficulty, num_questions):
    subject_instructions = {
        "Logical Reasoning": "Chapters may include: Syllogisms, Blood Relations, Coding-Decoding, Seating Arrangement, Direction Sense.",
        "Quantitative Aptitude": "Chapters may include: Time & Work, Percentages, Profit & Loss, Speed Time & Distance, Ratios.",
        "Verbal Ability": "Chapters may include: Synonyms & Antonyms, Reading Comprehension, Sentence Correction, Para Jumbles, Idioms & Phrases."
    }
    prompt = f"""
    Generate exactly {num_questions} multiple choice questions (MCQ) about {subject} with {difficulty.lower()} difficulty,
    focused on engineering placement scenarios in Indian B.Tech colleges like those asked by companies like Infosys, Wipro, TCS.
    {subject_instructions.get(subject, '')}

    For each question, provide:
    1. The question text.
    2. A specific chapter or topic name for the question (e.g., "Time & Work", "Syllogisms").
    3. Four options labeled A), B), C), D).
    4. The correct answer letter.
    5. A detailed step-by-step solution.

    Format EACH question as a JSON object like this:
    {{
        "chapter": "Chapter Name Here",
        "question": "Question text here",
        "options": {{ "A": "option 1", "B": "option 2", "C": "option 3", "D": "option 4" }},
        "correct_answer": "Correct letter here",
        "solution": "Detailed step-by-step solution here"
    }}

    Return ONLY a JSON array of these questions with the key "questions". Do not include any other text or explanations.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            temperature=0.7
        )
        response = chat_completion.choices[0].message.content
        questions = json.loads(response).get('questions', [])
        
        if len(questions) < num_questions:
            needed = num_questions - len(questions)
            questions.extend(get_default_questions(subject, needed))
            
        return questions[:num_questions]
    
    except Exception as e:
        return get_default_questions(subject, num_questions)

def get_default_questions(subject, num_questions):
    defaults = {
        "Logical Reasoning": [{"chapter": "Syllogisms", "question": "If all Bloops are Razzies and all Razzies are Lazzies, then all Bloops are definitely Lazzies?", "options": {"A": "True", "B": "False", "C": "Uncertain", "D": "None of the above"}, "correct_answer": "A", "solution": "This is a case of transitive relation. If A implies B and B implies C, then A implies C. So, the statement is True."}],
        "Quantitative Aptitude": [{"chapter": "Speed, Time & Distance", "question": "If a train travels 300 km in 5 hours, what is its average speed?", "options": {"A": "50 km/h", "B": "60 km/h", "C": "70 km/h", "D": "80 km/h"}, "correct_answer": "B", "solution": "Average Speed = Total Distance / Total Time. Speed = 300 km / 5 hours = 60 km/h."}],
        "Verbal Ability": [{"chapter": "Synonyms", "question": "Choose the correct synonym for 'Benevolent'", "options": {"A": "Cruel", "B": "Kind", "C": "Selfish", "D": "Greedy"}, "correct_answer": "B", "solution": "'Benevolent' means well-meaning and kindly. 'Kind' is the closest synonym."}]
    }
    subject_questions = defaults.get(subject, [])
    return subject_questions[:num_questions]


if __name__ == '__main__':
    app.run(debug=True)

