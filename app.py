from flask import Flask,render_template,g,request,session,url_for,redirect,send_file
import mysql.connector
from mysql.connector import errorcode
import secrets,io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
pdf_file = None
def generate_pdf(data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica", 12)
    y = 750

    for row in data:
        ticket_info = (
            f"Ticket ID: {row[0]}\n"
            f"Price: {row[1]}\n"
            f"Train Name: {row[2]}\n"
            f"Source: {row[3]}\n"
            f"Destination: {row[4]}\n"
            f"No. of Seats: {row[5]}"
        )

        # Split the ticket_info into separate lines
        for line in ticket_info.split('\n'):
            c.drawString(100, y, line)
            y -= 15  # Move y position for the next line

        y -= 20  # Add extra space between tickets

        # Check if the y position is too low and needs a new page
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 750

    c.showPage()
    c.save()
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

app.secret_key = secrets.token_hex(16) 
db_config = {
    'user': 'root',
    'password': 'dinesh@2004',
    'host': 'localhost',
    'database': 'railwayreservation'
}
def get_db_connection():
    if 'db' not in g:
        g.db = mysql.connector.connect(**db_config)
    return g.db

@app.before_request
def before_request():
    g.db = get_db_connection()

@app.teardown_request
def teardown_request(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username  = request.form['username']
        password = request.form['password']
        cur = g.db.cursor()
        cur.execute("SELECT username,role FROM login WHERE username = %s AND password = %s ", (username, password))
        user = cur.fetchone()
        cur.close()
        if user:
            session['username'] = user[0]
            session['role'] = user[1]
            return redirect(url_for('home'))
        else:
            return render_template('login.html',link='new admin',url='/newadmin',action='/',message='new user',new = '/newuser',error = 'invalid credentials')
    return render_template('login.html',link='new admin',url='/newadmin',action='/',message='new user',new = '/newuser')

@app.route('/newuser',methods=['GET','POST'])
def newuser():
    if request.method == 'POST':
        username = request.form['username']
        name  = request.form['name']
        password = request.form['password']
        email  =  request.form['email']
        phone  =  request.form['phone']
        gender  =  request.form['gender']
        dob = request.form['dob']
        state  =  request.form['state']
        pincode = request.form['pincode']
        cur = g.db.cursor()
        try:
            cur.execute("insert into login(username,password) values(%s,%s);",(username,password))
            cur.execute("INSERT INTO user (username, email, name, phone, gender, dateofbirth, state, pincode) VALUES (%s, %s, %s, %s, %s, %s, %s,%s);", (username, email, name, phone, gender, dob, state, pincode))
            g.db.commit()
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_DUP_ENTRY:
                return render_template('userform.html',message = "Already exist usename or email")
            else :
                print(err)
                return render_template('userform.html',message='server error')
        finally:
            cur.close()
    return render_template('userform.html')

@app.route('/newadmin',methods=['GET','POST'])
def newadmin():
    if request.method== 'POST':
        adminname = request.form['adminname']
        name  = request.form['name']
        password = request.form['password']
        email  =  request.form['email']
        phone  =  request.form['phone']
        cur = g.db.cursor()
        try:
            cur.execute("insert into login values(%s,%s,'admin');",(adminname,password))
            cur.execute("insert into admin(adminname, name, phone, email) values(%s,%s,%s,%s);",(adminname,name,phone,email))
            g.db.commit()
            return render_template('home.html')
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_DUP_ENTRY:
                return render_template('adminform.html',message = "Already exist usename or email")
            else :
                print(err)
                return render_template('adminform.html',message = "server error")
        finally:
            cur.close()        
    return render_template('adminform.html')

@app.route('/home')
def home():
    role = session['role']
    if role == 'user':
        return render_template('home.html')
    else:
        cur = g.db.cursor(dictionary=True)
        cur.execute("select * from train;")
        data = cur.fetchall()
        column_names = [i[0] for i in cur.description if i[0] != 'trainid']
        cur.execute("Select * from station;")
        stations = cur.fetchall()
        st_col = [i[0] for i in cur.description]
        cur.close()
        return render_template('admin.html',data=data, column_names = column_names,stations=stations,st_col = st_col)

@app.route('/search')
def search():
    to = request.args.get('to')
    fr = request.args.get('from')
    date = request.args.get('date')
    cur = g.db.cursor()
    print(to,fr,date)
    cur.execute("SELECT t.trainid, t.name, r1.source, r2.destination, s.starting_time, s.reaching_time, t.rate, t.available, t.capacity FROM train t INNER JOIN route r1 ON t.trainid = r1.train_id INNER JOIN route r2 ON t.trainid = r2.train_id INNER JOIN schedule s ON r1.routeid = s.id WHERE r1.source = %s AND r2.destination = %s AND DATE(s.starting_time) = %s AND r1.sequence <= r2.sequence", (fr, to, date))
    data = cur.fetchall()
    if data:
        cur.close()
        return render_template('available.html',data=data)
    else:
        cur.close()
        return render_template('available.html',message='No result')

@app.route("/tickets")
def tickets():
    global pdf_file
    cur = g.db.cursor()
    cur.execute("select t.tid,t.price,tr.name,p.source,p.destination,p.no_of_seats from ticket t inner join train tr on t.trainid=tr.trainid  inner join passenger p on p.pid=t.pid where (select username from user u where u.userid=p.userid)=%s",(session['username'],))
    data = cur.fetchall()
    pdf_data = generate_pdf(data)

    pdf_data = generate_pdf(data)

    # Store the PDF in a BytesIO object for download
    global pdf_file
    pdf_file = io.BytesIO(pdf_data)
    pdf_file.seek(0)

    return render_template('ticket.html', data=data)

@app.route('/download_pdf')
def download_pdf():
    global pdf_file  # Access global pdf_file

    if pdf_file:
        pdf_file.seek(0)  # Ensure the file pointer is at the beginning
        return send_file(
            pdf_file,
            download_name='ticket.pdf',
            as_attachment=True
        )
    else:
        return "PDF file not found or generated."


@app.route('/book/<int:train_id>',methods=['GET','POST'])
def book(train_id):
    if request.method == 'POST':
        nos = int(request.form['nos'])
        so = request.form['source']
        des= request.form['destination']
        date = request.form['date']
        cur = g.db.cursor()
        cur.execute('SELECT t.*, r1.source, r2.destination, s.starting_time, s.reaching_time FROM train t INNER JOIN route r1 ON t.trainid = r1.train_id AND r1.source = %s INNER JOIN route r2 ON t.trainid =r2.train_id AND r2.destination = %s INNER JOIN schedule s ON r1.routeid = s.id AND DATE(s.starting_time) = %s WHERE r1.sequence <= r2.sequence and t.trainid =%s;',(so,des,date,train_id))
        result = cur.fetchall()
        if not result:
            cur.close()
            return render_template('book.html',error='wrong train value')
        cur.execute("select available from train where trainid = %s",(train_id,))
        result = cur.fetchone()
        if nos>result[0]:
            cur.close()
            return render_template('book.html',error='not enough space')
        cur.execute("select userid from user where username =  %s",(session['username'],))
        result = cur.fetchone()
        cur.execute("select rate from train where trainid = %s",(train_id,))
        r = cur.fetchone()[0]
        cur.execute("select distance from route where destination = %s and train_id = %s",(des,train_id))
        d = cur.fetchone()[0]
        p=r*d
        cur.execute("insert into passenger (no_of_seats,source,destination,userid) values(%s,%s,%s,%s);",(nos,so,des,result[0]))
        g.db.commit()
        id = cur.lastrowid
        cur.execute("insert into ticket (price,pid,trainid) values(%s,%s,%s)",(p,id,train_id))
        g.db.commit()
        return redirect(url_for('home'))
    return render_template('book.html')

@app.route('/cancel/<int:t_id>')
def cancel(t_id):
    cur = g.db.cursor()
    cur.execute("select pid from ticket where tid = %s",(t_id,))
    pid = cur.fetchone()[0]
    cur.execute("delete from ticket where tid = %s",(t_id,))
    g.db.commit()
    cur.execute("select * from ticket where pid = %s",(pid,))
    result = cur.fetchall()
    if not result:
        cur.execute("delete from passenger where pid = %s",(pid,))
        g.db.commit()
    cur.close()
    return redirect(request.referrer)
    
@app.route('/newtrain',methods=['GET','POST'])
def train():
    if request.method=='POST':
        name = request.form['name']
        start = request.form['start']
        end = request.form['end']
        rate = request.form['rate']
        available = request.form['available']
        capacity = request.form['capacity']
        cur = g.db.cursor()
        try:
            cur.execute("insert into train(name,start,end,rate,available,capacity) values(%s,%s,%s,%s,%s,%s)",(name,start,end,rate,available,capacity))
            g.db.commit()
            return redirect(url_for('home'))
        except mysql.connector.Error as err:
            if err.errno == 1452:  
                return render_template('train.html', error="there is no such station")
            return render_template('train.html',error=err)
        finally:
            cur.close()
    return render_template('train.html',url='/newtrain')

@app.route('/trainupdate/<int:train_id>',methods=['POST','GET'])
def updatetrain(train_id):
    if request.method=='POST':
        name = request.form['name']
        start = request.form['start']
        end = request.form['end']
        rate = request.form['rate']
        available = request.form['available']
        capacity = request.form['capacity']
        cur = g.db.cursor()
        try:
            cur.execute("update train set name=%s,start = %s, end = %s, rate = %s, available = %s, capacity = %s WHERE trainid = %s",(name,start,end,rate,available,capacity,train_id))
            g.db.commit()
            return redirect(url_for('home'))
        except mysql.connector.Error as err: 
            return render_template('train.html',train_id=train_id,url=url_for('updatetrain',train_id=train_id))
        finally:
            cur.close()
    return render_template('train.html',train_id=train_id,url= url_for('updatetrain',train_id=train_id))    
    
@app.route('/traindelete/<int:train_id>')
def deletetrain(train_id):
    cur = g.db.cursor()
    cur.execute("delete from schedule where id in (select routeid from route where train_id =%s )",(train_id,))
    cur.execute("delete from route where train_id = %s",(train_id,))
    cur.execute("delete from train where trainid = %s",(train_id,))
    g.db.commit()
    cur.close()
    return redirect(url_for('home'))

@app.route('/route/<int:train_id>')
def route(train_id):
    cur = g.db.cursor()
    cur.execute("select routeid,source,destination,sequence,distance,starting_time,reaching_time from route inner join schedule on routeid = id where train_id =%s",(train_id,))
    data = cur.fetchall()
    col = [i[0] for i in cur.description]
    cur.close()
    return render_template('route.html',data=data,col=col,train_id=train_id)

@app.route('/newroute/<int:train_id>',methods=['GET','POST'])
def newroute(train_id):
    if request.method=='POST':
        source = request.form['source']
        destination = request.form['destination']
        sequence = request.form['sequence']
        distance = request.form['distance']
        st = request.form['st']
        rt = request.form['rt']
        cur = g.db.cursor()
        try:
            cur.execute("insert into route (train_id, source, destination, sequence, distance) values(%s,%s,%s,%s,%s)",(train_id,source,destination,sequence,distance))
            g.db.commit()
            route_id = cur.lastrowid
            cur.execute("insert into schedule (starting_time, reaching_time, id) values(%s,%s,%s)",(st,rt,route_id))
            g.db.commit()
            return redirect(url_for('route',train_id=train_id))
        except mysql.connector.Error as err:
            print(err)
            return render_template('routeform.html',train_id=train_id,url=url_for('newroute',train_id=train_id))
        finally:
            cur.close()
    return render_template('routeform.html',train_id=train_id,url=url_for('newroute',train_id=train_id))

@app.route('/routeupdate/<int:train_id>/<int:route_id>',methods=['POST','GET'])
def updateroute(route_id,train_id):
    if request.method=='POST':
        source = request.form['source']
        destination = request.form['destination']
        sequence = request.form['sequence']
        distance = request.form['distance']
        st = request.form['st']
        rt = request.form['rt']
        cur = g.db.cursor()
        try:
            cur.execute("update route set source=%s,destination = %s, sequence = %s, distance = %s WHERE routeid = %s;",(source,destination,sequence,distance,route_id))
            cur.execute("update schedule set starting_time = %s,reaching_time = %s where id =%s;",(st,rt,route_id))
            g.db.commit()
            return redirect(url_for('route',train_id=train_id))
        except mysql.connector.Error as err: 
            return render_template('routeform.html',url=url_for('updateroute',route_id=route_id,train_id=train_id)) 
        finally:
            cur.close()
    return render_template('routeform.html',url=url_for('updateroute',route_id=route_id,train_id=train_id))    
    
@app.route('/routedelete/<int:train_id>/<int:route_id>')
def deleteroute(route_id,train_id):
    cur = g.db.cursor()
    cur.execute("delete from schedule where id = %s",(route_id,))
    cur.execute("delete from route where routeid = %s",(route_id,))
    g.db.commit()
    cur.close()
    return redirect(url_for('route',train_id=train_id))

@app.route('/newstation', methods=['GET', 'POST'])
def newstation():
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['add']
        cur = g.db.cursor()
        try:
            cur.execute("INSERT INTO station (name,address) VALUES (%s,%s)", (name,address))
            g.db.commit()
            return redirect(url_for('home'))
        except mysql.connector.Error as err:
            print(err)
            if err.errno == mysql.connector.errorcode.ER_DUP_ENTRY:
                return render_template('stationform.html', message="Station already exists")
            else:
                return render_template('stationform.html', message="Error inserting data")
        finally:
            cur.close()
    return render_template('stationform.html')

@app.route('/trainroute/<int:id>')
def trainroute(id):
    cur = g.db.cursor()
    cur.execute("select routeid,source,destination,sequence,distance,starting_time,reaching_time from route inner join schedule on routeid = id where train_id =%s",(id,))
    data = cur.fetchall()
    column_names = [col[0] for col in cur.description]  
    cur.close()

    return render_template('trainroute.html', data=data, column_names=column_names)



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))
    
if __name__ == '__main__':
    app.run(debug=True)