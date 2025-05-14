from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed # Import FileField và FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectMultipleField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, Optional # Thêm Optional
from app.models import User, Genre

class LoginForm(FlaskForm):
    username_or_email = StringField('Tên đăng nhập hoặc Email', validators=[DataRequired()])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    remember_me = BooleanField('Nhớ đăng nhập')
    submit = SubmitField('Đăng nhập')

class RegistrationForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
    password = PasswordField('Mật khẩu', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField(
        'Nhập lại mật khẩu', validators=[DataRequired(), EqualTo('password', message='Mật khẩu không khớp.')])
    submit = SubmitField('Đăng ký')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Tên đăng nhập này đã được sử dụng.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Địa chỉ email này đã được sử dụng.')

class PostForm(FlaskForm):
    title = StringField('Tiêu đề', validators=[DataRequired(), Length(max=100)])
    content = TextAreaField('Nội dung', validators=[DataRequired()])
    genres = SelectMultipleField('Thể loại', coerce=int, 
                                 validators=[DataRequired(message="Vui lòng chọn ít nhất một thể loại.")])
    
    # Trường để upload ảnh mới
    image_upload = FileField('Thêm ảnh (tùy chọn)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Chỉ cho phép file ảnh (jpg, jpeg, png, gif)!'),
        Optional() # Cho phép trường này trống
    ])
    
    # Trường để upload video mới
    video_upload = FileField('Thêm video (tùy chọn)', validators=[
        FileAllowed(['mp4', 'mov', 'avi', 'mkv', 'webm'], 'Chỉ cho phép file video (mp4, mov, avi, mkv, webm)!'),
        Optional() # Cho phép trường này trống
    ])
    
    # Trường để nhúng URL video
    video_embed_url = StringField('Hoặc nhúng URL video (YouTube, Vimeo, etc. - tùy chọn)', 
                                  validators=[Length(max=255), Optional()])

    submit = SubmitField('Đăng bài')

    def __init__(self, *args, **kwargs):
        super(PostForm, self).__init__(*args, **kwargs)
        # Query tất cả genres để hiển thị trong SelectMultipleField
        self.genres.choices = [(g.id, g.name) for g in Genre.query.order_by('name').all()]

class CommentForm(FlaskForm):
    content = TextAreaField('Bình luận', validators=[DataRequired()])
    submit = SubmitField('Gửi bình luận')

class GenreForm(FlaskForm):
    name = StringField('Tên thể loại', validators=[DataRequired(), Length(max=50)])
    description = TextAreaField('Mô tả (tùy chọn)')
    submit = SubmitField('Lưu thể loại')

    def __init__(self, original_name=None, *args, **kwargs): # Thêm original_name cho edit
        super(GenreForm, self).__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        if name.data != self.original_name: # Chỉ kiểm tra nếu tên đã thay đổi hoặc là form tạo mới
            genre = Genre.query.filter_by(name=name.data).first()
            if genre:
                raise ValidationError('Tên thể loại này đã tồn tại.')