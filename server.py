import os,binascii
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify
from flask.ext.paginate import Pagination
from flaskext.mysql import MySQL
from flask_mail import Mail,Message
from config import config, ADMINS, MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
from werkzeug.utils import secure_filename
import datetime,json,hashlib,re

import logging
from logging.handlers import SMTPHandler
credentials = None

# Image upload folder in shout
UPLOAD_FOLDER = 'ImgPosts/'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

mysql = MySQL()
# create our little application :)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

for key in config:
    app.config[key] = config[key]

mail = Mail(app)
# Mail
mail.init_app(app)

if MAIL_USERNAME or MAIL_PASSWORD:
    credentials = (MAIL_USERNAME, MAIL_PASSWORD)
    mail_handler = SMTPHandler((MAIL_SERVER, MAIL_PORT), 'no-reply@' + MAIL_SERVER, ADMINS, 'resetpass', credentials)
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

mysql.init_app(app)
app.config.from_object(__name__)

def get_cursor():
    return mysql.connect().cursor()

@app.errorhandler(404)
def page_not_found(e):
    return render_template('global/404.html'), 404

@app.errorhandler(500)
def special_exception_handler(error):
    return 'Database connection failed', 500

@app.teardown_appcontext
def close_db():
    """Closes the database again at the end of the request."""
    get_cursor().close()

def allowed_file(filename):
	return '.' in filename and \
		filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/uploads/<filename>')
def uploaded_file(filename):
	return send_from_directory(app.config['UPLOAD_FOLDER'],filename)

@app.route('/postblog',methods=['GET','POST'])
def postblog():
	if request.method=="POST":
		return redirect(url_for('shout'))
	return render_template('shout/editor.html')

def emailhash(email):
	return u''+(hashlib.md5(str(email)).hexdigest())+''

app.jinja_env.globals.update(emailhash=emailhash)

@app.route('/admin-login',methods=['GET','POST'])
def admin_login():
	ip=request.remote_addr
	if ip=="127.0.0.1":
		if request.method=="POST":
			db=get_cursor()
			uname=str(request.form['username'])
			pwd=str(request.form['password'])
			sql = 'select Count(*) from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
			db.execute(sql)
			data = db.fetchone()[0]
			if not data:
				error='Invalid username/password'
			else:
				session['logged_in'] = True
				sql='select Role from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
				db.execute(sql)
				result=db.fetchone()[0]
				session['temp']=result
				session['uname']=uname
				sql='select Sno,email from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
				db.execute(sql)
				result=db.fetchone()
				uid=result[0]
				db.execute("COMMIT")
				# sql='insert into usage_history (`IP_ADDRESS`, `SessionStatus`, `LoginID`, `LoginTime`) values("%s",1,"%s",CURRENT_TIMESTAMP)'%(ip,uid)
				# db.execute(sql)
				# db.execute("commit")
				app.config['USERNAME'] = uname
				app.config['USERID'] = uid
				session['email']=result[1]
				session['userid']=uid
				flash('You were logged in ')
				return redirect(url_for('mainscreen'))
			return render_template('admin/admin_login.html',user_ip=ip)
		return render_template('admin/admin_login.html',user_ip=ip)
	db=get_cursor()
	sql='insert into illegal_access(`IP_ADDRESS`,`DATE`,`page_accessed`) values("%s",CURRENT_TIMESTAMP,"Admin-Login")'%(ip)
	db.execute(sql)
	db.execute("commit")
	return '<div  style="color:RED"><h3>Your IP address %s doesnot match.</h3><h1>You have been caught and reported for trying to access admin page</h1></div>'%(ip)

@app.route('/postit',methods=['GET','POST'])
def postit():
	if request.method=="POST":
		db=get_cursor()
		user = app.config['USERNAME']
		content = request.form['content']
		posttype = int(request.form['ctype'])
		privacytype = int(request.form['ptype'])
		now = datetime.datetime.today()
		if privacytype == 2:
			query = 'insert into AnonymousPosts (Date, PostContent, Type, LikeCount,Name) values ("%s","%s","%s","0","Anonymous")'
			db.execute(query%(now,content,posttype))
			db.execute("commit")
			return redirect(url_for('shout'))
		else:
			likecount=0
			query = 'insert into AnonymousPosts (Date,PostContent,Type,LikeCount,Name) values ("%s","%s","%s","%s","%s")'
			db.execute(query%(now,content,posttype,likecount,user))
			db.execute("commit")
			flash('Posted at '+now.strftime('%d/%m/%y'))
			return redirect(url_for('shout'))
	return redirect(url_for('shout'))

@app.route("/register")
def register():
	return render_template('global/register.html')

@app.route("/add",methods=['POST'])
def add():
	error = None
	db=get_cursor()
	if request.method=='POST':
		uname = str(request.form['username'])
		rollno = str(request.form['rollno'])
		pwd = str(request.form['password1'])
		confirm = str(request.form['password2'])
		email = str(request.form['email'])
		year = str(request.form['year'])
		name = str(request.form['name'])
		phno = str(request.form['phone'])
		addr = str(request.form['address'])
		if pwd == confirm:
			sql = 'insert into Login (RollNo,UserName,Password,Role,Email) values ("%s","%s",MD5("%s"),"%s","%s")'%(rollno,uname,pwd,2,email)
			db.execute(sql)
			db.execute("commit")
			retrievesno = 'select Sno from Login where RollNo="%s" and UserName="%s"'%(rollno,uname)
			db.execute(retrievesno)
			sno = db.fetchone()[0]
			profilesql = 'insert into Profile values ("%s","%s","%s","%s","%s","%s","%s","%s")'
			db.execute(profilesql%(str(sno),rollno,name,phno,year,email,addr,uname))
			db.execute('commit')
			flash("Registered Successfully.")
			return redirect(url_for('login'))
		else:
			flash("Failed. Check again")
			return redirect(url_for('register'))
	return redirect(url_for('register'))

@app.route('/forgetpassword',methods=['GET','POST'])
def forgetpassword():
	if request.method=='POST':
		db=get_cursor()
		rollno = request.form['rollno']
		uname = request.form['username']
		email = request.form['email']
		sql = 'select * from Login where UserName="%s" and Email="%s" and Rollno="%s"'%(uname,email,rollno)
		db.execute(sql)
		db.execute("commit")
		values = db.fetchall()
		if not values:
			flash('No one with that data is found.')
			return redirect(url_for('forgetpassword'))
		else:
			new_password=binascii.b2a_hex(os.urandom(15))
			flash(new_password + ' is the new password generated.')
			resetsql = 'update Login set Password="%s" where UserName="%s" and RollNo="%s"'%(new_password,uname,rollno)
			db.execute(resetsql)
			db.execute("commit")
			return redirect(url_for('mainscreen'))
	else:
		return render_template('global/forgetpassword.html')

@app.route("/login",methods = ['GET','POST'])
def login():
	ip = request.remote_addr
	error = None
	db = get_cursor()
	session['temp']=0
	session.permanent = True
	if request.method=='POST':
		uname=str(request.form['username'])
		pwd=str(request.form['password'])
		sql = 'select Count(*) from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
		db.execute(sql)
		data = db.fetchone()[0]
		if not data:
			error='Invalid username/password'
		else:
			session['logged_in'] = True
			sql='select Role from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
			db.execute(sql)
			result=db.fetchone()[0]
			session['temp']=result
			session['uname']=uname
			sql='select Sno,email from Login where UserName="%s" and Password=MD5("%s")'%(uname,pwd)
			db.execute(sql)
			result=db.fetchone()
			uid=result[0]
			db.execute("COMMIT")
			sql='insert into usage_history (`IP_ADDRESS`, `SessionStatus`, `LoginID`, `LoginTime`) values("%s",1,"%s",CURRENT_TIMESTAMP)'%(ip,uid)
			db.execute(sql)
			db.execute("commit")
			app.config['USERNAME'] = uname
			app.config['USERID'] = uid
			session['email']=result[1]
			session['userid']=uid
			flash('You were logged in ')
			return redirect(url_for('mainscreen'))
	return render_template('global/login.html', error=error,UName=app.config['USERNAME'],user_ip=ip)

@app.route('/like')
def like():
	db=get_cursor()
	a = request.args.get('a',0,type=int)
	b = request.args.get('b',0,type=int)
	if a>0:
		shift=0
		sql='select * from like_history where sno=%s and username="%s"'%(a,app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		if result<=0:
			sql='insert into like_history values(%s,"%s",1)'%(a,app.config['USERNAME'])
		else:
			if result[2]==0:
				sql='delete from like_history where sno=%s and username="%s"'%(a,app.config['USERNAME'])
				shift=1
			else:
				sql='update like_history set activity=1 where sno=%s and username = "%s"'%(a,app.config['USERNAME'])
		db.execute(sql)
		db.execute("commit")
		sql='update anonymousposts set likecount=likecount+1 where sno=%s'%(a)
		db.execute(sql)
		db.execute("commit")
		sql='select likecount from anonymousposts where sno=%s'%(a)
		db.execute(sql)
		res=db.fetchone()[0]
		return jsonify(result1=res,shift=shift)
	elif b>0:
		shift=0
		sql='select * from like_history where sno=%s and username="%s"'%(b,app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		if result<=0:
			sql='insert into like_history values(%s,"%s",0)'%(b,app.config['USERNAME'])
		else:
			if result[2]==1:
				sql='delete from like_history where sno=%s and username="%s"'%(b,app.config['USERNAME'])
				shift=1
			else:
				sql='update like_history set activity=0 where sno=%s and username = "%s"'%(b,app.config['USERNAME'])
		db.execute(sql)
		db.execute("commit")
		sql='update anonymousposts set likecount=likecount-1 where sno=%s'%(b)
		db.execute(sql)
		db.execute("commit")
		sql='select likecount from anonymousposts where sno=%s'%(b)
		db.execute(sql)
		res=db.fetchone()[0]
		return jsonify(result1=res,shift=shift)

@app.route('/users', strict_slashes=False)
def allusers():
	db=get_cursor()
	sql = 'select * from Profile'
	db.execute(sql)
	users = db.fetchall()
	session['currentpage']="Admin"
	if not users:
		flash('No users in database')
		return redirect(url_for('mainscreen'))
	else:
		gravatar=[]
		for user in users:
			gravatar.append(hashlib.md5(user[5]).hexdigest())
		return render_template('admin/users.html',users=users,gravatar=gravatar,UName=app.config['USERNAME'])

# Query for users profile - API using Sno present in database
@app.route('/users/<id_no>', strict_slashes=False, methods=['GET','POST'])
def users(id_no):
	db=get_cursor()
	sql = 'select * from Profile where Sno=%s'%id_no
	db.execute(sql)
	user = db.fetchone()
	session['currentpage']="SCorner"
	if not user:
		flash('User '+id_no+' not found')
		return redirect(url_for('mainscreen'))
	else:
		gravatar=hashlib.md5(user[5]).hexdigest()
		sql = 'select * from AnonymousPosts where Name=(select UserName from Profile where Sno="%s")'%id_no
		db.execute(sql)
		posts = db.fetchall()
		return render_template('admin/profile.html',user=user,gravatar=gravatar,UName=app.config['USERNAME'],posts=posts)

# Query for users profile - API using Email registered to user
@app.route('/e-users/<id_email>', strict_slashes=False)
def usersemail(id_email):
	session["currentpage"]="Admin"
	db=get_cursor()
	sql = 'select * from Profile where Email="%s"'%id_email
	db.execute(sql)
	user = db.fetchone()
	if not user:
		flash('Email '+id_email+' not found')
		return redirect(url_for('mainscreen'))
	else:
		return render_template('admin/profile.html',user=user,UName=app.config['USERNAME'])

@app.route('/logout')
def logout():
    if session['logged_in'] != None:
        if session['logged_in']==True:
            session.pop('logged_in', None)
            session.pop('temp',0)
            db=get_cursor()
            sql='update usage_history set `SessionStatus`=0,`LogoutTime`=CURRENT_TIMESTAMP where `SessionStatus`=1 and `LoginID`="%s"'%(app.config['USERID'])
            db.execute(sql)
            db.execute("commit")
            session.clear()
            flash('You were logged out')
        else:
            flash('Welcome Back!')
    return redirect(url_for('mainscreen'))

@app.route('/login-history')
def login_history():
	session["currentpage"]="Admin"
	ip=request.remote_addr
	db=get_cursor()
	if ip!="127.0.0.0":
		#need to change this IP address
		sql='insert into illegal_access(`IP_ADDRESS`,`DATE`,`page_accessed`) values("%s",CURRENT_TIMESTAMP,"Login-History")'%(ip)
		db.execute(sql)
		db.execute("commit")
		return '<div  style="color:RED"><h3>Your IP address %s doesnot match.</h3><h1>You have been caught and reported for trying to access admin page</h1></div>'%(ip)
	sql='select * from usage_history'
	db.execute(sql)
	entries=db.fetchall()
	unames=[]
	for entry in entries:
		sql='select userName from login where sno=%s'%(entry[2])
		db.execute(sql)
		unames.append(str(db.fetchone()[0]))
	db.execute("commit")
	session['currentpage']="Admin"
	return render_template('global/login_history.html',entries=entries,unames=unames)

@app.route("/filter",methods=['GET'])
def filter():
	session["currentpage"]="Shout Box"
	search=False
	q=request.args.get('q')
	if q:
		search=True
	try:
		page = int(request.args.get('page',1))
	except ValueError:
		page = 1
	db=get_cursor()
	filter_num=request.args.get('filter',-1,type=int)
	per_page=2
	if page==1:
		start=0
	else:
		start=(page-1)*per_page
	sql = 'select * from AnonymousPosts order by Date desc limit %s,%s'%(start,per_page)
	if filter_num>0:
		sql='select * from AnonymousPosts where Type=%s limit %s,%s'%(filter_num,start,per_page)
	else:
		return redirect(url_for('shout'))
	db.execute(sql)
	posts=db.fetchall()
	db.execute("commit")
	activity=[]
	comments=[]
	i=0
	for post in posts:
		sql='select activity from like_history where sno=%s and username="%s"'%(post[0],app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		db.execute("commit")
		if result is None:
			like=-1
		else:
			like=int(result[0])
		activity.append(int(like))
		sql='select * from comments where sno=%s order by date'%(post[0])
		db.execute(sql)
		comments.append(db.fetchall())
		i=i+1
	query='select Count(*) from anonymousposts'
	if filter_num>0:
		query='select Count(*) from anonymousposts where Type=%s'%(filter_num)
	print query
	db.execute(query)
	total=int(db.fetchone()[0])
	db.execute("commit")
	pagination = Pagination(page = page ,per_page=per_page,total = total, search=search,record_name = 'posts',bs_version=3)
	return render_template('shout/screen.html',posts=posts,UName=app.config['USERNAME'],activity=activity,pagination=pagination,comments=comments) #show_entries

@app.route('/comment',methods=['POST'])
def comment():
	page=request.form['page_num']
	pagenum=page[-1]
	substring="filter"
	flag=False
	if substring in page:
		flag=True
		if "page=" in page:
			pagenum=int(pagenum)
			filternum=re.search("filter=(.*)&",page).group(1)
		else:
			pagenum=''
			filternum=re.search("filter=(.*)?",page).group(1)
		try:
			filter_num=int(filternum)
		except ValueError:
			filter_num=''
	else:
		try:
			pagenum=int(pagenum)
		except ValueError:
			pagenum=''
	db=get_cursor()
	postid=int(request.form['comment'])
	now=datetime.datetime.now()
	userid=app.config['USERID']
	uname=app.config['USERNAME']
	content=request.form['comment_content']
	if len(content)>0:
		sql='insert into comments(`sno`, `date`, `userID`,`userName`, `content`) values(%s,"%s",%s,"%s","%s")'%(postid,now,userid,uname,content)
		db.execute(sql)
		db.execute("commit")
	if flag==False:
		if pagenum:
			return redirect(url_for('shout',page=pagenum))
		return redirect(url_for('shout'))
	elif flag==True:
		if pagenum:
			return redirect(url_for('filter',filter=filter_num,page=pagenum))
		return redirect(url_for('filter',filter=filter_num))

@app.route("/")
def mainscreen():
	session["currentpage"]="SCorner"
	return render_template('global/welcome.html')
		
@app.route("/shout")
def shout():
	session["currentpage"]="Shout Box"
	search=False
	q=request.args.get('q')
	if q:
		search=True
	try:
		page = int(request.args.get('page',1))
	except ValueError:
		page = 1
	db = get_cursor()
	start=0
	per_page=2
	if page==1:
		start=0
	else:
		start=(page-1)*per_page
	sql = 'select * from AnonymousPosts order by Date desc limit %s,%s'%(start,per_page)
	db.execute(sql)
	posts = db.fetchall()
	db.execute("commit")
	activity=[]
	comments=[]
	i=0
	for post in posts:
		sql='select activity from like_history where sno=%s and username="%s"'%(post[0],app.config['USERNAME'])
		db.execute(sql)
		result=db.fetchone()
		db.execute("commit")
		if result is None:
			like=-1
		else:
			like=int(result[0])
		activity.append(int(like))
		sql='select * from comments where sno=%s order by date'%(post[0])
		db.execute(sql)
		comments.append(db.fetchall())
		i=i+1
	query='select Count(*) from anonymousposts'
	db.execute(query)
	total=int(db.fetchone()[0])
	db.execute("commit")
	pagination = Pagination(page = page ,per_page=per_page,total = total, search=search,record_name = 'posts',bs_version=3)
	return render_template('shout/screen.html',posts=posts,UName=app.config['USERNAME'],activity=activity,pagination=pagination,comments=comments) #show_entries

#---------------Buy_Sell---------------

@app.route('/bechde')
def bechde():
	session['currentpage']="Bech De!"
	return render_template('buysell/index.html')

@app.route('/additem',methods=['GET','POST'])
def additem():
	session['currentpage']="Bech De!"
	db=get_cursor()
	sql='select * from store_categories'
	db.execute(sql)
	category=db.fetchall()
	db.execute("commit")
	if request.method=="POST":
		uploaderid=app.config['USERID']
		name=request.form['itemName']
		desc=request.form['itemDesc']
		categoryid=int(request.form['category'])
		qty=int(request.form['qty'])
		mrp=float(request.form['mrp'])
		dealprice=float(request.form['dealprice'])
		sql='insert into store(`UserID`, `Name`, `ItemDescription`, `CategoryID`, `Quantity`, `MRP`, `DealPrice`, `Available`) values("%s","%s","%s",%s,%s,%s,%s,1)'%(uploaderid,name,desc,categoryid,qty,mrp,dealprice)
		db.execute(sql)
		db.execute("commit")
		return redirect(url_for('store'))
	return render_template('buysell/additem.html',category=category)

@app.route('/item/<itemID>')
def show_item_profile(itemID):
	session["currentpage"]="Bech De!"
	db=get_cursor()
	sql='select * from store where itemID="%s"'%(itemID)
	db.execute(sql)
	details=db.fetchone()
	db.execute("commit")
	sql='select * from profile where sno=%s'%(details[1])
	db.execute(sql)
	uploader=db.fetchone()
	db.execute("commit")
	is_user_uploader=False
	if int(details[1])==int(uploader[0]) and int(details[1])==app.config['USERID']:
		is_user_uploader = True
	return render_template('buysell/item_description.html',details=details,uploader=uploader,is_user_uploader=is_user_uploader)

@app.route('/item/sold/<itemID>',methods=['POST'])
def sold(itemID):
	session["currentpage"]="Bech De!"
	db=get_cursor()
	sql='update store set available=0 where itemID=%s'%(itemID)
	db.execute(sql)
	db.execute("commit")
	return redirect(url_for('show_item_profile',itemID=itemID))

@app.route('/store')
def store():
	session["currentpage"]="Bech De!"
	db=get_cursor()
	sql="select * from store"
	db.execute(sql)
	entries=db.fetchall()
	uploader=[]
	category=[]
	for entry in entries:
		sql='select UserName from login where Sno=%s'%(entry[1])
		db.execute(sql)
		uploader.append(db.fetchone()[0])
		db.execute("commit")
		sql='select CategoryName from store_categories where categoryid=%s'%(entry[4])
		db.execute(sql)
		category.append(db.fetchone())
	db.execute('select distinct CategoryID,CategoryName from store_categories')		
	filter_cat=db.fetchall()
	return render_template('buysell/store.html',entries=entries,uploader=uploader,category=category,filter_cat=filter_cat)

@app.route('/filter_store',methods=['POST'])
def filter_store():
	session["currentpage"]="Bech De!"
	db=get_cursor()
	category=int(request.form['filter'])
	sql='select * from store where categoryid="%s"'%(category)
	db.execute(sql)
	entries=db.fetchall()
	uploader=[]
	category=[]
	for entry in entries:
		sql='select UserName from login where RollNo="%s"'%(entry[0])
		db.execute(sql)
		uploader.append(db.fetchone())
		db.execute("commit")
		sql='select CategoryName from store_categories where categoryid=%s'%(entry[4])
		db.execute(sql)
		category.append(db.fetchone())
	db.execute('select distinct CategoryID,CategoryName from store_categories')		
	filter_cat=db.fetchall()
	return render_template('buysell/store.html',entries=entries,uploader=uploader,category=category,filter_cat=filter_cat)

if __name__ == "__main__":
	app.debug = True
	app.secret_key=os.urandom(24)
	app.run(host='0.0.0.0')