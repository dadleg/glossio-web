import sys
from app import create_app, db
from app.models import User

def usage():
    print("Usage: python manage_users.py <command> [args]")
    print("Commands:")
    print("  add <email> <name> <password>   - Create a new user")
    print("  list                            - List all users")
    print("  delete <email>           - Delete a user")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        usage()
        
    command = sys.argv[1]
    app = create_app()
    
    with app.app_context():
        if command == 'add':
            if len(sys.argv) != 5:
                print("Usage: python manage_users.py add <email> <name> <password>")
                return
            email = sys.argv[2]
            name = sys.argv[3]
            password = sys.argv[4]
            
            if User.query.filter_by(email=email).first():
                print(f"Error: User {email} already exists.")
                return
            
            u = User(email=email, name=name)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            print(f"User {name} ({email}) created successfully.")
            
        elif command == 'list':
            users = User.query.all()
            print(f"Found {len(users)} users:")
            for u in users:
                print(f" - ID: {u.id}, Email: {u.email}")
                
        elif command == 'delete':
            if len(sys.argv) != 3:
                print("Usage: python manage_users.py delete <email>")
                return
            email = sys.argv[2]
            user = User.query.filter_by(email=email).first()
            if not user:
                print(f"Error: User {email} not found.")
                return
                
            db.session.delete(user)
            db.session.commit()
            print(f"User {email} deleted.")
            
        else:
            usage()

if __name__ == '__main__':
    main()
