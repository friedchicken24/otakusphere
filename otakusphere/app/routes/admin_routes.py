from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Post, Comment, Genre
from app.forms import GenreForm # Thêm các form admin nếu cần
from functools import wraps

bp = Blueprint('admin', __name__)

# Decorator để kiểm tra quyền admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Vui lòng đăng nhập để truy cập trang này.', 'info')
            return redirect(url_for('auth.login', next=request.url))
        if current_user.role != 'admin':
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@admin_required
def dashboard():
    user_count = User.query.count()
    post_count = Post.query.count()
    comment_count = Comment.query.count()
    genre_count = Genre.query.count()
    return render_template('admin/dashboard.html', title='Admin Dashboard',
                           user_count=user_count, post_count=post_count,
                           comment_count=comment_count, genre_count=genre_count)

@bp.route('/users')
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', title='Quản lý người dùng', users=users)

@bp.route('/users/<int:user_id>/toggle_active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id: # Admin không tự vô hiệu hóa mình
        flash('Bạn không thể tự vô hiệu hóa tài khoản của mình.', 'danger')
        return redirect(url_for('admin.list_users'))
    user.is_active = not user.is_active
    db.session.commit()
    status = "kích hoạt" if user.is_active else "vô hiệu hóa"
    flash(f'Đã {status} tài khoản {user.username}.', 'success')
    return redirect(url_for('admin.list_users'))

@bp.route('/users/<int:user_id>/set_role/<new_role>', methods=['POST'])
@admin_required
def set_user_role(user_id, new_role):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id and new_role != 'admin': # Admin không tự hạ quyền mình
        flash('Bạn không thể tự hạ quyền của mình.', 'danger')
        return redirect(url_for('admin.list_users'))
    if new_role not in ['user', 'admin']: # Chỉ cho phép các role hợp lệ
        flash('Role không hợp lệ.', 'danger')
        return redirect(url_for('admin.list_users'))
    user.role = new_role
    db.session.commit()
    flash(f'Đã cập nhật role cho {user.username} thành {new_role}.', 'success')
    return redirect(url_for('admin.list_users'))


@bp.route('/posts')
@admin_required
def list_posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('admin/posts.html', title='Quản lý bài viết', posts=posts)

# Admin có thể dùng route edit/delete post của user_routes nếu có quyền

@bp.route('/genres', methods=['GET', 'POST'])
@admin_required
def list_genres():
    form = GenreForm()
    if form.validate_on_submit():
        genre = Genre(name=form.name.data, description=form.description.data)
        db.session.add(genre)
        try:
            db.session.commit()
            flash('Thể loại mới đã được tạo!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Tên thể loại này đã tồn tại.', 'danger')
        return redirect(url_for('admin.list_genres'))
    
    genres = Genre.query.order_by(Genre.name.asc()).all()
    return render_template('admin/genres.html', title='Quản lý thể loại', genres=genres, form=form)

@bp.route('/genres/<int:genre_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_genre(genre_id):
    genre = Genre.query.get_or_404(genre_id)
    form = GenreForm(obj=genre)
    # Để validate_name hoạt động đúng khi edit, cần xử lý phức tạp hơn
    # hoặc tạo form riêng cho edit. Tạm thời bỏ qua validate_name khi edit.
    # form.name.validators = [v for v in form.name.validators if not isinstance(v, ValidationError)]

    if form.validate_on_submit():
        # Kiểm tra trùng tên thủ công nếu không custom validator
        existing_genre = Genre.query.filter(Genre.name == form.name.data, Genre.id != genre_id).first()
        if existing_genre:
            flash('Tên thể loại này đã tồn tại.', 'danger')
        else:
            genre.name = form.name.data
            genre.description = form.description.data
            db.session.commit()
            flash('Thể loại đã được cập nhật!', 'success')
            return redirect(url_for('admin.list_genres'))
            
    return render_template('admin/edit_genre.html', title='Chỉnh sửa thể loại', form=form, genre=genre)


@bp.route('/genres/<int:genre_id>/delete', methods=['POST'])
@admin_required
def delete_genre(genre_id):
    genre = Genre.query.get_or_404(genre_id)
    if genre.posts_ref: # Kiểm tra xem thể loại có bài viết nào không
        flash('Không thể xóa thể loại này vì nó đang được sử dụng bởi các bài viết.', 'danger')
        return redirect(url_for('admin.list_genres'))
    db.session.delete(genre)
    db.session.commit()
    flash('Thể loại đã được xóa!', 'success')
    return redirect(url_for('admin.list_genres'))