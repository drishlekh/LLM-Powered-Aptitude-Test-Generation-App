



import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv
import time
import random
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key_here')

# Initializing Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Predefined subjects
SUBJECTS = [
    "Logical Reasoning",
    "Quantitative Aptitude",
    "Verbal Ability"
]

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Getting form data
        selected_subjects = request.form.getlist('subjects')
        difficulty = request.form.get('difficulty', 'Medium')
        num_questions = min(int(request.form.get('num_questions', 5)), 30)
        timed_test = request.form.get('timed_test') == 'on'
        dark_mode = request.form.get('dark_mode') == 'on'
        
        # Generate questions only for selected subjects
        questions = []
        if selected_subjects:  # Only proceeds if at least one subject is selected
            questions_per_subject = num_questions // len(selected_subjects)
            remaining_questions = num_questions % len(selected_subjects)
            
            for i, subject in enumerate(selected_subjects):
                # Distribute remaining questions to first few subjects
                q_count = questions_per_subject + (1 if i < remaining_questions else 0)
                subject_questions = generate_questions(subject, difficulty, q_count)
                questions.extend(subject_questions)
        
        # Shuffle questions
        random.shuffle(questions)
        
        # Initialize session variables
        session['questions'] = questions
        session['current_question'] = 0
        session['score'] = 0
        session['timed_test'] = timed_test
        session['dark_mode'] = dark_mode
        session['start_time'] = time.time()
        session['time_per_question'] = 60  # 1 minute per question if timed
        session['answered'] = [False] * len(questions)
        session['visited'] = [False] * len(questions)
        session['selected_subjects'] = selected_subjects
        
        return redirect(url_for('quiz'))
    
    return render_template('index.html', 
                        subjects=SUBJECTS,
                        timed_test=request.form.get('timed_test') == 'on' if request.method == 'POST' else False,
                        dark_mode=request.form.get('dark_mode') == 'on' if request.method == 'POST' else False)

@app.route('/quiz')
def quiz():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    # Mark current question as visited
    current_idx = session['current_question']
    session['visited'][current_idx] = True
    session.modified = True
    
    # Get current question and ensure it has a solution
    current_question = session['questions'][current_idx]
    if 'solution' not in current_question or not current_question['solution']:
        current_question['solution'] = "Detailed solution not available for this question"
        session.modified = True
    
    # Calculate time left
    time_left = None
    if session.get('timed_test', False):
        elapsed = time.time() - session['start_time']
        total_time = len(session['questions']) * session['time_per_question']
        time_left = max(0, total_time - elapsed)
    
    return render_template('quiz.html', 
                        question=current_question,
                        question_num=current_idx + 1,
                        total_questions=len(session['questions']),
                        timed_test=session.get('timed_test', False),
                        dark_mode=session.get('dark_mode', False),
                        time_left=time_left,
                        answered=session['answered'],
                        visited=session['visited'])

@app.route('/check_answer', methods=['POST'])
def check_answer():
    if 'questions' not in session:
        return jsonify({'error': 'Session expired'}), 400
    
    data = request.get_json()
    selected_option = data.get('selected_option')
    current_idx = session['current_question']
    questions = session['questions']
    
    # Update answer status
    session['answered'][current_idx] = True
    session.modified = True
    
    # Check correctness
    current_question = questions[current_idx]
    is_correct = selected_option == current_question['correct_answer']
    if is_correct:
        session['score'] += 1
    
    # Ensure solution exists, if not provide default
    solution = current_question.get('solution')
    if not solution:
        solution = "Solution not available for this question"
    
    # Prepare response
    response_data = {
        'is_correct': is_correct,
        'correct_answer': current_question['correct_answer'],
        'solution': solution,
        'score': session['score'],
        'total_questions': len(questions),
        'answered': session['answered'],
        'visited': session['visited']
    }
    
    # Move to next question if not last
    if current_idx + 1 < len(questions):
        session['current_question'] += 1
        response_data.update({
            'has_next': True,
            'next_question': questions[current_idx + 1],
            'question_num': current_idx + 2
        })
    else:
        response_data['has_next'] = False
    
    # Calculate time left if timed test
    if session.get('timed_test', False):
        elapsed = time.time() - session['start_time']
        total_time = len(questions) * session['time_per_question']
        response_data['time_left'] = max(0, total_time - elapsed)
    
    return jsonify(response_data)

@app.route('/set_question', methods=['POST'])
def set_question():
    if 'questions' not in session:
        return jsonify({'error': 'Session expired'}), 400
    
    data = request.get_json()
    question_num = data.get('question_num', 1)
    
    # Update current question
    session['current_question'] = question_num - 1
    session['visited'][question_num-1] = True
    session.modified = True
    
    return jsonify({
        'question': session['questions'][question_num-1],
        'total_questions': len(session['questions'])
    })

@app.route('/toggle_dark_mode', methods=['POST'])
def toggle_dark_mode():
    session['dark_mode'] = not session.get('dark_mode', False)
    session.modified = True
    return jsonify({'dark_mode': session['dark_mode']})

@app.route('/results')
def results():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    score = session.get('score', 0)
    total = len(session['questions'])
    timed_out = request.args.get('timed_out', 'false') == 'true'
    dark_mode = session.get('dark_mode', False)
    
    # Clear session data
    session.clear()
    
    return render_template('results.html', 
                         score=score, 
                         total=total,
                         timed_out=timed_out,
                         dark_mode=dark_mode)



def generate_questions(subject, difficulty, num_questions):
    # Subject-specific instructions
    subject_instructions = {
        "Logical Reasoning": """
        Generate logical reasoning questions that may include:
        - Syllogisms
        - Logical sequences
        - Pattern recognition
        - Deductive reasoning problems
        - Analytical puzzles
        Do NOT include any mathematical calculations or quantitative problems.
        """,
        "Quantitative Aptitude": """
        Generate quantitative aptitude questions that may include:
        - Arithmetic problems
        - Algebra
        - Geometry
        - Data interpretation
        - Percentage and ratio calculations
        Do NOT include any verbal or logical reasoning questions.
        """,
        "Verbal Ability": """
        Generate verbal ability questions that may include:
        - Synonyms and antonyms
        - Reading comprehension
        - Grammar and sentence correction
        - Vocabulary
        - Para jumbles
        - Idioms and phrases
        Do NOT include any mathematical or logical reasoning questions.
        """
    }

    prompt = f"""
Generate exactly {num_questions} multiple choice questions (MCQ) about {subject} with {difficulty.lower()} difficulty,
focused on engineering placement scenarios in Indian B.Tech colleges. The questions should be very much related 
to that of questions that are being asked by companies like Infosys, Wipro, TCS, HighRadius etc.
if required you may include previous year questions too.

{subject_instructions.get(subject, '')}

For each question, provide:
1. The question text (must be strictly about {subject})
2. Four options labeled A), B), C), D)
3. The correct answer (just the letter)
4. A detailed step-by-step solution explaining how to arrive at the correct answer

Format each question as follows:
{{
    "question": "question text here",
    "options": {{
        "A": "option 1",
        "B": "option 2", 
        "C": "option 3",
        "D": "option 4"
    }},
    "correct_answer": "correct letter here",
    "solution": "Detailed step-by-step solution explaining the reasoning and calculations"
}}

IMPORTANT:
- The questions must be strictly about {subject} only
- Do not include any questions that belong to other subjects
- If generating Verbal Ability questions, do not include any mathematical calculations
- If generating Quantitative Aptitude questions, do not include any verbal or logical reasoning
- If generating Logical Reasoning questions, do not include any mathematical calculations or verbal questions

Return only a JSON array of these questions with the key "questions", nothing else.
"""
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama3-8b-8192",
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        # Parse the response
        response = chat_completion.choices[0].message.content
        questions = json.loads(response).get('questions', [])
        
        # Filter questions to ensure they match the subject
        filtered_questions = []
        for q in questions:
            if is_question_valid(q, subject):
                # Ensure the question has all required fields
                if 'solution' not in q or not q['solution']:
                    q['solution'] = "Detailed solution not available for this question"
                filtered_questions.append(q)
            if len(filtered_questions) >= num_questions:
                break
        
        # If we didn't get enough valid questions, use defaults
        if len(filtered_questions) < num_questions:
            default_qs = get_default_questions(subject, num_questions - len(filtered_questions))
            filtered_questions.extend(default_qs)
        
        return filtered_questions[:num_questions]
    
    except Exception as e:
        print(f"Error generating questions: {e}")
        return get_default_questions(subject, num_questions)
    
    
def is_question_valid(question, subject):
    """Check if a question actually belongs to the requested subject"""
    q_text = question.get('question', '').lower()
    
    # Words that indicate wrong subject
    invalid_words = {
        "Verbal Ability": ["calculate", "percentage", "profit", "loss", "ratio", "sum", "average", "km", "hour"],
        "Quantitative Aptitude": ["synonym", "antonym", "grammar", "sentence", "passage", "reading"],
        "Logical Reasoning": ["calculate", "percentage", "synonym", "antonym", "grammar"]
    }
    
    # Check for invalid words in the question
    for word in invalid_words.get(subject, []):
        if word in q_text:
            return False
    
    return True

def get_default_questions(subject, num_questions):
    defaults = {
        "Logical Reasoning": [
            {
                "question": "If all Bloops are Razzies and all Razzies are Lazzies, then all Bloops are definitely Lazzies?",
                "options": {
                    "A": "True",
                    "B": "False",
                    "C": "Uncertain",
                    "D": "None of the above"
                },
                "correct_answer": "A",
                "solution": "Step 1: Understand the given statements\n- All Bloops are Razzies (Bloops ⊂ Razzies)\n- All Razzies are Lazzies (Razzies ⊂ Lazzies)\n\nStep 2: Apply transitive property\nIf A ⊂ B and B ⊂ C, then A ⊂ C\n\nStep 3: Conclusion\nTherefore, all Bloops are Lazzies (Bloops ⊂ Lazzies)\n\nFinal Answer: A) True"
            }
        ],
        "Quantitative Aptitude": [
            {
                "question": "If a train travels 300 km in 5 hours, what is its average speed?",
                "options": {
                    "A": "50 km/h",
                    "B": "60 km/h",
                    "C": "70 km/h",
                    "D": "80 km/h"
                },
                "correct_answer": "B",
                "solution": "Step 1: Recall the formula for average speed\nAverage Speed = Total Distance / Total Time\n\nStep 2: Plug in the given values\nTotal Distance = 300 km\nTotal Time = 5 hours\n\nStep 3: Calculate\nAverage Speed = 300 km / 5 hours = 60 km/h\n\nStep 4: Match with options\nOption B matches our calculation\n\nFinal Answer: B) 60 km/h"
            }
        ],
        "Verbal Ability": [
            {
                "question": "Choose the correct synonym for 'Benevolent'",
                "options": {
                    "A": "Cruel",
                    "B": "Kind",
                    "C": "Selfish",
                    "D": "Greedy"
                },
                "correct_answer": "B",
                "solution": "Step 1: Understand the word 'Benevolent'\nMeaning: Well-meaning and kindly\n\nStep 2: Analyze options\nA) Cruel - Opposite meaning\nB) Kind - Similar meaning\nC) Selfish - Different meaning\nD) Greedy - Different meaning\n\nStep 3: Select best match\n'Kind' is the closest synonym\n\nFinal Answer: B) Kind"
            },
            {
                "question": "Identify the grammatically correct sentence:",
                "options": {
                    "A": "She don't like apples",
                    "B": "She doesn't likes apples",
                    "C": "She doesn't like apples",
                    "D": "She not like apples"
                },
                "correct_answer": "C",
                "solution": "Step 1: Analyze subject-verb agreement\n- 'She' is third person singular, so it requires 'does' + base verb\n\nStep 2: Evaluate options\nA) Incorrect - 'don't' doesn't agree with 'she'\nB) Incorrect - 'likes' should be base form 'like' after 'does'\nC) Correct - proper subject-verb agreement\nD) Incorrect - missing auxiliary verb\n\nFinal Answer: C) She doesn't like apples"
            }
        ]
    }
    
    subject_questions = defaults.get(subject, [])
    return subject_questions[:num_questions]





if __name__ == '__main__':
    app.run(debug=True)