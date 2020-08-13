from flask import Flask, request, url_for, render_template
from flask_socketio import SocketIO
from collections import defaultdict
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hippityhoppitygetoffmyproperty'
socketio = SocketIO(app)

classrooms = defaultdict(lambda: None)

def valid_code(code):
    global classrooms
    try:
        code = int(code)
    except ValueError:
        return False
    return code in classrooms

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
        return f'<script>window.location = "/teacher/room/{code}?password={password}"</script>'
    else:
        return 'Invalid code'

@app.route('/teacher/create',methods=['POST'])
def teacher_create():
    global classrooms
    code = random.randint(100000,999999)
    password = request.form['password']
    classrooms[code] = {
        'password': password,
        'questions': []
    }
    return f'<script>window.location = "/teacher/room/{code}?password={password}"</script>'

@app.route('/teacher/room/<code>')
def teacher_room(code):
    global classrooms
    if valid_code(code):
        return render_template('teacherview.html',code=code)
    else:
        return 'Invalid code'

@app.route('/student/room/<code>')
def student_room(code):
    global classrooms
    if valid_code(code):
        return render_template('studentview.html')
    else:
        return 'Invalid code'

@app.route('/student/join',methods=['GET','POST'])
def student_join():
    if request.method == 'GET':
        return render_template('studentjoin.html')
    else:
        code = request.form['code']
        return f'<script>window.location = "/student/room/{code}"</script>'

@app.route('/debug')
def debug():
    global classrooms
    return str(classrooms)

if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0')