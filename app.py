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
        
        # 파라미터 읽기
        sort_type = request.args.get('sort', 'newest')
        view_type = request.args.get('view', 'all')
        
        # 필터 조건 설정
        query = {}
        if view_type == 'mine':
            query = {"created_by": payload['email']}
            
        sort_query = get_sort_query(sort_type)
        
        # 파이프라인
        pipeline = [
            {"$match": query},
            {"$addFields": {"total_count": {"$add": ["$left_count", "$right_count"]}}},
            {"$sort": dict(sort_query)},
            {"$limit": 10}
        ]
        topics = list(db.topics.aggregate(pipeline))
        
        live_topics = []
        # 만료시간이 지났다면 DB에서 Trash를 False로 업데이트
        # attach recent comments to each topic
        for t in topics:
            t['expire_at'] = t['created_at'] + datetime.timedelta(seconds=30)         

            if datetime.datetime.now() >= t['expire_at'] : 
                t['trash'] = False
                db.topics.update_one({"_id":t['_id']},{"$set":{"trash":False}})
            
            # Trash 값이 True인 것들만 새로운 리스트에 저장
            if t['trash']:
                t['_id'] = str(t['_id'])
                live_topics.append(t)

            # 댓글 조회
            comments = list(db.comments.find({'topic_id': t['_id']}))
            for c in comments:
                c['_id'] = str(c['_id'])
            t['comments'] = comments      

        return render_template('index.html', user_info=user_info, topics=live_topics, sort_now=sort_type)
    except Exception as e:
       print(e)
    return redirect(url_for('login'))        

    
@app.route('/end_vote_page')
def end_vote_page():
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({"email": payload['email']}, {'_id': False})
        
        topics = list(db.topics.find({"trash":False}).sort('created_at', -1).limit(10))
        
        for t in topics:
            t['_id'] = str(t['_id'])
            
        return render_template('end_vote_page.html', user_info=user_info, topics=topics)
    except:
        return redirect(url_for('login'))

#현재 진행중인 투표에서 더보기 버튼
@app.route('/api/get_topics', methods=['GET'])
def get_more_topics():
    token_receive = request.cookies.get('mytoken')
    payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])

    skip_receive = int(request.args.get('skip', 0))
    sort_type = request.args.get('sort', 'newest')
    view_type = request.args.get('view', 'all')
    
    query = {"created_by": payload['email']} if view_type == 'mine' else {}
    sort_query = get_sort_query(sort_type)

    pipeline = [
        {"$match": query},
        {"$addFields": {"total_count": {"$add": ["$left_count", "$right_count"]}}},
        {"$sort": dict(sort_query)},
        {"$skip": skip_receive},
        {"$limit": 10}
    ]
    topics = list(db.topics.aggregate(pipeline))
    live_topics =[]
    for t in topics:
        t['_id'] = str(t['_id'])
        t['expire_at'] = t['created_at'] + datetime.timedelta(seconds=30)

        if t['trash']:
            t['_id'] = str(t['_id'])
            live_topics.append(t)

    return jsonify({'result': 'success', 'topics': live_topics})


# 이미 끝이 난 투표에서 더보기 버튼
@app.route('/api/get_end_topics', methods=['GET'])
def get_more_end_topics():
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
    live_topics =[]
    for t in topics:
        t['_id'] = str(t['_id'])
        t['expire_at'] = t['created_at'] + datetime.timedelta(seconds=30)

        if not t['trash']:
            t['_id'] = str(t['_id'])
            live_topics.append(t)

    return jsonify({'result': 'success', 'topics': live_topics})

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
        comment_doc = {'user_email': payload['email'], 'topic_id': request.form['topic_id'], 'content': request.form['comment'], 'created_at': datetime.datetime.now()}
        db.comments.insert_one(comment_doc)
        comment_doc['_id'] = str(comment_doc.get('_id', ''))
        return jsonify({'result': 'success', 'comment': comment_doc})
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