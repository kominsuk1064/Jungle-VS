import jwt
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

SECRET_KEY = 'JUNGLE_SECRET_6'
client = MongoClient('mongodb://localhost:27017/')
db = client.dbjungle


@app.route('/')
def home():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({"email": payload['email']}, {'_id': False})
        
        topics = list(db.topics.find({}).sort('created_at', -1))
        
        for t in topics:
            t['_id'] = str(t['_id'])
            
        return render_template('index.html', user_info=user_info, topics=topics)
    except:
        return redirect(url_for('login'))

@app.route('/api/topic', methods=['POST'])
def create_topic():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        left = request.form['left']
        right = request.form['right']
        
        db.topics.insert_one({
            'left_item': left,
            'right_item': right,
            'left_count': 0,
            'right_count': 0,
            'created_by': payload['email'],
            'created_at': datetime.datetime.now()
        })
        return jsonify({'result': 'success', 'msg': '주제가 생성되었습니다!'})
    except:
        return jsonify({'result': 'fail', 'msg': '로그인이 필요합니다.'}), 403

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')


@app.route('/api/signup', methods=['POST'])
def signup_post():
    email = request.form['username']
    password = request.form['password']
    nickname = request.form['nickname']
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    if db.users.find_one({'email': email}):
        return jsonify({'result': 'fail', 'msg': '이미 존재하는 이메일입니다.'})

    db.users.insert_one({
        'email': email,
        'password': hashed_password,
        'nickname': nickname
    })
    return jsonify({'result': 'success', 'msg': '회원가입 완료!'})

@app.route('/api/login', methods=['POST'])
def login_post():
    email = request.form['username']
    password = request.form['password']

    user = db.users.find_one({'email': email})

    # 1) 아이디로 DB를 서칭, 없을시 실패 얼럿
    if not user : 
        return jsonify({'result': 'fail', 'msg':'존재하지 않는 ID입니다.'})

    # 2번) 비밀번호가 일치하지 않을 시 
    if not check_password_hash(user.get('password'), password):
        return jsonify({'result': 'fail', 'msg':'비밀번호가 틀립니다.'})

    #로그인 성공시 토큰 발급 
    payload = {
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return jsonify({'result': 'success', 'token': token})


@app.route('/api/vote', methods=['POST'])
def vote():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_email = payload['email']
        topic_id = request.form['topic_id']
        option = request.form['option']
        
        if db.votes.find_one({'user_email': user_email, 'topic_id': topic_id}):
            return jsonify({'msg': '이미 투표에 참여하셨습니다.'})
        
        db.votes.insert_one({'user_email': user_email, 'topic_id': topic_id, 'selected': option})
        
        field = 'left_count' if option == 'left' else 'right_count'
        db.topics.update_one({'_id': ObjectId(topic_id)}, {'$inc': {field: 1}})
        
        return jsonify({'result': 'success', 'msg': '투표 성공!'})
    except:
        return jsonify({'msg': '인증 만료'}), 403

@app.route('/api/comment', methods=['POST'])
def post_comment():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        db.comments.insert_one({
            'user_email': payload['email'],
            'topic_id': request.form['topic_id'],
            'content': request.form['comment'],
            'created_at': datetime.datetime.now()
        })
        return jsonify({'result': 'success'})
    except:
        return jsonify({'msg': '로그인 필요'}), 403
    
@app.route('/make_topic_page')
def make_topic_page():
    return render_template('make_topic.html')

if __name__ == '__main__':
    if db.topics.count_documents({'left_item': '전공자'}) == 0:
        db.topics.insert_one({
            'left_item': '전공자', 
            'right_item': '비전공자',
            'left_count': 0, 
            'right_count': 0,
            'created_at': datetime.datetime.now()
        })
        
    if db.topics.count_documents({'left_item': 'Windows'}) == 0:
        db.topics.insert_one({
            'left_item': 'Windows', 
            'right_item': 'Mac',
            'left_count': 0, 
            'right_count': 0,
            'created_at': datetime.datetime.now()
        })
    
    if db.topics.count_documents({'left_item': '개발자'}) == 0:
        db.topics.insert_one({
            'left_item': '개발자', 
            'right_item': '비개발자',
            'left_count': 0, 
            'right_count': 0,
            'created_at': datetime.datetime.now()
        })
        
    if db.topics.count_documents({'left_item': 'Android'}) == 0:
        db.topics.insert_one({
            'left_item': 'Android', 
            'right_item': 'iOS',
            'left_count': 0, 
            'right_count': 0,
            'created_at': datetime.datetime.now()
        })

    if db.topics.count_documents({'left_item': '혼자 몰입'}) == 0:
        db.topics.insert_one({
            'left_item': '혼자 몰입', 
            'right_item': '같이 협업',
            'left_count': 0, 
            'right_count': 0,
            'created_at': datetime.datetime.now()
        })
        
    if db.topics.count_documents({'left_item': '프론트엔드'}) == 0:
        db.topics.insert_one({
            'left_item': '프론트엔드', 
            'right_item': '백엔드',
            'left_count': 0, 
            'right_count': 0,
            'created_at': datetime.datetime.now()
        })
        
    app.run('0.0.0.0', port=5001, debug=True)