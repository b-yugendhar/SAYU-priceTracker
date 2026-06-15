import glob

def patch_templates():
    for f in glob.glob('templates/*.html'):
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Patch prefixes mapping to the Auth Blueprint
        content = content.replace('url_for("login")', 'url_for("auth.login")')
        content = content.replace("url_for('login')", "url_for('auth.login')")
        content = content.replace('url_for("register")', 'url_for("auth.register")')
        content = content.replace("url_for('register')", "url_for('auth.register')")
        content = content.replace('url_for("logout")', 'url_for("auth.logout")')
        content = content.replace("url_for('logout')", "url_for('auth.logout')")
        
        # Redundant patches if any existed
        content = content.replace('auth.auth.', 'auth.')
        
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
            
if __name__ == "__main__":
    patch_templates()
    print("Templates successfully patched.")
