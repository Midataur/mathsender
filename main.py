from flask import Flask, request, url_for, render_template
from flask_socketio import SocketIO, join_room, leave_room
from collections import defaultdict
import json
import random

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

def fetch_answer(answer_list,author):
    for x in answer_list:
        if x['submitted_by'] == author:
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
    #walrus time?
    if answer := fetch_answer(answers,name):
        answer['answer'] = '\\('+answer_text+'\\)'
    else:
        answer = {
            'submitted_by': name,
            'answer': '\\('+answer_text+'\\)',
            'correct': None
        }
        answers.append(answer)

    # Send out to the teacher page
    socketio.emit(
        'new_answer_teacher',
        {'answer': answer, 'qid': qid},
        room=code,
        broadcast=True
    )

@socketio.on('new_question')
def new_question(question_text,code,password):
    global classrooms
    print(question_text,code,password)
    room = classrooms[int(code)]
    if room['password'] == password:
        question = {
            'text': question_text,
            'id': room['curqid']+1,
            'answers': []
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

@socketio.on('autocorrect')
def autocorrect(clicked_answer,correct,code,qid):
    # if correct is True, the clicked answer is correct
    answers = classrooms[int(code)]['questions'][int(qid)]['answers']
    for i in range(len(answers)):
        if answers[i]['answer'] == clicked_answer['answer']:
            if correct:
                classrooms[int(code)]['questions'][int(qid)]['answers'][i]['correct'] = True
                # Send out to the teacher page
                socketio.emit(
                    'mark_correct',
                    {'answer': answers[i], 'qid': qid},
                    room=code,
                    broadcast=True
                )
            else:
                classrooms[int(code)]['questions'][int(qid)]['answers'][i]['correct'] = False
                socketio.emit(
                    'mark_incorrect',
                    {'answer': answers[i], 'qid': qid},
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
    
    classrooms[code]['questions'][1] = {
        'text': 'What is 1+1?',
        'id':1,
        'answers': [
            {
                'submitted_by': 'Jerome',
                'answer': '2',
                'correct': None,

            },
            {
                'submitted_by': 'Another Jerome',
                'answer': '2',
                'correct': None,

            },
            {
                'submitted_by': 'The cooler Jerome',
                'answer': '`e^(i pi)+3`',
                'correct': None,
            }
        ]
    }
    
    return f'<script>window.location = "/teacher/room/{code}?password={password}"</script>'

@app.route('/teacher/room/<code>')
def teacher_room(code):
    global classrooms
    if valid_code(code):
        password = request.args.get('password')
        questions = list(classrooms[int(code)]['questions'].values())[::-1]
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
                return render_template('teacherquestion.html',question=question, code=code, password=password)
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

print(app.url_map)

if __name__ == '__main__':
    @app.route('/debug')
    def debug():
        global classrooms
        0/0
    socketio.run(create_app(),host='0.0.0.0')