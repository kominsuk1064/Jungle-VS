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

# 정렬 쿼리를 생성하는 헬퍼 함수
def get_sort_query(sort_type):
    if sort_type == 'oldest':
        return [('created_at', 1)]
    elif sort_type == 'popular':
        # 투표 합계(left_count + right_count) 기준 내림차순, 같으면 최신순
        return [('total_count', -1), ('created_at', -1)]
    else:  # newest 또는 기본값
        return [('created_at', -1)]

@app.route('/')
def home():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({"email": payload['email']}, {'_id': False})
        
        # 정렬 기준 파라미터 (기본값: newest)
        sort_type = request.args.get('sort', 'newest')
        sort_query = get_sort_query(sort_type)
        
        # total_count 필드를 임시로 만들어 정렬
        pipeline = [
            {"$addFields": {"total_count": {"$add": ["$left_count", "$right_count"]}}},
            {"$sort": dict(sort_query)},
            {"$limit": 10}
        ]
        topics = list(db.topics.aggregate(pipeline))
        
        for t in topics:
            t['_id'] = str(t['_id'])
            
        return render_template('index.html', user_info=user_info, topics=topics, sort_now=sort_type)
    except:
        return redirect(url_for('login'))

@app.route('/api/get_topics', methods=['GET'])
def get_more_topics():
    skip_receive = int(request.args.get('skip', 0))
    sort_type = request.args.get('sort', 'newest')
    limit_count = 10
    sort_query = get_sort_query(sort_type)

    pipeline = [
        {"$addFields": {"total_count": {"$add": ["$left_count", "$right_count"]}}},
        {"$sort": dict(sort_query)},
        {"$skip": skip_receive},
        {"$limit": limit_count}
    ]
    topics = list(db.topics.aggregate(pipeline))
    
    for t in topics:
        t['_id'] = str(t['_id'])
        
    return jsonify({'result': 'success', 'topics': topics})

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
    rePassword = request.form['rePassword']
    
    if db.users.find_one({'email': email}):
        return jsonify({'result': 'fail', 'msg': '이미 존재하는 이메일입니다.'})
    
    if password != rePassword :
        return jsonify({'result': 'fail', 'msg': '비밀번호가 일치하지 않습니다!'})
    
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
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

    if not user : 
        return jsonify({'result': 'fail', 'msg':'존재하지 않는 ID입니다.'})

    if not check_password_hash(user.get('password'), password):
        return jsonify({'result': 'fail', 'msg':'비밀번호가 틀립니다.'})

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
    app.run('0.0.0.0', port=5001, debug=True)