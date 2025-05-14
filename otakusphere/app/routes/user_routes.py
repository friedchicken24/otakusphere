from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from app import db # db được import từ app package
from app.models import Post, User, Comment, Genre, PostLike, Friendship, Notification # Import các model cần thiết
from app.forms import PostForm, CommentForm # Import các form cần thiết
from sqlalchemy.exc import IntegrityError # Để bắt lỗi trùng lặp (ví dụ: tên genre)

# Tạo Blueprint cho user routes
bp = Blueprint('user', __name__) # Đặt tên blueprint là 'user' để url_for('user.home') hoạt động

@bp.route('/')
@bp.route('/home')
def home():
    page = request.args.get('page', 1, type=int)
    # Sử dụng current_app.config thay vì app.config trực tiếp trong blueprint
    posts_pagination = Post.query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False
    )
    posts = posts_pagination.items
    return render_template('user/home.html', title='Trang chủ', posts=posts, pagination=posts_pagination)

@bp.route('/post/new', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author_id=current_user.id)
        selected_genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
        for genre in selected_genres:
            post.genres.append(genre)
        db.session.add(post)
        db.session.commit()
        flash('Bài viết của bạn đã được tạo!', 'success')
        return redirect(url_for('user.home'))
    return render_template('user/create_post.html', title='Tạo bài viết mới', form=form, legend='Tạo bài viết mới')

@bp.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    comment_form = CommentForm()

    if comment_form.validate_on_submit() and current_user.is_authenticated:
        comment = Comment(content=comment_form.content.data, post_id=post.id, author_id=current_user.id)
        db.session.add(comment)
        
        # Tạo notification cho chủ bài viết (nếu không phải là người bình luận)
        if post.author_id != current_user.id:
            # Giả sử User model có phương thức add_notification
            post.author_user.add_notification( 
                actor=current_user,
                type='new_comment',
                content=f'{current_user.username} đã bình luận về bài viết "{post.title}".',
                link=url_for('user.view_post', post_id=post.id, _external=True), # _external=True để có URL đầy đủ
                source_entity_id=comment.id, 
                source_entity_type='comment'
            )
        db.session.commit()
        flash('Bình luận của bạn đã được thêm!', 'success')
        return redirect(url_for('user.view_post', post_id=post.id)) # Redirect để tránh resubmit form
    
    comments = Comment.query.filter_by(post_id=post.id).order_by(Comment.created_at.asc()).all()
    user_liked_post = False
    if current_user.is_authenticated:
        user_liked_post = PostLike.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None

    return render_template('user/view_post.html', title=post.title, post=post, 
                           comments=comments, comment_form=comment_form, user_liked_post=user_liked_post)

@bp.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id and current_user.role != 'admin':
        abort(403) # Forbidden
    
    form = PostForm(obj=post) # Load dữ liệu hiện tại của post vào form
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        # Cập nhật genres
        post.genres = [] # Xóa các genre cũ trước khi thêm mới
        selected_genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
        for genre in selected_genres:
            post.genres.append(genre)
        db.session.commit()
        flash('Bài viết đã được cập nhật!', 'success')
        return redirect(url_for('user.view_post', post_id=post.id))
    elif request.method == 'GET':
        # Đảm bảo form được điền đúng dữ liệu khi GET request
        form.title.data = post.title
        form.content.data = post.content
        form.genres.data = [genre.id for genre in post.genres] # Chọn các genre hiện tại
    return render_template('user/create_post.html', title='Chỉnh sửa bài viết', form=form, legend='Chỉnh sửa bài viết')


@bp.route('/post/<int:post_id>/delete', methods=['POST']) # Chỉ chấp nhận POST để xóa
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id and current_user.role != 'admin':
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Bài viết đã được xóa!', 'success')
    return redirect(url_for('user.home'))

@bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = PostLike.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if like:
        db.session.delete(like)
        # (Tùy chọn) Xóa notification nếu có, hoặc tạo notification "unliked"
        flash('Bạn đã bỏ thích bài viết.', 'info')
    else:
        new_like = PostLike(user_id=current_user.id, post_id=post.id)
        db.session.add(new_like)
        # Tạo notification cho chủ bài viết (nếu không phải là người thích)
        if post.author_id != current_user.id:
            post.author_user.add_notification(
                actor=current_user,
                type='new_like',
                content=f'{current_user.username} đã thích bài viết "{post.title}".',
                link=url_for('user.view_post', post_id=post.id, _external=True),
                source_entity_id=post.id,
                source_entity_type='post'
            )
        flash('Bạn đã thích bài viết!', 'success')
    db.session.commit()
    return redirect(url_for('user.view_post', post_id=post.id))


@bp.route('/profile/<username>')
# @login_required # Có thể bỏ nếu muốn public profile
def profile(username):
    user_profile_obj = User.query.filter_by(username=username).first_or_404() # Đổi tên biến để tránh nhầm lẫn
    user_posts = Post.query.filter_by(author_id=user_profile_obj.id).order_by(Post.created_at.desc()).all()
    
    is_self = current_user.is_authenticated and current_user.id == user_profile_obj.id
    are_friends = False
    sent_request_to_profile_user = False # current_user đã gửi request cho user_profile_obj
    received_request_from_profile_user = False # current_user đã nhận request từ user_profile_obj

    if current_user.is_authenticated and not is_self:
        are_friends = current_user.is_friends_with(user_profile_obj)
        sent_request_to_profile_user = current_user.has_sent_request_to(user_profile_obj)
        received_request_from_profile_user = current_user.has_received_request_from(user_profile_obj)
        
    return render_template('user/profile.html', title=f'Hồ sơ {user_profile_obj.username}', 
                           user_profile=user_profile_obj, # Truyền user_profile_obj vào template
                           posts=user_posts,
                           is_self=is_self, are_friends=are_friends,
                           sent_request=sent_request_to_profile_user, # Đổi tên biến cho rõ ràng
                           received_request=received_request_from_profile_user) # Đổi tên biến

# --- Friendships Routes ---
@bp.route('/friend/send_request/<username>', methods=['POST'])
@login_required
def send_friend_request(username):
    recipient = User.query.filter_by(username=username).first_or_404()
    if current_user.id == recipient.id:
        flash('Bạn không thể gửi yêu cầu kết bạn cho chính mình.', 'warning')
        return redirect(url_for('user.profile', username=username))

    # Sử dụng phương thức helper từ User model
    friendship = current_user.send_friend_request(recipient) 
    if friendship:
        # Tạo notification cho người nhận
        recipient.add_notification(
            actor=current_user,
            type='friend_request',
            content=f'{current_user.username} đã gửi cho bạn một lời mời kết bạn.',
            link=url_for('user.friends_list', _external=True) # Hoặc link đến profile của current_user
        )
        db.session.commit()
        flash(f'Đã gửi yêu cầu kết bạn đến {username}.', 'success')
    else:
        flash(f'Không thể gửi yêu cầu kết bạn đến {username} (có thể đã gửi, đã là bạn, hoặc có lỗi).', 'info')
    return redirect(url_for('user.profile', username=username))

@bp.route('/friend/accept_request/<username>', methods=['POST'])
@login_required
def accept_friend_request(username):
    requester = User.query.filter_by(username=username).first_or_404()
    # current_user là người nhận, requester là người gửi
    friendship = current_user.accept_friend_request(requester)
    if friendship:
        # Tạo notification cho người gửi yêu cầu (requester)
        requester.add_notification(
            actor=current_user,
            type='friend_accept',
            content=f'{current_user.username} đã chấp nhận lời mời kết bạn của bạn.',
            link=url_for('user.profile', username=current_user.username, _external=True)
        )
        db.session.commit()
        flash(f'Bạn đã trở thành bạn bè với {username}.', 'success')
    else:
        flash('Không tìm thấy yêu cầu kết bạn hoặc có lỗi xảy ra.', 'danger')
    # Redirect về trang friends hoặc profile của requester
    return redirect(request.referrer or url_for('user.friends_list'))


@bp.route('/friend/decline_request/<username>', methods=['POST'])
@login_required
def decline_friend_request(username):
    requester = User.query.filter_by(username=username).first_or_404()
    # current_user là người nhận, requester là người gửi
    if current_user.decline_friend_request(requester):
        db.session.commit()
        flash(f'Bạn đã từ chối yêu cầu kết bạn từ {username}.', 'info')
    else:
        flash('Không tìm thấy yêu cầu kết bạn hoặc có lỗi xảy ra.', 'danger')
    return redirect(request.referrer or url_for('user.friends_list'))

@bp.route('/friend/unfriend/<username>', methods=['POST'])
@login_required
def unfriend(username):
    friend_user = User.query.filter_by(username=username).first_or_404()
    if current_user.unfriend(friend_user):
        db.session.commit()
        flash(f'Bạn đã hủy kết bạn với {username}.', 'info')
    else:
        flash(f'Bạn không phải là bạn bè với {username} hoặc có lỗi xảy ra.', 'danger')
    return redirect(url_for('user.profile', username=username))

@bp.route('/friends')
@login_required
def friends_list():
    friends = current_user.get_friends()
    pending_requests_received = current_user.get_pending_friend_requests() # Các request người khác gửi cho mình
    
    # Các request mình đã gửi và đang chờ
    sent_pending_requests = Friendship.query.filter_by(user_id=current_user.id, status='pending').all() 
    
    return render_template('user/friends.html', title='Bạn bè', 
                           friends=friends, 
                           pending_requests_received=pending_requests_received, 
                           sent_pending_requests=sent_pending_requests)


# --- Notifications Routes ---
@bp.route('/notifications')
@login_required
def notifications():
    # Lấy danh sách thông báo, sắp xếp theo thời gian mới nhất trước
    user_notifications = current_user.notifications_received.order_by(Notification.created_at.desc()).all()
    
    # Không tự động đánh dấu đã đọc ở đây, để người dùng chủ động
    return render_template('user/notifications.html', 
                           title='Thông báo', 
                           notifications=user_notifications)

@bp.route('/notifications/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id: # Đảm bảo user chỉ đánh dấu notif của mình
        abort(403)
    
    was_unread = not notification.is_read
    notification.is_read = True
    db.session.commit()

    if was_unread:
        flash('Thông báo đã được đánh dấu là đã đọc.', 'success')
    
    # Nếu thông báo có link, chuyển hướng đến link đó. Nếu không, quay lại trang notifications.
    if notification.link:
        return redirect(notification.link)
    return redirect(url_for('user.notifications'))

@bp.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    if unread_notifications:
        for notif in unread_notifications:
            notif.is_read = True
        db.session.commit()
        flash('Tất cả thông báo chưa đọc đã được đánh dấu là đã đọc.', 'success')
    else:
        flash('Không có thông báo nào chưa đọc.', 'info')
    return redirect(url_for('user.notifications'))

# Thêm các route cho comment edit/delete sau nếu cần
# Ví dụ:
# @bp.route('/comment/<int:comment_id>/edit', methods=['GET', 'POST'])
# @login_required
# def edit_comment(comment_id):
#     comment = Comment.query.get_or_404(comment_id)
#     if comment.author_id != current_user.id and current_user.role != 'admin':
#         abort(403)
#     # ... logic form và cập nhật ...
#     pass

# @bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
# @login_required
# def delete_comment(comment_id):
#     comment = Comment.query.get_or_404(comment_id)
#     if comment.author_id != current_user.id and current_user.role != 'admin':
#         abort(403)
#     post_id_redirect = comment.post_id
#     db.session.delete(comment)
#     db.session.commit()
#     flash('Bình luận đã được xóa.', 'success')
#     return redirect(url_for('user.view_post', post_id=post_id_redirect))