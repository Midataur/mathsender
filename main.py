from flask import Flask, request, url_for, render_template
from flask_socketio import SocketIO
from collections import defaultdict
import random

app = Flask(__name__)
app.config['DEBUG'] = True
socketio = SocketIO(app)

classrooms = defaultdict(lambda: None)

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

@app.route('/')
def main():
    return render_template('index.html')

@app.route('/teacher')
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
        'questions': {}
    }
    classrooms[code]['questions'][1] = {
        'text': 'What is 1+1?',
        'id':1,
        'answers': [
            {
                'submitted_by': 'Jerome',
                'answer': '2'
            },
            {
                'submitted_by': 'The cooler Jerome',
                'answer': '`e^(i pi)+3`'
            }
        ]
    }
    return f'<script>window.location = "/teacher/room/{code}?password={password}"</script>'

@app.route('/teacher/room/<code>')
def teacher_room(code):
    global classrooms
    if valid_code(code):
        password = request.args.get('password')
        questions = list(classrooms[int(code)]['questions'].values())
        return render_template(
            'teacherview.html',
            code=code,
            questions=questions,
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
            print(password,room['password'])
            if password == room['password']:
                #checks passed, render
                question = room['questions'][int(qid)]
                return render_template('teacherquestion.html',question=question, code=code)
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
        questions = list(classrooms[int(code)]['questions'].values())
        return render_template(
            'studentview.html',
            name=name,
            questions=questions,
            code=code
        )
    else:
        return 'Invalid code'

@app.route('/student/join',methods=['GET','POST'])
def student_join():
    if request.method == 'GET':
        return render_template('studentjoin.html')
    else:
        code = request.form['code']
        name = request.form['name']
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
                answer=answer, code=code
            )
        else:
            return ''
    else:
        return 'Invalid room code'

@app.route('/debug')
def debug():
    global classrooms
    return str(classrooms)

if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0')