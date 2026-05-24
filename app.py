import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from config import Config
from utils.hashing import hash_password, verify_password
from utils.report_generator import build_pdf_report

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def current_user():
    if 'user_id' not in session:
        return None
    cur = mysql.connection.cursor()
    cur.execute('SELECT user_id, name, email, role, score FROM users WHERE user_id=%s', (session['user_id'],))
    return cur.fetchone()

@app.route('/')
def index():
    return render_template('welcome.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form.get('role', 'trainee')
        cur = mysql.connection.cursor()
        try:
            cur.execute('INSERT INTO users(name,email,role,password_hash) VALUES(%s,%s,%s,%s)',
                        (name, email, role, hash_password(password)))
            mysql.connection.commit()
            flash('Registration successful. Login now.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash('Email already exists or database error.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM users WHERE email=%s', (email,))
        user = cur.fetchone()
        if user and verify_password(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            flash('Welcome Investigator!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute('SELECT COUNT(*) total FROM cases')
    total = cur.fetchone()['total']
    cur.execute('SELECT COUNT(*) total FROM evidence WHERE collected_by=%s', (session['user_id'],))
    ev = cur.fetchone()['total']
    cur.execute('SELECT COUNT(*) total FROM verdicts WHERE submitted_by=%s', (session['user_id'],))
    verdicts = cur.fetchone()['total']
    return render_template('dashboard.html', user=current_user(), total_cases=total, evidence_count=ev, verdict_count=verdicts)

@app.route('/cases', methods=['GET', 'POST'])
@login_required
def case_list():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        cur.execute('''INSERT INTO cases(title, crime_type, location, date_of_crime, difficulty, description)
                       VALUES(%s,%s,%s,%s,%s,%s)''',
                    (request.form['title'], request.form['crime_type'], request.form['location'], request.form['date_of_crime'], request.form['difficulty'], request.form['description']))
        case_id = cur.lastrowid
        bg = request.form.get('background_url') or 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200'
        cur.execute('INSERT INTO crime_scenes(case_id, background_url, description) VALUES(%s,%s,%s)',
                    (case_id, bg, 'Custom crime scene created by investigator. Add evidence manually from the evidence lab.'))
        mysql.connection.commit()
        flash('New case created and added to available cases.', 'success')
        return redirect(url_for('case_list'))
    q = request.args.get('q', '')
    if q:
        cur.execute('SELECT * FROM cases WHERE title LIKE %s OR crime_type LIKE %s OR location LIKE %s ORDER BY case_id DESC', (f'%{q}%', f'%{q}%', f'%{q}%'))
    else:
        cur.execute('SELECT * FROM cases ORDER BY case_id DESC')
    cases = cur.fetchall()
    return render_template('case_list.html', cases=cases, q=q)

@app.route('/case/<int:case_id>')
@login_required
def crime_scene(case_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM cases WHERE case_id=%s', (case_id,))
    case = cur.fetchone()
    cur.execute('SELECT * FROM crime_scenes WHERE case_id=%s LIMIT 1', (case_id,))
    scene = cur.fetchone()
    cur.execute('SELECT * FROM hotspots WHERE scene_id=%s', (scene['scene_id'],))
    hotspots = cur.fetchall()
    cur.execute('SELECT hotspot_id FROM collected_evidence WHERE user_id=%s AND case_id=%s', (session['user_id'], case_id))
    collected = {r['hotspot_id'] for r in cur.fetchall()}
    return render_template('crime_scene.html', case=case, scene=scene, hotspots=hotspots, collected=collected)

@app.route('/collect/<int:case_id>/<int:hotspot_id>', methods=['POST'])
@login_required
def collect(case_id, hotspot_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM hotspots WHERE hotspot_id=%s', (hotspot_id,))
    h = cur.fetchone()
    cur.execute('SELECT id FROM collected_evidence WHERE user_id=%s AND case_id=%s AND hotspot_id=%s', (session['user_id'], case_id, hotspot_id))
    if not cur.fetchone():
        cur.execute('INSERT INTO collected_evidence(user_id, case_id, hotspot_id, evidence_name) VALUES(%s,%s,%s,%s)', (session['user_id'], case_id, hotspot_id, h['label']))
        cur.execute('''INSERT INTO evidence(case_id, hotspot_id, type, description, collected_by, lab_result)
                       VALUES(%s,%s,%s,%s,%s,%s)''', (case_id, hotspot_id, h['evidence_type'], h['clue_description'], session['user_id'], 'Pending lab examination'))
        mysql.connection.commit()
        flash('Evidence collected and logged in chain of custody.', 'success')
    nxt = request.form.get('next', 'scene')
    if nxt == 'lab':
        return redirect(url_for('evidence_lab', case_id=case_id))
    return redirect(url_for('crime_scene', case_id=case_id))

@app.route('/evidence/<int:case_id>', methods=['GET', 'POST'])
@login_required
def evidence_lab(case_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        evidence_id = request.form.get('evidence_id')
        lab_result = request.form.get('lab_result')
        if evidence_id and lab_result:
            cur.execute('UPDATE evidence SET lab_result=%s WHERE evidence_id=%s AND collected_by=%s', (lab_result, evidence_id, session['user_id']))
            cur.execute('INSERT INTO lab_tests(evidence_id, test_type, result, performed_by) VALUES(%s,%s,%s,%s)', (evidence_id, request.form.get('test_type','General Forensic Test'), lab_result, session['user_id']))
            mysql.connection.commit()
            flash('Lab result updated.', 'success')
    cur.execute('SELECT * FROM cases WHERE case_id=%s', (case_id,))
    case = cur.fetchone()
    cur.execute('SELECT * FROM crime_scenes WHERE case_id=%s LIMIT 1', (case_id,))
    scene = cur.fetchone()
    cur.execute('SELECT * FROM hotspots WHERE scene_id=%s ORDER BY is_red_herring, hotspot_id', (scene['scene_id'],))
    hotspots = cur.fetchall()
    cur.execute('SELECT hotspot_id FROM collected_evidence WHERE user_id=%s AND case_id=%s', (session['user_id'], case_id))
    collected = {r['hotspot_id'] for r in cur.fetchall()}
    cur.execute('''SELECT e.*, h.label, h.icon, h.is_red_herring FROM evidence e LEFT JOIN hotspots h ON e.hotspot_id=h.hotspot_id
                   WHERE e.case_id=%s AND e.collected_by=%s ORDER BY e.collected_at DESC''', (case_id, session['user_id']))
    evidence = cur.fetchall()
    return render_template('evidence_lab.html', case=case, scene=scene, hotspots=hotspots, collected=collected, evidence=evidence)

@app.route('/upload/<int:case_id>', methods=['POST'])
@login_required
def upload(case_id):
    file = request.files.get('file')
    note = request.form.get('note', 'Uploaded field file')
    if file and allowed_file(file.filename):
        filename = f"case{case_id}_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        cur = mysql.connection.cursor()
        cur.execute('''INSERT INTO evidence(case_id, hotspot_id, type, description, collected_by, file_hash, lab_result)
                       VALUES(%s,NULL,%s,%s,%s,%s,%s)''', (case_id, 'uploaded_file', note, session['user_id'], filename, 'Uploaded file preserved'))
        mysql.connection.commit()
        flash('Real-life image/FIR/document uploaded.', 'success')
    else:
        flash('Upload only png, jpg, jpeg, webp, or pdf.', 'danger')
    return redirect(url_for('evidence_lab', case_id=case_id))

@app.route('/suspects/<int:case_id>', methods=['GET', 'POST'])
@login_required
def suspects(case_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM cases WHERE case_id=%s', (case_id,))
    case = cur.fetchone()
    cur.execute('SELECT * FROM suspects WHERE case_id=%s', (case_id,))
    suspects = cur.fetchall()
    selected = None
    interview = None
    if request.method == 'POST':
        sid = request.form['suspect_id']
        cur.execute('SELECT * FROM suspects WHERE suspect_id=%s', (sid,))
        selected = cur.fetchone()
        pressure = request.form.get('question_style','neutral')
        if selected:
            interview = f"Interview note: {selected['name']} was questioned using a {pressure} approach. Alibi checked: {selected['alibi']} Motive observed: {selected['motive']}"
    return render_template('suspects.html', case=case, suspects=suspects, selected=selected, interview=interview)

@app.route('/verdict/<int:case_id>', methods=['GET', 'POST'])
@login_required
def verdict(case_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM cases WHERE case_id=%s', (case_id,))
    case = cur.fetchone()
    cur.execute('SELECT * FROM suspects WHERE case_id=%s', (case_id,))
    suspects = cur.fetchall()
    result = None
    if request.method == 'POST':
        accused = int(request.form['accused_suspect_id'])
        reasoning = request.form['reasoning']
        cur.execute('SELECT is_guilty, name FROM suspects WHERE suspect_id=%s', (accused,))
        guilty = cur.fetchone()
        cur.execute('SELECT COUNT(*) total FROM evidence WHERE case_id=%s AND collected_by=%s', (case_id, session['user_id']))
        ev_count = cur.fetchone()['total']
        is_correct = bool(guilty and guilty['is_guilty'])
        score = min(100, (60 if is_correct else 20) + min(ev_count * 8, 32) + (8 if len(reasoning) > 80 else 0))
        cur.execute('''INSERT INTO verdicts(case_id, submitted_by, accused_suspect_id, reasoning, score, is_correct)
                       VALUES(%s,%s,%s,%s,%s,%s)''', (case_id, session['user_id'], accused, reasoning, score, is_correct))
        mysql.connection.commit()
        result = {'is_correct': is_correct, 'score': score, 'accused': guilty['name'] if guilty else ''}
    cur.execute('''SELECT v.*, s.name accused_name FROM verdicts v LEFT JOIN suspects s ON v.accused_suspect_id=s.suspect_id
                   WHERE v.case_id=%s AND v.submitted_by=%s ORDER BY v.submitted_at DESC LIMIT 1''', (case_id, session['user_id']))
    last_verdict = cur.fetchone()
    return render_template('verdict.html', case=case, suspects=suspects, result=result, last_verdict=last_verdict)

@app.route('/report/<int:case_id>')
@login_required
def report(case_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM cases WHERE case_id=%s', (case_id,))
    case = cur.fetchone()
    cur.execute('SELECT * FROM users WHERE user_id=%s', (session['user_id'],))
    user = cur.fetchone()
    cur.execute('''SELECT e.*, h.label FROM evidence e LEFT JOIN hotspots h ON e.hotspot_id=h.hotspot_id
                   WHERE e.case_id=%s AND e.collected_by=%s''', (case_id, session['user_id']))
    evidence = cur.fetchall()
    cur.execute('SELECT * FROM suspects WHERE case_id=%s', (case_id,))
    suspects_data = cur.fetchall()
    cur.execute('''SELECT v.*, s.name accused_name FROM verdicts v LEFT JOIN suspects s ON v.accused_suspect_id=s.suspect_id
                   WHERE v.case_id=%s AND v.submitted_by=%s ORDER BY v.submitted_at DESC LIMIT 1''', (case_id, session['user_id']))
    verdict_data = cur.fetchone()
    filename = f'investigation_report_case_{case_id}_user_{session["user_id"]}.pdf'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    build_pdf_report(filepath, case, user, evidence, suspects_data, verdict_data)
    return send_file(filepath, as_attachment=True)

@app.route('/case_closed/<int:case_id>')
@login_required
def case_closed(case_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE cases SET status='closed' WHERE case_id=%s", (case_id,))
    mysql.connection.commit()

    cur.execute("SELECT * FROM cases WHERE case_id=%s", (case_id,))
    case = cur.fetchone()

    return render_template('case_closed.html', case=case)

if __name__ == '__main__':
    app.run(debug=True)
