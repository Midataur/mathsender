from flask import Flask, request, url_for, render_template, make_response
from flask_socketio import SocketIO, join_room, leave_room
from collections import defaultdict
import json
import random
from datetime import datetime


classrooms = defaultdict(lambda: None)

app = Flask(__name__)
app.config['DEBUG'] = True if __name__ == '__main__' else False
socketio = SocketIO(app)

#this one is just for heroku
def create_app():
    global app
    return app

def valid_code(code):
    global classrooms
    try:
        code = int(code)
    except ValueError:
        return False
    return code in classrooms

def fetch_answer(answers,name):
    for x in answers:
        if x['submitted_by'] == name:
             return x
    return None

### SOCKETS ###

@socketio.on('room_connect')
def connect(code):
    join_room(code)
    questions = list(classrooms[int(code)]['questions'].values())
    num_studs = len(classrooms[int(code)]['students'])
    print('New connection from',code)
    socketio.emit('question_list',questions,room=code)
    socketio.emit('current_student_count',num_studs,room=code)

@socketio.on('request_answers')
def send_answers(code,qid):
    answers = classrooms[int(code)]['questions'][int(qid)]['answers']
    socketio.emit('answers_list',answers,room=code)

@socketio.on('new_answer')
def new_answer(name,answer_text,code,qid):
    global classrooms
    room = classrooms[int(code)]
    question = room['questions'][int(qid)]
    answers = question['answers']
    
    # Remove an answer from the same person
    if answer := fetch_answer(answers,name):
        answers.remove(answer)
    
    # Create the new answer
    answer = {
            'submitted_by': name,
            'answer': '\\('+answer_text+'\\)', # Latex Formatting
            'correct': None
        }
    print(answer)
    answers.append(answer)

    # Send out to the teacher page
    socketio.emit(
        'new_answer_teacher',
        {'answer': answer, 'qid': qid},
        room=code,
        broadcast=True
    )

    # Autocorrect the new answer
    autocorrect(answer,None,code,qid)
    

@socketio.on('new_question')
def new_question(question_text,code,password):
    global classrooms
    print(question_text,code,password)
    room = classrooms[int(code)]
    if room['password'] == password:
        question = {
            'text': question_text,
            'id': room['curqid']+1,
            'answers': [],
            'corrections': {
                'correct': [],
                'incorrect': []
            }
        }
        room['curqid'] += 1
        room['questions'][room['curqid']] = question
        # Send out to the student page
        socketio.emit(
            'new_question_client',
            [question_text,room['curqid']],
            room=code,
            broadcast=True
            
        )

@socketio.on('edit_question')
def edit_question(question_text,code,password,qid):
    room = classrooms[int(code)]
    question = room['questions'][int(qid)]
    if password == room['password']:
        question['text'] = question_text
    socketio.emit(
        'changed_question',
        [qid,question_text],
        room=code,
        broadcast=True
    )

#I'm rewriting this to be a bit better and have less bugs -max
@socketio.on('autocorrect')
def autocorrect(new_answer,correct,code,qid):

    question = classrooms[int(code)]['questions'][int(qid)]
    answers = question['answers']
    correct_answers = question['corrections']['correct']
    incorrect_answers = question['corrections']['incorrect']

    # the way you had it you couldn't change an answer from incorrect to correct
    if correct == True:
        if new_answer['answer'] in correct_answers: #if already marked correct, do nothing
            return None
        
        if new_answer['answer'] in incorrect_answers: #if already marked incorrect
            incorrect_answers.remove(new_answer['answer'])

        correct_answers.append(new_answer['answer'])

    elif correct == False:
        if new_answer['answer'] in incorrect_answers: #if already marked incorrect, do nothing
            return None
        
        if new_answer['answer'] in correct_answers: #if already marked correct
            correct_answers.remove(new_answer['answer'])

        incorrect_answers.append(new_answer['answer'])
    
    #actual correcting part
    #yes this is still linear time but at least it's clean now
    # I don't think you can do it not in linear time
    for answer in answers:
        if answer['answer'] in question['corrections']['correct']:
            answer['correct'] = True
            send_mark('mark_correct',answer,qid,code)
        elif answer['answer'] in question['corrections']['incorrect']:
            answer['correct'] = False
            send_mark('mark_incorrect',answer,qid,code)

def send_mark(protocol,answer,qid,code):
    socketio.emit(
        protocol,
        {'answer': answer, 'qid': qid},
        room=code,
        broadcast=True
    )

### ROUTES ###

@app.route('/')
def main():
    return render_template('index.html')

@app.route('/teacher/home')
def teacher_main():
    return render_template('teachermain.html')

@app.route('/teacher/join',methods=['POST'])
def teacher_join():
    global classrooms
    code = request.form['code']
    password = request.form['password']
    if valid_code(code):
        if password == classrooms[int(code)]['password']:
            return f'<script>window.location = "/teacher/room/{code}?password={password}"</script>'
        else:
            return 'Invalid password'
    else:
        return 'Invalid code'

@app.route('/teacher/create',methods=['POST'])
def teacher_create():
    global classrooms
    code = random.randint(100000,999999)
    password = request.form['password']
    classrooms[code] = {
        'password': password,
        'questions': {},
        'curqid': 0,
        'students': []
    }
    
    qfile = request.files['questions']
    questions = qfile.read().decode()
    if questions:
        questions = json.loads(questions)
        questions = {int(key): value for key, value in questions.items()}
        classrooms[code]['questions'] = questions
        
    return f'<script>window.location = "/teacher/room/{code}?password={password}"</script>'

@app.route('/teacher/room/<code>')
def teacher_room(code):
    global classrooms
    if valid_code(code):
        password = request.args.get('password')
        return render_template(
            'teacherview.html',
            code=code,
            password=password
        )
    else:
        return 'Invalid code'

@app.route('/teacher/room/<code>/questions/<qid>')
def teacher_question(code,qid):
    global classrooms
    password = request.args.get('password')
    #sanity checks
    if valid_code(code):
        room = classrooms[int(code)]
        if qid.isdigit() and int(qid) in room['questions']:
            if password == room['password']:
                #checks passed, render
                question = room['questions'][int(qid)]
                return render_template('teacherquestion.html', question=question, code=code, password=password)
            else:
                return 'Wrong room password'
        else:
            return 'Invalid question code'
    else:
        return 'Invalid room code'

@app.route('/student/room/<code>')
def student_room(code):
    global classrooms
    name = request.args.get('name')
    if valid_code(code):
        room = classrooms[int(code)]
        if name not in room['students']:
            room['students'].append(name)
        return render_template(
            'studentview.html',
            name=name,
            code=code
        )
    else:
        return 'Invalid code'

@app.route('/student/join',methods=['GET','POST'])
def student_join():
    global classrooms
    if request.method == 'GET':
        return render_template('studentjoin.html')
    else:
        code = request.form['code']
        name = request.form['name']
        room = classrooms[int(code)]
        if not room:
            return 'Invalid code. Check that you typed it correctly'
        return f'<script>window.location = "/student/room/{code}?name={name}"</script>'

@app.route('/student/room/<code>/questions/<qid>')
def student_question(code,qid):
    global classrooms
    name = request.args.get('name')
    #sanity checks
    if valid_code(code):
        room = classrooms[int(code)]
        if qid.isdigit() and int(qid) in room['questions']:
            question = room['questions'][int(qid)]
            answer = fetch_answer(question['answers'],name)
            #sanitization
            if answer:
                tmp_answer = dict(answer)
                print('Sanitizing worked:',tmp_answer is not answer)
                tmp_answer['answer'] = tmp_answer['answer'].replace('\\','\\\\')
                answer = tmp_answer
            return render_template(
                'studentquestion.html',
                question=question,
                answer=answer, 
                code=code,
                name=name
            )
        else:
            return ''
    else:
        return 'Invalid room code'
@app.route("/about")
def aboutPage():
    cData = ""
    with open('changelog/changelog.json') as f:
        cData = json.load(f)
    return render_template('about.html', changelogData=cData)

@app.route('/export',methods=["POST"])
def export_questions():
    global classrooms
    room = classrooms[int(request.form['code'])]
    password = request.form['password']
    if room['password'] == password:
        questions = dict(room['questions'])
        for key in questions.keys():
            questions[key]['answers'] = []
        data = json.dumps(questions)
        response = make_response(data)
        file_name = f"questions-{datetime.date(datetime.now())}.MathSender.json"
        response.headers["Content-Type"] = "application/json"
        response.headers["Content-Disposition"] = f"attachment; filename={file_name}"
        return response
    return "Wrong password!"

print(app.url_map)

if __name__ == '__main__':
    @app.route('/debug')
    def debug():
        global classrooms
        0/0
    socketio.run(create_app(),host='0.0.0.0')
