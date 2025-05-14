from app import create_app, db
from app.models import User, Post, Comment, Genre # Import các model cần thiết

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Post': Post, 'Comment': Comment, 'Genre': Genre}

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False))