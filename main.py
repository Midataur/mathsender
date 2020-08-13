from flask import Flask, request, url_for, render_template
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hippityhoppitygetoffmyproperty'
socketio = SocketIO(app)

def valid_color(color):
    if color[0] == '#':
        color = color[1:]
        print('took the hashtag off of',color)
    if len(color) != 6:
        print(color,'failed length test')
        return False
    return all([x in '1234567890abcdef' for x in color])

@app.route('/')
def main():
    return render_template('index.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/response')
def colorplace():
    return render_template('response.html')

@socketio.on('change_color')
def change_color(color):
    color = str(color).lower()
    if valid_color(color):
        color = '#'+color
        print('Received color',color,'sending change')
        socketio.emit('broadcast_color',color,broadcast=True)

@socketio.on('connect')
def connection():
    print('New connection!')

@socketio.on('send_message')
def new_message(username,message):
    data = [username,message]
    socketio.emit('message_receive',data,broadcast=True)

if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0')