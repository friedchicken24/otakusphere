from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db # Import db từ app package

# Bảng nối nhiều-nhiều cho post_genres
post_genres_table = db.Table('post_genres',
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    role = db.Column(db.String(20), default='user', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    posts = db.relationship('Post', backref='author_user', lazy='dynamic', cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='author_user', lazy='dynamic', cascade="all, delete-orphan")
    likes = db.relationship('PostLike', back_populates='user', cascade="all, delete-orphan")
    
    sent_friend_requests = db.relationship('Friendship',
                                           foreign_keys='Friendship.user_id',
                                           backref='requester', lazy='dynamic',
                                           cascade="all, delete-orphan")
    received_friend_requests = db.relationship('Friendship',
                                               foreign_keys='Friendship.friend_id',
                                               backref='receiver', lazy='dynamic',
                                               cascade="all, delete-orphan")
    notifications_received = db.relationship('Notification',
                                             foreign_keys='Notification.user_id',
                                             backref='recipient_user', lazy='dynamic',
                                             cascade="all, delete-orphan")
    notifications_acted = db.relationship('Notification',
                                         foreign_keys='Notification.actor_id',
                                         backref='actor_user', lazy='dynamic') # No cascade for actor

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'
    
    def send_friend_request(self, recipient_user):
        if not self.has_sent_request_to(recipient_user) and \
           not recipient_user.has_sent_request_to(self) and \
           self.id != recipient_user.id and \
           not self.is_friends_with(recipient_user):
            friendship = Friendship(user_id=self.id, friend_id=recipient_user.id, status='pending')
            db.session.add(friendship)
            return friendship
        return None

    def accept_friend_request(self, requester_user):
        friendship = Friendship.query.filter_by(user_id=requester_user.id, friend_id=self.id, status='pending').first()
        if friendship:
            friendship.status = 'accepted'
            return friendship
        return None

    def decline_friend_request(self, requester_user):
        friendship = Friendship.query.filter_by(user_id=requester_user.id, friend_id=self.id, status='pending').first()
        if friendship:
            db.session.delete(friendship)
            return True
        return False
    
    def unfriend(self, friend_user):
        deleted_count = 0
        f1 = Friendship.query.filter(
            ((Friendship.user_id == self.id) & (Friendship.friend_id == friend_user.id) | \
             (Friendship.user_id == friend_user.id) & (Friendship.friend_id == self.id)) & \
            (Friendship.status == 'accepted')
        ).first() # Chỉ cần tìm một record đại diện cho mối quan hệ accepted
        
        if f1:
            db.session.delete(f1)
            deleted_count +=1
        
        # Nếu bạn có logic tạo 2 record cho friendship, thì xóa cả record còn lại
        # f2 = Friendship.query.filter_by(user_id=friend_user.id, friend_id=self.id, status='accepted').first()
        # if f2 and f1 != f2: # Đảm bảo không xóa cùng record 2 lần nếu chỉ có 1 record
        #     db.session.delete(f2)
        #     deleted_count +=1
        return deleted_count > 0

    def is_friends_with(self, other_user):
        return Friendship.query.filter(
            ((Friendship.user_id == self.id) & (Friendship.friend_id == other_user.id) | \
             (Friendship.user_id == other_user.id) & (Friendship.friend_id == self.id)) & \
            (Friendship.status == 'accepted')
        ).first() is not None

    def has_sent_request_to(self, other_user):
        return Friendship.query.filter_by(user_id=self.id, friend_id=other_user.id, status='pending').first() is not None

    def has_received_request_from(self, other_user):
        return Friendship.query.filter_by(user_id=other_user.id, friend_id=self.id, status='pending').first() is not None

    def get_friends(self):
        friends = []
        # Lấy các user_id của bạn bè từ các mối quan hệ 'accepted'
        # Trường hợp user_id của mình là người gửi
        friend_ids_as_requester = db.session.query(Friendship.friend_id).filter(
            Friendship.user_id == self.id, Friendship.status == 'accepted'
        ).all()
        # Trường hợp user_id của mình là người nhận
        friend_ids_as_receiver = db.session.query(Friendship.user_id).filter(
            Friendship.friend_id == self.id, Friendship.status == 'accepted'
        ).all()

        all_friend_ids = {fid[0] for fid in friend_ids_as_requester}
        all_friend_ids.update({fid[0] for fid in friend_ids_as_receiver})

        if all_friend_ids:
            friends = User.query.filter(User.id.in_(all_friend_ids)).all()
        return friends
    
    def get_pending_friend_requests(self): # Các request người khác gửi cho mình
        return Friendship.query.filter_by(friend_id=self.id, status='pending').all()

    def add_notification(self, actor, type, content, link=None, source_entity_id=None, source_entity_type=None):
        actor_id_val = actor.id if actor else None
        notif = Notification(user_id=self.id, actor_id=actor_id_val, type=type,
                             content=content, link=link,
                             source_entity_id=source_entity_id,
                             source_entity_type=source_entity_type)
        db.session.add(notif)
        return notif

    def unread_notification_count(self):
        # Đảm bảo notifications_received là lazy='dynamic'
        return self.notifications_received.filter_by(is_read=False).count()

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ĐÃ XÓA: image_filename và video_filename

    comments = db.relationship('Comment', backref='post_ref', lazy='dynamic', cascade="all, delete-orphan")
    genres = db.relationship('Genre', secondary=post_genres_table, lazy='subquery',
                             backref=db.backref('posts_ref', lazy=True))
    likes = db.relationship('PostLike', back_populates='post', cascade="all, delete-orphan")
    
    # THÊM MỚI: Mối quan hệ với PostMedia
    media_items = db.relationship('PostMedia', backref='post_ref', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Post {self.title}>'

# THÊM MỚI: Model PostMedia
class PostMedia(db.Model):
    __tablename__ = 'post_media'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False)
    # Sử dụng name='media_type_enum' để SQLAlchemy biết tên của kiểu ENUM trong DB
    media_type = db.Column(db.Enum('image', 'video_file', 'video_embed', name='media_type_enum'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False) 
    thumbnail_path = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # backref 'post_ref' đã được định nghĩa trong Post.media_items
    # Nếu muốn truy cập ngược từ PostMedia -> Post, có thể thêm:
    # post = db.relationship('Post', back_populates='media_items')

    def __repr__(self):
        return f'<PostMedia {self.id} for Post {self.post_id} - Type: {self.media_type}>'


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Comment {self.id}>'

class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Genre {self.name}>'

class PostLike(db.Model):
    __tablename__ = 'post_likes'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='likes')
    post = db.relationship('Post', back_populates='likes')

    def __repr__(self):
        return f'<PostLike User {self.user_id} - Post {self.post_id}>'

class Friendship(db.Model):
    __tablename__ = 'friendships'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    status = db.Column(db.Enum('pending', 'accepted', 'declined', 'blocked', name='friendship_status_enum'),
                       default='pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('user_id <> friend_id', name='ck_friendship_user_id_friend_id'),
    )
    def __repr__(self):
        return f'<Friendship {self.user_id} -> {self.friend_id}: {self.status}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False) 
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL', onupdate='CASCADE'), nullable=True) 
    type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    source_entity_id = db.Column(db.Integer, nullable=True)
    source_entity_type = db.Column(db.String(50), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.id} for {self.user_id}>'