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

def get_sort_query(sort_type):
    if sort_type == 'oldest':
        return [('created_at', 1)]
    elif sort_type == 'popular':
        return [('total_count', -1), ('created_at', -1)]
    else:
        return [('created_at', -1)]

@app.route('/')
def home():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({"email": payload['email']}, {'_id': False})
        user_email = payload['email']
        
        # 파라미터 읽기
        sort_type = request.args.get('sort', 'newest')
        view_type = request.args.get('view', 'all')
        
        # 필터 조건 설정
        query = {"trash": True} # 기본적으로 진행 중인 것만
        if view_type == 'mine':
            query["created_by"] = user_email
            
        sort_query = get_sort_query(sort_type)
        
        # 파이프라인 수정 ($trash 오타 및 조건 수정)
        pipeline = [
            {"$match": query},
            {"$addFields": {"total_count": {"$add": ["$left_count", "$right_count"]}}},
            {"$sort": dict(sort_query)},
            {"$limit": 10}
        ]
        topics = list(db.topics.aggregate(pipeline))
        
        # 현재 유저의 투표 기록을 가져와서 딕셔너리화 (ID: 선택항목)
        user_votes = list(db.votes.find({"user_email": user_email}))
        voted_dict = {v['topic_id']: v['selected'] for v in user_votes}
        
        live_topics = []
        now = datetime.datetime.now()

        for t in topics:
            t['_id'] = str(t['_id'])
            # 만료 시간 계산 (30초는 테스트용으로 보임)
            t['expire_at'] = t['created_at'] + datetime.timedelta(hours=30)
            
            # 만료 체크 및 처리
            if now >= t['expire_at']: 
                db.topics.update_one({"_id": ObjectId(t['_id'])}, {"$set": {"trash": False}})
                continue # 만료된 것은 live_topics에 넣지 않음

            # 프론트엔드에서 필요한 '내가 투표한 정보' 주입
            t['user_voted'] = voted_dict.get(t['_id'], None)

            # 댓글 조회 (필요 시)
            comments = list(db.comments.find({'topic_id': t['_id']}))
            for c in comments:
                c['_id'] = str(c['_id'])
            t['comments'] = comments
            
            live_topics.append(t)

        return render_template('index.html', user_info=user_info, topics=live_topics, sort_now=sort_type, view_now=view_type)
    except Exception as e:
        print(f"Error: {e}")
        return redirect(url_for('login'))

@app.route('/api/get_topics', methods=['GET'])
def get_more_topics():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_email = payload['email']

        skip_receive = int(request.args.get('skip', 0))
        sort_type = request.args.get('sort', 'newest')
        view_type = request.args.get('view', 'all')
        
        query = {"trash": True}
        if view_type == 'mine':
            query["created_by"] = user_email
            
        sort_query = get_sort_query(sort_type)

        pipeline = [
            {"$match": query},
            {"$addFields": {"total_count": {"$add": ["$left_count", "$right_count"]}}},
            {"$sort": dict(sort_query)},
            {"$skip": skip_receive},
            {"$limit": 10}
        ]
        topics = list(db.topics.aggregate(pipeline))
        
        # 투표 정보 매핑
        user_votes = list(db.votes.find({"user_email": user_email}))
        voted_dict = {v['topic_id']: v['selected'] for v in user_votes}

        live_topics = []
        for t in topics:
            t['_id'] = str(t['_id'])
            t['user_voted'] = voted_dict.get(t['_id'], None)
            live_topics.append(t)

        return jsonify({'result': 'success', 'topics': live_topics})
    except:
        return jsonify({'result': 'fail', 'msg': '인증 오류'})

@app.route('/api/vote', methods=['POST'])
def vote():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_email = payload['email']
        topic_id = request.form['topic_id']
        option = request.form['option']
        
        # 1. 기존 투표 확인 (수정 불가 조건)
        existing_vote = db.votes.find_one({'user_email': user_email, 'topic_id': topic_id})
        
        if existing_vote:
            # 이미 투표했다면 실패 응답 반환
            return jsonify({'result': 'fail', 'msg': '이미 투표에 참여하셨습니다. 투표는 수정할 수 없습니다.'})
        
        # 2. 신규 투표 진행
        db.votes.insert_one({
            'user_email': user_email, 
            'topic_id': topic_id, 
            'selected': option,
            'voted_at': datetime.datetime.now()
        })
        
        field = 'left_count' if option == 'left' else 'right_count'
        db.topics.update_one({'_id': ObjectId(topic_id)}, {'$inc': {field: 1}})
        
        return jsonify({'result': 'success', 'msg': '투표가 완료되었습니다!'})
    except Exception as e:
        return jsonify({'result': 'fail', 'msg': '인증이 만료되었거나 오류가 발생했습니다.'}), 403

# --- 이하 기존 코드 유지 (Signup, Login, Comment 등) ---

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
            'created_at': datetime.datetime.now(),
            'trash': True
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

@app.route('/api/get_comments', methods=['GET'])
def get_comments():
    topic_id = request.args.get('topic_id')
    comments = list(db.comments.find({'topic_id': topic_id}))
    for c in comments:
        c['_id'] = str(c['_id'])    
    return jsonify({'result': 'success', 'comments': comments})

if __name__ == '__main__':
    if db.topics.count_documents({'left_item': '전공자'}) == 0:
        db.topics.insert_one({
            'left_item': '전공자',
            'right_item': '비전공자',
            'left_count': 0,
            'right_count': 0,
            'created_at': datetime.datetime.now(),
            'trash': True
        })
        
    if db.topics.count_documents({'left_item': 'Windows'}) == 0:
        db.topics.insert_one({
            'left_item': 'Windows',
            'right_item': 'Mac',
            'left_count': 0,
            'right_count': 0,
            'created_at': datetime.datetime.now(),
            'trash': True
        })

    if db.topics.count_documents({'left_item': '개발자'}) == 0:
        db.topics.insert_one({
            'left_item': '개발자',
            'right_item': '비개발자',
            'left_count': 0,
            'right_count': 0,
            'created_at': datetime.datetime.now(),
            'trash': True
        })

    if db.topics.count_documents({'left_item': 'Android'}) == 0:
        db.topics.insert_one({
            'left_item': 'Android',
            'right_item': 'iOS',
            'left_count': 0,
            'right_count': 0,
            'created_at': datetime.datetime.now(),
            'trash': True
        })

    if db.topics.count_documents({'left_item': '혼자 몰입'}) == 0:
        db.topics.insert_one({
            'left_item': '혼자 몰입',
            'right_item': '같이 협업',
            'left_count': 0,
            'right_count': 0,
            'created_at': datetime.datetime.now(),
            'trash': True
        })

    if db.topics.count_documents({'left_item': '프론트엔드'}) == 0:
        db.topics.insert_one({
            'left_item': '프론트엔드',
            'right_item': '백엔드',
            'left_count': 0,
            'right_count': 0,
            'created_at': datetime.datetime.now(),
            'trash': False
        })
    app.run('0.0.0.0', port=5001, debug=True)